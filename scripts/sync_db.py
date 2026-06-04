#!/usr/bin/env python3
"""
概念库 SQLite 索引层 — sync_db.py

将概念页 .md 文件同步到 SQLite 数据库，提供结构化查询能力。
.md 文件是权威数据源，SQLite 是索引层（可重建）。

用法：
  python3 scripts/sync_db.py                  全量同步（首次或修复用）
  python3 scripts/sync_db.py --incremental    增量同步（只处理变动文件）
  python3 scripts/sync_db.py --file 概念名     只同步单个概念
  python3 scripts/sync_db.py --query "SQL"    执行自定义查询
  python3 scripts/sync_db.py --stats          输出数据库统计信息
  python3 scripts/sync_db.py --check          校验数据库与文件系统一致性

集成点：
  新增/修改概念页后，自动执行 --incremental 确保 DB 与文件系统一致。
  可在 concept-studio 的 ingest/parable/hook 流程末尾加入此步骤。
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ── 路径常量 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_ROOT = os.path.dirname(SCRIPT_DIR)
CONCEPT_DIR = os.path.join(LIB_ROOT, "概念页")
MEMORY_DIR = os.path.join(LIB_ROOT, "memory")
DB_PATH = os.path.join(MEMORY_DIR, "concepts.db")
RELATIONS_PATH = os.path.join(MEMORY_DIR, "concept_relations.md")

# ── Schema 版本 ───────────────────────────────────────────
SCHEMA_VERSION = 1


# ══════════════════════════════════════════════════════════
#  Frontmatter / Wikilink 解析（复用 build_index.py 的逻辑）
# ══════════════════════════════════════════════════════════

def parse_frontmatter(content: str) -> Optional[dict]:
    """提取 YAML frontmatter，返回字段字典。不依赖 PyYAML。"""
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None

    raw = m.group(1)
    result = {}

    for line in raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        colon_idx = line.find(":")
        if colon_idx < 0:
            continue

        key = line[:colon_idx].strip()
        val = line[colon_idx + 1:].strip()

        if val.startswith("[") and val.endswith("]"):
            items = re.findall(r"[^\[\],\s]+", val)
            result[key] = items
        elif val.startswith('"') or val.startswith("'"):
            result[key] = val.strip('"').strip("'")
        else:
            result[key] = val

    return result


def extract_english_name(name_field: str) -> Optional[str]:
    """从 '弱意志（Akrasia）' 提取英文名。"""
    m = re.search(r"（([^）]+)）", name_field)
    if m:
        return m.group(1).strip()
    m = re.search(r"\(([^)]+)\)", name_field)
    if m:
        return m.group(1).strip()
    return None


def extract_wikilinks(content: str) -> List[str]:
    """提取所有 [[目标名]] 链接，去重保序。"""
    raw = re.findall(r"\[\[([^\]]+)\]\]", content)
    targets = []
    seen = set()
    for r in raw:
        target = re.split(r"[|#]", r)[0].strip()
        if target and target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


def detect_link_context(content: str, target: str) -> str:
    """
    判断 [[target]] 出现在哪个章节。
    返回章节名（如 '核心机制'），找不到返回 ''。
    """
    # 找到所有 ## 章节 及其位置
    sections = list(re.finditer(r"^## (.+)$", content, re.MULTILINE))
    if not sections:
        return ""

    # 找 [[target]] 的位置
    link_pattern = re.escape(target)
    for m in re.finditer(rf"\[\[{link_pattern}\]\]", content):
        link_pos = m.start()

        # 二分找所属章节
        lo, hi = 0, len(sections) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if sections[mid].start() <= link_pos:
                lo = mid
            else:
                hi = mid - 1

        if sections[lo].start() <= link_pos:
            return sections[lo].group(1)

    return ""


def parse_tags(tags_value) -> dict:
    """拆分 tags 为 discipline/pattern/apply/person 四组。"""
    if isinstance(tags_value, str):
        tags_value = [tags_value]

    disciplines = []
    pattern = None
    applies = []
    persons = []

    for tag in tags_value:
        if tag.startswith("discipline/"):
            disciplines.append(tag[len("discipline/"):])
        elif tag.startswith("pattern/"):
            pattern = tag[len("pattern/"):]
        elif tag.startswith("apply/"):
            applies.append(tag[len("apply/"):])
        elif tag.startswith("person/"):
            persons.append(tag[len("person/"):])

    return {
        "discipline": disciplines,
        "pattern": pattern,
        "apply": applies,
        "persons": persons,
    }


# ══════════════════════════════════════════════════════════
#  数据库初始化
# ══════════════════════════════════════════════════════════

def get_connection() -> sqlite3.Connection:
    """获取数据库连接，启用 WAL 模式提升并发性能。"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # 返回 dict-style row
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """创建表结构（幂等，IF NOT EXISTS）。"""
    cursor = conn.cursor()

    # ── 元数据表 ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS db_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # ── 概念主表 ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS concepts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            name_en         TEXT,
            domains         TEXT NOT NULL DEFAULT '[]',
            date            TEXT NOT NULL DEFAULT '',
            source          TEXT NOT NULL DEFAULT '',
            tags            TEXT NOT NULL DEFAULT '[]',
            disciplines     TEXT NOT NULL DEFAULT '[]',
            pattern         TEXT DEFAULT NULL,
            applies         TEXT NOT NULL DEFAULT '[]',
            persons         TEXT NOT NULL DEFAULT '[]',
            filepath        TEXT NOT NULL UNIQUE,
            file_mtime      REAL NOT NULL DEFAULT 0,
            body_word_count INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT ''
        )
    """)

    # ── 关联关系表 ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id   INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            target_name TEXT NOT NULL,
            context     TEXT NOT NULL DEFAULT '',
            resolved    INTEGER NOT NULL DEFAULT 0,  -- 0=断链 1=实链
            target_id   INTEGER REFERENCES concepts(id) ON DELETE SET NULL,
            UNIQUE(source_id, target_name, context)
        )
    """)

    # ── 集群表 ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cluster_members (
            cluster_id  INTEGER NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
            concept_id  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
            PRIMARY KEY (cluster_id, concept_id)
        )
    """)

    # ── 全文检索表 ──
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS concepts_fts USING fts5(
            name,
            name_en,
            domains,
            source,
            content=concepts,
            content_rowid=id,
            tokenize='unicode61'
        )
    """)

    # ── 触发器：FTS 同步 ──
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS concepts_ai AFTER INSERT ON concepts BEGIN
            INSERT INTO concepts_fts(rowid, name, name_en, domains, source)
            VALUES (new.id, new.name, new.name_en, new.domains, new.source);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS concepts_ad AFTER DELETE ON concepts BEGIN
            INSERT INTO concepts_fts(concepts_fts, rowid, name, name_en, domains, source)
            VALUES ('delete', old.id, old.name, old.name_en, old.domains, old.source);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS concepts_au AFTER UPDATE ON concepts BEGIN
            INSERT INTO concepts_fts(concepts_fts, rowid, name, name_en, domains, source)
            VALUES ('delete', old.id, old.name, old.name_en, old.domains, old.source);
            INSERT INTO concepts_fts(rowid, name, name_en, domains, source)
            VALUES (new.id, new.name, new.name_en, new.domains, new.source);
        END
    """)

    # ── 索引 ──
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_resolved ON links(resolved)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_concepts_domain ON concepts(domains)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_concepts_source ON concepts(source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_concepts_date ON concepts(date)")

    # 写入 schema 版本
    cursor.execute(
        "INSERT OR REPLACE INTO db_meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )

    conn.commit()


# ══════════════════════════════════════════════════════════
#  单文件解析
# ══════════════════════════════════════════════════════════

def scan_one_file(filepath: str) -> Optional[dict]:
    """
    扫描一个概念页 .md 文件，返回结构化字典。
    返回 None 表示不是有效概念页。
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    fm = parse_frontmatter(content)
    if not fm:
        return None

    filename = os.path.basename(filepath)
    name_cn = filename[:-3] if filename.endswith(".md") else filename

    # 跳过 INDEX.md
    if name_cn == "INDEX":
        return None

    # name 字段
    name_field = fm.get("name", name_cn)
    name_en = extract_english_name(name_field) if name_field else None

    # domain
    domain = fm.get("domain", [])
    if isinstance(domain, str):
        domain = [domain]

    # tags
    tags_raw = fm.get("tags", [])
    parsed_tags = parse_tags(tags_raw)

    # source / date
    source = fm.get("source", "")
    date = fm.get("date", "")

    # 正文：去掉 frontmatter 后的部分
    body_start = content.find("---", content.find("---") + 3) + 3
    body = content[body_start:] if body_start > 3 else content
    cn_char_count = len(re.findall(r"[一-鿿]", body))

    # wikilinks
    out_links = extract_wikilinks(content)

    # 带上下文的链接详情
    link_details = []
    for target in out_links:
        ctx = detect_link_context(body, target)
        link_details.append({"target": target, "context": ctx})

    # 相对路径
    rel_path = os.path.relpath(filepath, LIB_ROOT)
    mtime = os.path.getmtime(filepath)

    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "name_cn": name_cn,
        "name": name_field,
        "name_en": name_en,
        "domain": domain,
        "tags": tags_raw if isinstance(tags_raw, list) else [tags_raw],
        "disciplines": parsed_tags["discipline"],
        "pattern": parsed_tags["pattern"],
        "applies": parsed_tags["apply"],
        "persons": parsed_tags["persons"],
        "source": source,
        "date": date,
        "filepath": rel_path,
        "mtime": mtime,
        "word_count": cn_char_count,
        "link_details": link_details,
        "now": now_iso,
    }


