#!/usr/bin/env python3
"""
概念库索引生成器 — build_index.py

三种模式：
  python3 scripts/build_index.py               全量扫描，重建索引
  python3 scripts/build_index.py --incremental  只处理变动文件，重算派生数据
  python3 scripts/build_index.py --check        校验 frontmatter 词汇表合规

输出：memory/concept_lite.json   — 轻量索引（查重+分类，各模块日常使用）
      memory/concept_graph.json  — 图结构索引（关联分析专用）
      memory/concept_meta.json   — 管理元数据（文件路径/来源/日期）
依赖：纯 Python 标准库，无需 pip install
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

# 公共模块：路径常量、frontmatter 解析、词汇表（单一数据源）、集群解析等
from _common import (
    CONCEPT_DIR,
    LIB_ROOT,
    MEMORY_DIR,
    LITE_PATH,
    GRAPH_PATH,
    META_PATH,
    ALIASES_PATH,
    RELATIONS_PATH,
    VOCABULARY,
    parse_frontmatter,
    extract_english_name,
    extract_wikilinks,
    parse_tags,
    parse_relations_clusters,
    iter_concept_files,
    atomic_write_json as _atomic_write,
)

# 旧格式索引路径（过渡期保留，不放入公共模块）
INDEX_PATH = os.path.join(MEMORY_DIR, "concept_index.json")

# ── 以下函数已迁移至 _common.py，从此处导入 ──
# parse_frontmatter / extract_wikilinks / parse_tags / extract_english_name

# ── 单文件扫描 ────────────────────────────────────────────

def scan_file(filepath: str) -> Optional[dict]:
    """扫描一个概念页，返回 node dict。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    fm = parse_frontmatter(content)
    if not fm:
        return None

    filename = os.path.basename(filepath)
    # 从文件名去掉 .md 得到概念中文名
    name_cn = filename[:-3] if filename.endswith('.md') else filename

    # 跳过 INDEX.md
    if name_cn == 'INDEX':
        return None

    # name 字段
    name_field = fm.get('name', name_cn)
    name_en = extract_english_name(name_field) if name_field else None

    # domain
    domain = fm.get('domain', [])
    if isinstance(domain, str):
        domain = [domain]

    # tags
    tags = parse_tags(fm.get('tags', []))

    # source
    source = fm.get('source', '')

    # date
    date = fm.get('date', '')

    # person 标签
    persons = []
    raw_tags = fm.get('tags', [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    for tag in raw_tags:
        if tag.startswith("person/"):
            persons.append(tag[len("person/"):])

    # 出链
    out_links = extract_wikilinks(content)

    return {
        "file": filename,
        "name": name_field,
        "name_en": name_en,
        "domain": domain,
        "discipline": tags["discipline"],
        "apply": tags["apply"],
        "persons": persons,
        "source": source,
        "date": date,
        "out_links": out_links,
        "in_links": [],
        "out_degree": len(out_links),
        "in_degree": 0,
    }


# ── 派生数据计算 ──────────────────────────────────────────

def compute_in_links(nodes: dict) -> None:
    """根据 out_links 反算 in_links 和 in_degree。"""
    # 清零
    for node in nodes.values():
        node["in_links"] = []
        node["in_degree"] = 0

    for name, node in nodes.items():
        for target in node["out_links"]:
            if target in nodes:
                nodes[target]["in_links"].append(name)
                nodes[target]["in_degree"] += 1


def compute_edges(nodes: dict) -> List[dict]:
    """生成边列表。"""
    edges = []
    for name, node in nodes.items():
        for target in node["out_links"]:
            edges.append({"source": name, "target": target})
    return edges


def compute_orphans(nodes: dict) -> dict:
    """计算孤立概念。"""
    fully = []
    semi = []
    for name, node in nodes.items():
        if node["out_degree"] == 0:
            if node["in_degree"] == 0:
                fully.append(name)
            else:
                semi.append({"name": name, "in_degree": node["in_degree"]})

    fully.sort()
    semi.sort(key=lambda x: x["in_degree"], reverse=True)
    return {"fully_isolated": fully, "semi_isolated": semi}


def compute_broken_links(nodes: dict) -> List[dict]:
    """计算断链（出链目标不在 nodes 中且不在 name_aliases 中）。"""
    broken = []
    for name, node in nodes.items():
        for target in node["out_links"]:
            if target not in nodes:
                broken.append({"source": name, "target": target})
    return broken


def compute_inverted_index(nodes: dict, field: str) -> Dict[str, List[str]]:
    """按某个字段构建倒排索引。field 可以是 'apply', 'domain', 'discipline'。"""
    index = defaultdict(list)
    for name, node in nodes.items():
        values = node.get(field)
        if values is None:
            continue
        if isinstance(values, str):
            values = [values]
        for v in values:
            if v:
                index[v].append(name)

    # 排序
    for k in index:
        index[k].sort()
    return dict(sorted(index.items()))


def compute_name_en_index(nodes: dict) -> Dict[str, str]:
    """构建英文名倒排索引: name_en.lower() -> 中文名。
    冲突时用 ' | ' 连接多个中文名（如同一概念的不同翻译）。
    """
    index = {}
    for name, node in nodes.items():
        en = node.get("name_en")
        if en:
            en_lower = en.lower()
            if en_lower in index:
                print(f"  ⚠️ 英文名冲突: '{en}' → {index[en_lower]} 和 {name}")
                index[en_lower] = index[en_lower] + " | " + name
            else:
                index[en_lower] = name
    return dict(sorted(index.items()))


# ── 连通分量（Union-Find）─────────────────────────────────

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> None:
        px, py = self.find(x), self.find(y)
        if px == py:
            return
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1


def compute_connected_components(nodes: dict) -> List[List[str]]:
    """计算图的连通分量，只返回 size >= 2 的。"""
    names = sorted(nodes.keys())
    name_to_idx = {n: i for i, n in enumerate(names)}
    uf = UnionFind(len(names))

    for name, node in nodes.items():
        src_idx = name_to_idx[name]
        for target in node["out_links"]:
            if target in name_to_idx:
                tgt_idx = name_to_idx[target]
                uf.union(src_idx, tgt_idx)

    # 分组
    groups = defaultdict(list)
    for i, n in enumerate(names):
        root = uf.find(i)
        groups[root].append(n)

    # 过滤 size >= 2，按 size 降序
    result = [sorted(g) for g in groups.values() if len(g) >= 2]
    result.sort(key=lambda g: len(g), reverse=True)
    return result


# ── 重复检测 ──────────────────────────────────────────────

def _lcs_ratio(s1: str, s2: str) -> float:
    """最长公共子序列比率（0-1）。"""
    if not s1 or not s2:
        return 0.0
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs_len = dp[m][n]
    return 2 * lcs_len / (m + n)


def detect_duplicates(nodes: dict) -> List[dict]:
    """检测潜在重复概念。同 domain+discipline 下名称相似度 > 0.7 的配对。"""
    # 按 domain+discipline 分组
    groups = defaultdict(list)
    for name, node in nodes.items():
        key = (tuple(sorted(node.get("domain", []))),
               tuple(sorted(node.get("discipline", []))))
        groups[key].append(name)

    duplicates = []
    for key, names in groups.items():
        if len(names) < 2:
            continue
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                ratio = _lcs_ratio(names[i], names[j])
                if ratio > 0.7:
                    duplicates.append({
                        "concepts": [names[i], names[j]],
                        "reason": f"同 domain+discipline, 名称相似度 {ratio:.2f}",
                    })

    # 英文名重复检测
    en_names = {}
    for name, node in nodes.items():
        en = node.get("name_en")
        if en:
            en_lower = en.lower()
            if en_lower in en_names:
                duplicates.append({
                    "concepts": [en_names[en_lower], name],
                    "reason": f"英文名重复: {en}",
                })
            else:
                en_names[en_lower] = name

    return duplicates


# ── 从 concept_relations.md 加载集群（使用 _common 的唯一实现） ──

def load_clusters_from_relations(relations_path: str) -> List[dict]:
    """解析 concept_relations.md 中的集群定义。（兼容接口，委托给 _common）"""
    if not os.path.exists(relations_path):
        return []
    try:
        with open(relations_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except IOError:
        return []
    return parse_relations_clusters(content)


# ── 从 name_aliases.json 加载别名 ────────────────────────

def load_name_aliases(aliases_path: str) -> dict:
    """加载同义名映射。"""
    if not os.path.exists(aliases_path):
        return {}
    try:
        with open(aliases_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}


# ── 词汇表校验 ────────────────────────────────────────────

def validate_frontmatter(nodes: dict, vocab: dict) -> List[dict]:
    """校验每个节点的 frontmatter 是否符合词汇表白名单。"""
    violations = []

    for name, node in nodes.items():
        # domain
        for d in node.get("domain", []):
            if d not in vocab["domain"]:
                violations.append({
                    "concept": name, "field": "domain", "value": d,
                    "allowed": vocab["domain"],
                })

        # discipline
        for d in node.get("discipline", []):
            if d not in vocab["discipline"]:
                violations.append({
                    "concept": name, "field": "discipline", "value": d,
                    "allowed": f"参见 vocabulary.discipline（{len(vocab['discipline'])}个）",
                })

        # apply
        for a in node.get("apply", []):
            if a not in vocab["apply"]:
                violations.append({
                    "concept": name, "field": "apply", "value": a,
                    "allowed": vocab["apply"],
                })

        # source
        s = node.get("source", "")
        if s and s not in vocab["source"]:
            violations.append({
                "concept": name, "field": "source", "value": s,
                "allowed": vocab["source"],
            })

        # name 格式
        name_field = node.get("name", "")
        if name_field and not re.search(r'（[^）]+）', name_field):
            # 宽松：不强制报错，只 warn
            pass

        # 缺 discipline
        if not node.get("discipline"):
            violations.append({
                "concept": name, "field": "discipline", "value": "(缺失)",
                "allowed": "至少一个 discipline 标签",
            })

        # 缺 apply
        if not node.get("apply"):
            violations.append({
                "concept": name, "field": "apply", "value": "(缺失)",
                "allowed": vocab["apply"],
            })

        # 缺 domain
        if not node.get("domain"):
            violations.append({
                "concept": name, "field": "domain", "value": "(缺失)",
                "allowed": vocab["domain"],
            })

    return violations


# ── 全量构建 ──────────────────────────────────────────────

def build_full_index() -> dict:
    """全量扫描概念页，构建完整索引。"""
    start_time = time.time()

    # 扫描所有 .md 文件
    nodes = {}
    scanned = 0
    for fname in os.listdir(CONCEPT_DIR):
        if not fname.endswith('.md') or fname == 'INDEX.md':
            continue
        filepath = os.path.join(CONCEPT_DIR, fname)
        if not os.path.isfile(filepath):
            continue

        node = scan_file(filepath)
        if node:
            # 从文件名提取中文名作为 key
            name_cn = fname[:-3]
            nodes[name_cn] = node
            scanned += 1

    # 计算派生数据
    compute_in_links(nodes)
    edges = compute_edges(nodes)
    orphans = compute_orphans(nodes)
    broken = compute_broken_links(nodes)
    components = compute_connected_components(nodes)
    duplicates = detect_duplicates(nodes)

    # 倒排索引
    apply_idx = compute_inverted_index(nodes, "apply")
    domain_idx = compute_inverted_index(nodes, "domain")
    discipline_idx = compute_inverted_index(nodes, "discipline")

    # 集群（从 concept_relations.md 加载）
    clusters = load_clusters_from_relations(RELATIONS_PATH)

    # 别名
    aliases = load_name_aliases(ALIASES_PATH)

    # 统计
    total_wikilinks = sum(n["out_degree"] for n in nodes.values())
    unique_targets = len(set(
        t for n in nodes.values() for t in n["out_links"]
    ))

    elapsed = time.time() - start_time

    return {
        "meta": {
            "version": 1,
            "total_concepts": len(nodes),
            "last_built": datetime.now(timezone.utc).isoformat(),
            "build_mode": "full",
            "source_path": CONCEPT_DIR,
            "scan_stats": {
                "files_scanned": scanned,
                "wikilinks_found": total_wikilinks,
                "unique_targets": unique_targets,
                "build_duration_seconds": round(elapsed, 3),
            },
        },
        "nodes": dict(sorted(nodes.items())),
        "edges": edges,
        "orphan_nodes": orphans,
        "broken_links": broken,
        "clusters": clusters,
        "apply_index": apply_idx,
        "domain_index": domain_idx,
        "discipline_index": discipline_idx,
        "name_aliases": aliases,
        "potential_duplicates": duplicates,
        "vocabulary": VOCABULARY,
    }


# ── 增量构建 ──────────────────────────────────────────────

def build_incremental_index() -> dict:
    """增量更新：只重扫变动文件，但重算所有派生数据。"""
    existing = load_existing_shards()
    if existing is None:
        print("索引文件不存在，回退到全量构建")
        return build_full_index()

    last_built_str = existing.get("meta", {}).get("last_built", "")
    if not last_built_str:
        print("无法读取 last_built 时间戳，回退到全量构建")
        return build_full_index()

    try:
        last_built = datetime.fromisoformat(last_built_str)
    except ValueError:
        print(f"无法解析时间戳: {last_built_str}，回退到全量构建")
        return build_full_index()

    # 如果时间戳无时区，假设 UTC
    if last_built.tzinfo is None:
        last_built = last_built.replace(tzinfo=timezone.utc)

    nodes = existing.get("nodes", {})
    indexed_files = {node["file"] for node in nodes.values()}

    # 当前文件系统上的文件
    current_files = set()
    for fname in os.listdir(CONCEPT_DIR):
        if fname.endswith('.md') and fname != 'INDEX.md':
            fpath = os.path.join(CONCEPT_DIR, fname)
            if os.path.isfile(fpath):
                current_files.add(fname)

    added = current_files - indexed_files
    removed = indexed_files - current_files

    # mtime > last_built 的文件
    modified = set()
    for fname in current_files:
        filepath = os.path.join(CONCEPT_DIR, fname)
        mtime = datetime.fromtimestamp(
            os.path.getmtime(filepath), tz=timezone.utc
        )
        if mtime > last_built:
            modified.add(fname)

    to_scan = added | modified

    start_time = time.time()

    # 重扫变动文件
    for fname in to_scan:
        filepath = os.path.join(CONCEPT_DIR, fname)
        node = scan_file(filepath)
        if node:
            name_cn = fname[:-3]
            nodes[name_cn] = node

    # 回填新增字段：旧节点可能缺少 persons 等字段
    for fname in current_files - to_scan:
        name_cn = fname[:-3]
        node = nodes.get(name_cn)
        if node and "persons" not in node:
            filepath = os.path.join(CONCEPT_DIR, fname)
            fresh = scan_file(filepath)
            if fresh and "persons" in fresh:
                node["persons"] = fresh["persons"]

    # 删除已不存在的文件
    removed_names = []
    for name, node in nodes.items():
        if node["file"] in removed:
            removed_names.append(name)
    for name in removed_names:
        del nodes[name]

    # 重算所有派生数据
    compute_in_links(nodes)
    edges = compute_edges(nodes)
    orphans = compute_orphans(nodes)
    broken = compute_broken_links(nodes)
    components = compute_connected_components(nodes)
    duplicates = detect_duplicates(nodes)

    apply_idx = compute_inverted_index(nodes, "apply")
    domain_idx = compute_inverted_index(nodes, "domain")
    discipline_idx = compute_inverted_index(nodes, "discipline")

    clusters = load_clusters_from_relations(RELATIONS_PATH)
    aliases = load_name_aliases(ALIASES_PATH)

    elapsed = time.time() - start_time

    total_wikilinks = sum(n["out_degree"] for n in nodes.values())
    unique_targets = len(set(
        t for n in nodes.values() for t in n["out_links"]
    ))

    return {
        "meta": {
            "version": 1,
            "total_concepts": len(nodes),
            "last_built": datetime.now(timezone.utc).isoformat(),
            "build_mode": "incremental",
            "source_path": CONCEPT_DIR,
            "scan_stats": {
                "files_scanned": len(to_scan),
                "files_added": len(added),
                "files_modified": len(modified),
                "files_removed": len(removed),
                "wikilinks_found": total_wikilinks,
                "unique_targets": unique_targets,
                "build_duration_seconds": round(elapsed, 3),
            },
        },
        "nodes": dict(sorted(nodes.items())),
        "edges": edges,
        "orphan_nodes": orphans,
        "broken_links": broken,
        "clusters": clusters,
        "apply_index": apply_idx,
        "domain_index": domain_idx,
        "discipline_index": discipline_idx,
        "name_aliases": aliases,
        "potential_duplicates": duplicates,
        "vocabulary": VOCABULARY,
    }


# ── 校验模式 ──────────────────────────────────────────────

def run_check() -> None:
    """校验所有概念页 frontmatter 是否合规。"""
    nodes = {}
    for fname in os.listdir(CONCEPT_DIR):
        if not fname.endswith('.md') or fname == 'INDEX.md':
            continue
        filepath = os.path.join(CONCEPT_DIR, fname)
        if not os.path.isfile(filepath):
            continue
        node = scan_file(filepath)
        if node:
            nodes[fname[:-3]] = node

    violations = validate_frontmatter(nodes, VOCABULARY)

    print(f"概念库校验报告（{len(nodes)} 概念）\n")

    if not violations:
        print("所有概念页 frontmatter 均合规。")
        return

    # 按字段分组
    by_field = defaultdict(list)
    for v in violations:
        by_field[v["field"]].append(v)

    for field, items in sorted(by_field.items()):
        print(f"### {field} 问题（{len(items)} 处）：")
        for item in items:
            val = item["value"]
            print(f"  - {item['concept']}: {field} = {val}")
        print()

    print(f"共 {len(violations)} 处问题。")


# ── 原子写入 ──────────────────────────────────────────────

# _atomic_write 已从 _common 导入，此处不再重复定义


def write_shards(index: dict) -> None:
    """将索引拆分为 3 个分片文件写入。过渡期同时写入旧格式。"""
    nodes = index["nodes"]
    meta = index["meta"]

    # ── 1. concept_lite.json ──
    names = sorted(nodes.keys())
    nodes_lite = {}
    for n, data in nodes.items():
        nodes_lite[n] = {
            "name": data["name"],
            "name_en": data.get("name_en"),
            "domain": data.get("domain", []),
            "discipline": data.get("discipline", []),
            "apply": data.get("apply", []),
            "persons": data.get("persons", []),
        }

    lite = {
        "meta": {**meta, "shard": "lite"},
        "names": names,
        "name_en_index": compute_name_en_index(nodes),
        "nodes_lite": dict(sorted(nodes_lite.items())),
        "apply_index": index["apply_index"],
        "domain_index": index["domain_index"],
        "discipline_index": index["discipline_index"],
        "name_aliases": index["name_aliases"],
        "orphan_nodes": index["orphan_nodes"],
        "vocabulary": index["vocabulary"],
    }

    # ── 2. concept_graph.json ──
    nodes_graph = {}
    for n, data in nodes.items():
        nodes_graph[n] = {
            "out_links": data["out_links"],
            "in_links": data["in_links"],
            "out_degree": data["out_degree"],
            "in_degree": data["in_degree"],
        }

    graph = {
        "meta": {**meta, "shard": "graph"},
        "nodes_graph": dict(sorted(nodes_graph.items())),
        "edges": index["edges"],
        "broken_links": index["broken_links"],
        "clusters": index["clusters"],
        "potential_duplicates": index["potential_duplicates"],
    }

    # ── 3. concept_meta.json ──
    nodes_meta = {}
    for n, data in nodes.items():
        nodes_meta[n] = {
            "file": data["file"],
            "source": data.get("source", ""),
            "date": data.get("date", ""),
        }

    meta_shard = {
        "meta": {**meta, "shard": "meta"},
        "nodes_meta": dict(sorted(nodes_meta.items())),
    }

    # 原子写入（compact 格式）
    _atomic_write(LITE_PATH, lite, compact=True)
    _atomic_write(GRAPH_PATH, graph, compact=True)
    _atomic_write(META_PATH, meta_shard, compact=True)

    # 过渡期：同时写入旧格式（标记 deprecated）
    deprecated_index = dict(index)
    deprecated_index["meta"]["deprecated"] = True
    _atomic_write(INDEX_PATH, deprecated_index, compact=False)


# ── 自洽性检查 ────────────────────────────────────────────

def self_check(index: dict) -> List[str]:
    """索引自洽性验证，返回警告列表。"""
    warnings = []
    nodes = index["nodes"]

    # 概念数一致
    if len(nodes) != index["meta"]["total_concepts"]:
        warnings.append(
            f"nodes 数量 {len(nodes)} ≠ meta.total_concepts {index['meta']['total_concepts']}"
        )

    # 边数一致
    total_out = sum(n["out_degree"] for n in nodes.values())
    if total_out != len(index["edges"]):
        warnings.append(
            f"edges 数量 {len(index['edges'])} ≠ sum(out_degree) {total_out}"
        )

    # 孤立节点存在于 nodes
    for name in index["orphan_nodes"].get("fully_isolated", []):
        if name not in nodes:
            warnings.append(f"孤立节点 '{name}' 不在 nodes 中")

    for item in index["orphan_nodes"].get("semi_isolated", []):
        if item["name"] not in nodes:
            warnings.append(f"半孤立节点 '{item['name']}' 不在 nodes 中")

    # 断链目标不在 nodes
    for bl in index["broken_links"]:
        if bl["target"] in nodes:
            warnings.append(f"断链 '{bl['source']}'→'{bl['target']}' 目标实际存在")

    return warnings


def self_check_shards() -> List[str]:
    """验证 3 个分片文件间的一致性。"""
    warnings = []

    if not all(os.path.exists(p) for p in [LITE_PATH, GRAPH_PATH, META_PATH]):
        warnings.append("分片文件不完整，缺少部分文件")
        return warnings

    with open(LITE_PATH, 'r', encoding='utf-8') as f:
        lite = json.load(f)
    with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    with open(META_PATH, 'r', encoding='utf-8') as f:
        meta_shard = json.load(f)

    # 概念数一致
    n1 = len(lite.get("names", []))
    n2 = len(graph.get("nodes_graph", {}))
    n3 = len(meta_shard.get("nodes_meta", {}))
    if not (n1 == n2 == n3):
        warnings.append(f"分片概念数不一致: lite={n1}, graph={n2}, meta={n3}")

    # name_en_index 完整性（允许冲突合并）
    en_count = sum(1 for n in lite.get("nodes_lite", {})
                   if lite["nodes_lite"][n].get("name_en"))
    en_index_count = len(lite.get("name_en_index", {}))
    # 冲突合并时 en_index_count < en_count 是正常的
    if en_index_count > en_count:
        warnings.append(
            f"name_en_index 条目数 {en_index_count} "
            f"> 有英文名的概念数 {en_count}（不应发生）"
        )

    # 边数一致
    total_out = sum(n["out_degree"] for n in graph.get("nodes_graph", {}).values())
    if total_out != len(graph.get("edges", [])):
        warnings.append(
            f"edges 数量 {len(graph.get('edges', []))} ≠ sum(out_degree) {total_out}"
        )

    return warnings


def load_existing_shards() -> Optional[dict]:
    """加载现有分片数据，合并为完整 nodes。兼容旧格式。"""
    # 优先从分片加载
    if os.path.exists(LITE_PATH) and os.path.exists(GRAPH_PATH):
        with open(LITE_PATH, 'r', encoding='utf-8') as f:
            lite = json.load(f)
        with open(GRAPH_PATH, 'r', encoding='utf-8') as f:
            graph = json.load(f)

        meta_shard = {}
        if os.path.exists(META_PATH):
            with open(META_PATH, 'r', encoding='utf-8') as f:
                meta_shard = json.load(f)

        # 合并为完整 nodes
        nodes = {}
        for name in lite.get("names", []):
            lite_node = lite.get("nodes_lite", {}).get(name, {})
            graph_node = graph.get("nodes_graph", {}).get(name, {})
            meta_node = meta_shard.get("nodes_meta", {}).get(name, {})
            nodes[name] = {**lite_node, **graph_node, **meta_node}

        return {
            "meta": lite.get("meta", {}),
            "nodes": nodes,
            "edges": graph.get("edges", []),
            "orphan_nodes": lite.get("orphan_nodes", {}),
            "broken_links": graph.get("broken_links", []),
            "clusters": graph.get("clusters", []),
            "apply_index": lite.get("apply_index", {}),
            "domain_index": lite.get("domain_index", {}),
            "discipline_index": lite.get("discipline_index", {}),
            "name_aliases": lite.get("name_aliases", {}),
            "potential_duplicates": graph.get("potential_duplicates", []),
            "vocabulary": lite.get("vocabulary", {}),
        }

    # 回退到旧格式
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    return None


# ── person 标签频次统计 ────────────────────────────────────

# person 标签准入门槛
PERSON_THRESHOLD = 5
# 当前白名单（与 page-spec.md 保持同步）
PERSON_WHITELIST = [
    "维特根斯坦", "康德", "庄子", "海德格尔", "弗洛伊德",
    "卡尼曼", "布迪厄", "福柯", "胡塞尔", "阿伦特",
]


def check_person_tags(nodes: dict) -> None:
    """统计 person 标签频次，检测是否有人跨过准入门槛。"""
    from collections import Counter

    freq = Counter()
    for name, node in nodes.items():
        for p in node.get("persons", []):
            freq[p] += 1

    if not freq:
        return

    # 检测：非白名单学者频次 >= 阈值 → 建议加入白名单
    new_candidates = []
    for scholar, count in freq.most_common():
        if count >= PERSON_THRESHOLD and scholar not in PERSON_WHITELIST:
            new_candidates.append((scholar, count))

    if new_candidates:
        print("\n📢 person 标签门槛检测：")
        for scholar, count in new_candidates:
            print(f"  ⬆️ {scholar} 出现 {count} 次，已达准入门槛（≥{PERSON_THRESHOLD}），建议加入 page-spec 白名单")
        print("  → 请更新 skills/concept-studio/modules/page-spec.md 中的白名单")

    # 检测：白名单中学者频次 < 阈值 → 建议移出
    low_freq = []
    for scholar in PERSON_WHITELIST:
        if freq.get(scholar, 0) < PERSON_THRESHOLD:
            low_freq.append((scholar, freq.get(scholar, 0)))

    if low_freq:
        if not new_candidates:
            print("\n📢 person 标签门槛检测：")
        for scholar, count in low_freq:
            print(f"  ⬇️ {scholar} 仅出现 {count} 次，低于门槛（≥{PERSON_THRESHOLD}），建议从白名单移除")


# ── main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="概念库索引生成器")
    parser.add_argument(
        "--incremental", "-i",
        action="store_true",
        help="增量模式：只处理变动文件",
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="校验模式：检查 frontmatter 词汇表合规",
    )
    args = parser.parse_args()

    if args.check:
        run_check()
        return

    print(f"概念页目录: {CONCEPT_DIR}")

    if args.incremental:
        print("模式: 增量")
        index = build_incremental_index()
    else:
        print("模式: 全量")
        index = build_full_index()

    # 自洽性检查（全量索引）
    warnings = self_check(index)
    if warnings:
        print("\n⚠️ 自洽性警告：")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("\n✅ 自洽性检查通过")

    # 写入分片
    write_shards(index)

    # 分片自检
    shard_warnings = self_check_shards()
    if shard_warnings:
        print("\n⚠️ 分片一致性警告：")
        for w in shard_warnings:
            print(f"  - {w}")
    else:
        print("✅ 分片一致性检查通过")

    # 输出摘要
    meta = index["meta"]
    print(f"\n索引构建完成")
    print(f"  概念数: {meta['total_concepts']}")
    print(f"  孤立节点: {len(index['orphan_nodes']['fully_isolated'])} 完全 + "
          f"{len(index['orphan_nodes']['semi_isolated'])} 半孤立")
    print(f"  断链: {len(index['broken_links'])} 处")
    print(f"  边数: {len(index['edges'])}")
    print(f"  集群: {len(index['clusters'])} 个")
    print(f"  潜在重复: {len(index['potential_duplicates'])} 对")
    print(f"  耗时: {meta['scan_stats']['build_duration_seconds']}s")

    # 分片文件大小
    for path, label in [(LITE_PATH, "lite"), (GRAPH_PATH, "graph"), (META_PATH, "meta")]:
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  分片 {label}: {size / 1024:.1f} KB")

    # person 标签门槛检测
    check_person_tags(index["nodes"])


if __name__ == "__main__":
    main()