# ══════════════════════════════════════════════════════════
#  同步核心逻辑
# ══════════════════════════════════════════════════════════

def upsert_concept(conn: sqlite3.Connection, data: dict) -> int:
    """
    插入或更新一个概念，返回概念 ID。
    包含 links 表的级联更新。
    """
    cursor = conn.cursor()

    # UPSERT concepts
    cursor.execute("""
        INSERT INTO concepts (
            name, name_en, domains, date, source, tags,
            disciplines, pattern, applies, persons,
            filepath, file_mtime, body_word_count, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            name_en       = excluded.name_en,
            domains       = excluded.domains,
            date          = excluded.date,
            source        = excluded.source,
            tags          = excluded.tags,
            disciplines   = excluded.disciplines,
            pattern       = excluded.pattern,
            applies       = excluded.applies,
            persons       = excluded.persons,
            filepath      = excluded.filepath,
            file_mtime    = excluded.file_mtime,
            body_word_count = excluded.body_word_count,
            updated_at    = excluded.updated_at
    """, (
        data["name_cn"], data["name_en"], json.dumps(data["domain"], ensure_ascii=False),
        data["date"], data["source"], json.dumps(data["tags"], ensure_ascii=False),
        json.dumps(data["disciplines"], ensure_ascii=False), data["pattern"],
        json.dumps(data["applies"], ensure_ascii=False),
        json.dumps(data["persons"], ensure_ascii=False),
        data["filepath"], data["mtime"], data["word_count"], data["now"],
    ))

    concept_id = cursor.lastrowid

    # 如果是 UPDATE（name 已存在），取已有 ID
    cursor.execute("SELECT id FROM concepts WHERE name = ?", (data["name_cn"],))
    row = cursor.fetchone()
    if row:
        concept_id = row["id"]

    # 清除旧链接，重新插入
    cursor.execute("DELETE FROM links WHERE source_id = ?", (concept_id,))

    # 构建名字→ID 映射用于链接解析
    cursor.execute("SELECT name, id FROM concepts")
    name_to_id = {row["name"]: row["id"] for row in cursor.fetchall()}

    for ld in data["link_details"]:
        target_name = ld["target"]
        resolved = 1 if target_name in name_to_id else 0
        target_id = name_to_id.get(target_name)

        cursor.execute("""
            INSERT OR IGNORE INTO links (source_id, target_name, context, resolved, target_id)
            VALUES (?, ?, ?, ?, ?)
        """, (concept_id, target_name, ld["context"], resolved, target_id))

    conn.commit()
    return concept_id


def delete_concept(conn: sqlite3.Connection, name_cn: str) -> bool:
    """从数据库删除一个概念（级联删除 links 和 cluster_members）。"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM concepts WHERE name = ?", (name_cn,))
    deleted = cursor.rowcount > 0
    conn.commit()
    return deleted


def sync_full(conn: sqlite3.Connection) -> dict:
    """全量同步：扫描所有 .md 文件，重建整个数据库内容。"""
    start = time.time()
    cursor = conn.cursor()

    # 清空现有数据（保留表结构）
    cursor.execute("DELETE FROM links")
    cursor.execute("DELETE FROM cluster_members")
    cursor.execute("DELETE FROM clusters")
    cursor.execute("DELETE FROM concepts")
    conn.commit()

    scanned = 0
    upserted = 0
    skipped = 0
    errors = []

    for fname in sorted(os.listdir(CONCEPT_DIR)):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        fpath = os.path.join(CONCEPT_DIR, fname)
        if not os.path.isfile(fpath):
            continue

        scanned += 1
        try:
            data = scan_one_file(fpath)
            if data:
                upsert_concept(conn, data)
                upserted += 1
            else:
                skipped += 1
        except Exception as e:
            errors.append((fname, str(e)))

    # 同步集群
    cluster_count = sync_clusters(conn)

    elapsed = time.time() - start

    return {
        "mode": "full",
        "scanned": scanned,
        "upserted": upserted,
        "skipped": skipped,
        "errors": len(errors),
        "error_details": errors,
        "clusters": cluster_count,
        "elapsed": round(elapsed, 3),
    }


def sync_incremental(conn: sqlite3.Connection) -> dict:
    """
    增量同步：只处理新增或修改的文件。
    通过比较文件 mtime 与数据库中的 file_mtime 判断是否需要更新。
    """
    start = time.time()
    cursor = conn.cursor()

    # 数据库中已有的文件
    cursor.execute("SELECT name, filepath, file_mtime FROM concepts")
    db_files = {}
    for row in cursor.fetchall():
        db_files[row["filepath"]] = {"name": row["name"], "mtime": row["file_mtime"]}

    # 当前文件系统上的文件
    current_files = {}
    for fname in sorted(os.listdir(CONCEPT_DIR)):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        fpath = os.path.join(CONCEPT_DIR, fname)
        if os.path.isfile(fpath):
            rel_path = os.path.relpath(fpath, LIB_ROOT)
            current_files[rel_path] = {
                "fname": fname,
                "name_cn": fname[:-3],
                "mtime": os.path.getmtime(fpath),
                "fpath": fpath,
            }

    # 分类
    added = set(current_files.keys()) - set(db_files.keys())
    removed = set(db_files.keys()) - set(current_files.keys())

    modified = set()
    for fpath in current_files:
        if fpath in db_files:
            db_mtime = db_files[fpath]["mtime"]
            cur_mtime = current_files[fpath]["mtime"]
            if cur_mtime > db_mtime + 0.001:  # 浮点容差
                modified.add(fpath)

    to_process = added | modified

    upserted = 0
    deleted = 0
    errors = []

    for rel_path in to_process:
        info = current_files.get(rel_path)
        if not info:
            continue
        try:
            data = scan_one_file(info["fpath"])
            if data:
                upsert_concept(conn, data)
                upserted += 1
        except Exception as e:
            errors.append((info["fname"], str(e)))

    # 处理已删除的文件
    for rel_path in removed:
        name_cn = db_files[rel_path]["name"]
        if delete_concept(conn, name_cn):
            deleted += 1

    # 同步集群
    cluster_count = sync_clusters(conn)

    elapsed = time.time() - start

    return {
        "mode": "incremental",
        "added": len(added),
        "modified": len(modified),
        "removed": deleted,
        "upserted": upserted,
        "errors": len(errors),
        "error_details": errors,
        "clusters": cluster_count,
        "elapsed": round(elapsed, 3),
    }


def sync_single(conn: sqlite3.Connection, concept_name: str) -> dict:
    """只同步单个指定概念。"""
    start = time.time()
    filepath = os.path.join(CONCEPT_DIR, f"{concept_name}.md")

    if not os.path.exists(filepath):
        return {"error": f"文件不存在: {filepath}"}

    try:
        data = scan_one_file(filepath)
        if not data:
            return {"error": f"无法解析文件（可能缺少 frontmatter）: {filepath}"}

        concept_id = upsert_concept(conn, data)
        sync_clusters(conn)

        return {
            "mode": "single",
            "concept": concept_name,
            "id": concept_id,
            "elapsed": round(time.time() - start, 3),
        }
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════
#  集群同步
# ══════════════════════════════════════════════════════════

def sync_clusters(conn: sqlite3.Connection) -> int:
    """
    从 concept_relations.md 解析集群定义并同步到 clusters 表。
    返回同步的集群数量。
    """
    if not os.path.exists(RELATIONS_PATH):
        return 0

    try:
        with open(RELATIONS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError:
        return 0

    cursor = conn.cursor()

    # 清空旧集群
    cursor.execute("DELETE FROM cluster_members")
    cursor.execute("DELETE FROM clusters")

    # 解析集群（复用 build_index.py 的逻辑）
    clusters = _parse_relations_clusters(content)

    # 名字→ID 映射
    cursor.execute("SELECT name, id FROM concepts")
    name_to_id = {row["name"]: row["id"] for row in cursor.fetchall()}

    count = 0
    for cluster in clusters:
        cursor.execute(
            "INSERT INTO clusters (code, name, description) VALUES (?, ?, ?)",
            (cluster["id"], cluster["name"], cluster.get("description", "")),
        )
        cluster_id = cursor.lastrowid

        for member_name in cluster.get("members", []):
            if member_name in name_to_id:
                cursor.execute(
                    "INSERT OR IGNORE INTO cluster_members (cluster_id, concept_id) VALUES (?, ?)",
                    (cluster_id, name_to_id[member_name]),
                )

        count += 1

    conn.commit()
    return count


def _parse_relations_clusters(content: str) -> List[dict]:
    """解析 concept_relations.md 中的集群定义。"""
    clusters = []
    lines = content.split("\n")
    current_cluster = None
    current_members_raw = []
    members_parsed = False

    def _parse_members(raw_lines):
        text = "\n".join(raw_lines)
        members = re.findall(r"`([^`]+)`", text)
        if not members:
            members = [w.strip() for w in text.split() if w.strip()]
        return members

    def _finalize(cluster, raw_lines):
        if cluster and not cluster.get("_finalized"):
            if raw_lines and not cluster["members"]:
                cluster["members"] = _parse_members(raw_lines)
            cluster["_finalized"] = True
            cluster.pop("_finalized", None)
            clusters.append(cluster)

    for line in lines:
        header_match = re.match(r"###\s+([A-Z])\s*[·•]\s*(.+?)(?:\s*✅)?\s*$", line)
        if header_match:
            _finalize(current_cluster, current_members_raw)
            current_cluster = {
                "id": header_match.group(1),
                "name": header_match.group(2).strip(),
                "members": [],
                "description": "",
            }
            current_members_raw = []
            members_parsed = False
            continue

        if current_cluster is not None:
            stripped = line.strip()

            if not stripped:
                if current_members_raw and not members_parsed:
                    current_cluster["members"] = _parse_members(current_members_raw)
                    members_parsed = True
                continue

            if stripped.startswith(">"):
                if current_members_raw and not members_parsed:
                    current_cluster["members"] = _parse_members(current_members_raw)
                    members_parsed = True
                desc = stripped.lstrip("> ").strip()
                if current_cluster["description"]:
                    current_cluster["description"] += " " + desc
                else:
                    current_cluster["description"] = desc
                continue

            if stripped.startswith("#") or stripped.startswith("---"):
                _finalize(current_cluster, current_members_raw)
                current_cluster = None
                current_members_raw = []
                members_parsed = False
                continue

            if not members_parsed:
                current_members_raw.append(stripped)

    _finalize(current_cluster, current_members_raw)
    return clusters


# ══════════════════════════════════════════════════════════
#  查询接口
# ══════════════════════════════════════════════════════════

def run_query(conn: sqlite3.Connection, sql: str) -> None:
    """执行用户提供的 SQL 查询并格式化输出结果。"""
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
    except sqlite3.Error as e:
        print(f"SQL 错误: {e}", file=sys.stderr)
        sys.exit(1)

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    if not rows:
        print("(空结果集)")
        return

    # 计算列宽
    col_widths = [len(c) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            val_str = str(val) if val is not None else "NULL"
            col_widths[i] = max(col_widths[i], min(len(val_str), 80))

    # 表头
    header = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(columns))
    print(header)
    print("-" * len(header))

    # 数据行
    for row in rows:
        cells = []
        for i, val in enumerate(row):
            val_str = str(val) if val is not None else "NULL"
            if len(val_str) > 80:
                val_str = val_str[:77] + "..."
            cells.append(val_str.ljust(col_widths[i]))
        print(" | ".join(cells))

    print(f"\n{len(rows)} 行")


def run_stats(conn: sqlite3.Connection) -> None:
    """输出数据库统计摘要。"""
    cursor = conn.cursor()

    # 基本计数
    cursor.execute("SELECT COUNT(*) FROM concepts")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM links WHERE resolved = 1")
    real_links = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM links WHERE resolved = 0")
    broken_links = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM clusters")
    total_clusters = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cluster_members")
    cluster_assignments = cursor.fetchone()[0]

    # 按 domain 统计
    cursor.execute("""
        SELECT value, COUNT(*) FROM concepts, json_each(concepts.domains)
        GROUP BY value ORDER BY COUNT(*) DESC LIMIT 15
    """)
    domain_stats = cursor.fetchall()

    # 按 source 统计
    cursor.execute("""
        SELECT source, COUNT(*) FROM concepts
        GROUP BY source ORDER BY COUNT(*) DESC
    """)
    source_stats = cursor.fetchall()

    # 孤立节点（无出链且无入链）
    cursor.execute("""
        SELECT COUNT(*) FROM concepts c
        WHERE NOT EXISTS (SELECT 1 FROM links l WHERE l.source_id = c.id)
        AND NOT EXISTS (SELECT 1 FROM links l WHERE l.target_id = c.id)
    """)
    fully_isolated = cursor.fetchone()[0]

    # 半孤立（只有入链无出链 或 只有出链无入链）
    cursor.execute("""
        SELECT COUNT(*) FROM concepts c
        WHERE (EXISTS (SELECT 1 FROM links l WHERE l.source_id = c.id)
        != EXISTS (SELECT 1 FROM links l WHERE l.target_id = c.id))
    """)
    semi_isolated = cursor.fetchone()[0]

    # 出链/入链 Top 5
    cursor.execute("""
        SELECT c.name, COUNT(l.id) AS cnt
        FROM concepts c JOIN links l ON l.source_id = c.id
        GROUP BY c.name ORDER BY cnt DESC LIMIT 5
    """)
    top_out = cursor.fetchall()

    cursor.execute("""
        SELECT c.name, COUNT(l.id) AS cnt
        FROM concepts c JOIN links l ON l.target_id = c.id
        GROUP BY c.name ORDER BY cnt DESC LIMIT 5
    """)
    top_in = cursor.fetchall()

    # 数据库大小
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

    print("=" * 60)
    print(f"概念库 SQLite 索引 — {DB_PATH}")
    print(f"数据库大小: {db_size / 1024:.1f} KB")
    print("=" * 60)
    print(f"\n概念总数:     {total}")
    print(f"实链:         {real_links}")
    print(f"断链:         {broken_links}")
    print(f"集群数:       {total_clusters} （{cluster_assignments} 个归属）")
    print(f"完全孤立:     {fully_isolated}")
    print(f"半孤立:       {semi_isolated}")

    print(f"\n--- 按 Domain ---")
    for row in domain_stats:
        print(f"  {row[0]:12s} {row[1]:4d}")

    print(f"\n--- 按 Source ---")
    for row in source_stats:
        print(f"  {row[0]:10s} {row[1]:4d}")

    if top_out:
        print(f"\n--- 出链 Top 5 ---")
        for row in top_out:
            print(f"  {row[0]:20s} {row[1]:3d} 条")

    if top_in:
        print(f"\n--- 入链 Top 5 ---")
        for row in top_in:
            print(f"  {row[0]:20s} {row[1]:3d} 条")


def run_check(conn: sqlite3.Connection) -> List[str]:
    """
    校验数据库与文件系统的一致性。
    返回不一致项列表。
    """
    issues = []
    cursor = conn.cursor()

    # 1. DB 中有但文件不存在
    cursor.execute("SELECT name, filepath FROM concepts")
    for row in cursor.fetchall():
        full_path = os.path.join(LIB_ROOT, row["filepath"])
        if not os.path.exists(full_path):
            issues.append(f"DB 有但文件缺失: {row['name']} ({row['filepath']})")

    # 2. 文件存在但 DB 中没有
    db_names = set()
    cursor.execute("SELECT name FROM concepts")
    for row in cursor.fetchall():
        db_names.add(row["name"])

    for fname in os.listdir(CONCEPT_DIR):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        name_cn = fname[:-3]
        if name_cn not in db_names:
            issues.append(f"文件存在但 DB 缺失: {name_cn}")

    # 3. mtime 不一致
    cursor.execute("SELECT name, filepath, file_mtime FROM concepts")
    for row in cursor.fetchall():
        full_path = os.path.join(LIB_ROOT, row["filepath"])
        if os.path.exists(full_path):
            file_mtime = os.path.getmtime(full_path)
            if abs(file_mtime - row["file_mtime"]) > 1.0:  # 1 秒容差
                issues.append(
                    f"mtime 不一致: {row['name']} "
                    f"(DB={row['file_mtime']:.1f}, 文件={file_mtime:.1f})"
                )

    # 4. 断链检查
    cursor.execute("""
        SELECT c.name, l.target_name FROM links l
        JOIN concepts c ON c.id = l.source_id
        WHERE l.resolved = 0
    """)
    broken = cursor.fetchall()
    if broken:
        issues.append(f"断链 {len(broken)} 处:")
        for b in broken[:10]:
            issues.append(f"  {b[0]} → [{b[1]}]")
        if len(broken) > 10:
            issues.append(f"  ... 还有 {len(broken) - 10} 处")

    if issues:
        print(f"一致性校验 — 发现 {len(issues)} 个问题:\n")
        for issue in issues:
            print(f"  ⚠ {issue}")
    else:
        print("一致性校验通过 — 数据库与文件系统完全一致 ✅")

    return issues


# ══════════════════════════════════════════════════════════
#  常用查询快捷方式
# ══════════════════════════════════════════════════════════

def run_preset_queries(conn: sqlite3.Connection, preset: str) -> None:
    """执行预设的常用查询。"""
    queries = {
        "orphans": """
            SELECT name, name_en, domains, source
            FROM concepts c
            WHERE NOT EXISTS (SELECT 1 FROM links l WHERE l.source_id = c.id)
            AND NOT EXISTS (SELECT 1 FROM links l WHERE l.target_id = c.id)
            ORDER BY name
        """,
        "broken": """
            SELECT s.name AS source_name, l.target_name, l.context
            FROM links l
            JOIN concepts s ON s.id = l.source_id
            WHERE l.resolved = 0
            ORDER BY s.name, l.target_name
        """,
        "no-domain": """
            SELECT name, domains FROM concepts
            WHERE domains = '[]'
            ORDER BY name
        """,
        "no-discipline": """
            SELECT name, disciplines FROM concepts
            WHERE disciplines = '[]'
            ORDER BY name
        """,
        "recent": """
            SELECT name, date, source, updated_at
            FROM concepts
            WHERE date != ''
            ORDER BY date DESC, name
            LIMIT 20
        """,
        "highly-connected": """
            SELECT c.name,
                   (SELECT COUNT(*) FROM links WHERE source_id = c.id) AS out_deg,
                   (SELECT COUNT(*) FROM links WHERE target_id = c.id) AS in_deg
            FROM concepts c
            WHERE (SELECT COUNT(*) FROM links WHERE source_id = c.id) +
                  (SELECT COUNT(*) FROM links WHERE target_id = c.id) > 5
            ORDER BY out_deg + in_deg DESC
            LIMIT 20
        """,
        "by-domain-psychology": """
            SELECT name, name_en, source, date
            FROM concepts
            WHERE domains LIKE '%心理学%'
            ORDER BY name
        """,
        "clusters-detail": """
            SELECT cl.code, cl.name, cl.description,
                   COUNT(cm.concept_id) AS member_count,
                   GROUP_CONCAT(c2.name, ', ') AS members
            FROM clusters cl
            LEFT JOIN cluster_members cm ON cl.id = cm.cluster_id
            LEFT JOIN concepts c2 ON cm.concept_id = c2.id
            GROUP BY cl.id
            ORDER BY cl.code
        """,
    }

    if preset not in queries:
        available = ", ".join(sorted(queries.keys()))
        print(f"未知预设: '{preset}'\n可用预设: {available}", file=sys.stderr)
        sys.exit(1)

    print(f">>> 预设查询: {preset}\n")
    run_query(conn, queries[preset])


# ══════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="概念库 SQLite 索引同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 scripts/sync_db.py                     全量同步
  python3 scripts/sync_db.py --incremental        增量同步（推荐日常使用）
  python3 scripts/sync_db.py --file ELIZA效应     只同步单个概念
  python3 scripts/sync_db.py --stats              统计摘要
  python3 scripts/sync_db.py --check              一致性校验
  python3 scripts/sync_db.py --query "SELECT name, domains FROM concepts LIMIT 10"
  python3 scripts/sync_db.py --preset orphans     预设查询（orphans/broken/no-domain/recent/...）
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--incremental", "-i", action="store_true",
                       help="增量模式（只处理变动文件）")
    group.add_argument("--file", "-f", type=str,
                       help="只同步单个概念（不含 .md 后缀）")
    group.add_argument("--query", "-q", type=str,
                       help="执行 SQL 查询")
    group.add_argument("--preset", "-p", type=str,
                       help="执行预设查询（orphans/broken/no-domain/recent/highly-connected/clusters-detail）")
    group.add_argument("--stats", "-s", action="store_true",
                       help="输出统计摘要")
    group.add_argument("--check", "-c", action="store_true",
                       help="一致性校验")

    args = parser.parse_args()

    conn = get_connection()
    init_db(conn)

    try:
        if args.query:
            run_query(conn, args.query)
        elif args.preset:
            run_preset_queries(conn, args.preset)
        elif args.stats:
            run_stats(conn)
        elif args.check:
            run_check(conn)
        elif args.file:
            result = sync_single(conn, args.file)
            if "error" in result:
                print(f"错误: {result['error']}", file=sys.stderr)
                sys.exit(1)
            print(f"✅ 已同步: {result['concept']} (ID={result['id']}, {result['elapsed']}s)")
        elif args.incremental:
            result = sync_incremental(conn)
            _print_sync_result(result)
        else:
            result = sync_full(conn)
            _print_sync_result(result)
    finally:
        conn.close()


def _print_sync_result(result: dict) -> None:
    """格式化输出同步结果。"""
    mode_label = {"full": "全量", "incremental": "增量", "single": "单文件"}
    mode = result.get("mode", "unknown")

    print(f"同步完成 [{mode_label.get(mode, mode)}模式]")
    print(f"  耗时: {result.get('elapsed', '?')}s")

    if mode == "full":
        print(f"  扫描: {result['scanned']} 个文件")
        print(f"  入库: {result['upserted']} 个概念")
        print(f"  跳过: {result['skipped']} 个（无 frontmatter 等）")
    elif mode == "incremental":
        print(f"  新增: {result['added']} 个")
        print(f"  修改: {result['modified']} 个")
        print(f"  删除: {result['removed']} 个")
        print(f"  入库: {result['upserted']} 个")
    elif mode == "single":
        print(f"  概念: {result.get('concept', '?')}")

    if result.get("clusters") is not None:
        print(f"  集群: {result['clusters']} 个")

    if result.get("errors", 0) > 0:
        print(f"\n⚠ {result['errors']} 个错误:")
        for fname, err in result.get("error_details", [])[:10]:
            print(f"  {fname}: {err}")
    else:
        print("  无错误 ✅")


if __name__ == "__main__":
    main()
