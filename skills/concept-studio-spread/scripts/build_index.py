#!/usr/bin/env python3
"""
概念库索引生成器 — build_index.py（concept-studio-spread 版）

用法：
  python3 build_index.py --root /path/to/lib               全量扫描，重建索引
  python3 build_index.py --root /path/to/lib --incremental  只处理变动文件
  python3 build_index.py --root /path/to/lib --check        校验 frontmatter 词汇表合规

输出：
  {ROOT}/memory/concept_lite.json    — 轻量索引（查重+分类，各模块日常使用）
  {ROOT}/memory/concept_graph.json   — 图结构索引（关联分析专用）
  {ROOT}/memory/concept_meta.json    — 管理元数据（文件路径/来源/日期）

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


# ── 路径解析 ──────────────────────────────────────────────

def resolve_root(args_root: str = None) -> str:
    """解析概念库根目录路径。"""
    if args_root:
        return args_root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def get_paths(root: str) -> dict:
    """返回所有关键路径。"""
    concept_dir = os.path.join(root, "概念页")
    memory_dir = os.path.join(root, "memory")
    return {
        "root": root,
        "concept_dir": concept_dir,
        "memory_dir": memory_dir,
        "lite": os.path.join(memory_dir, "concept_lite.json"),
        "graph": os.path.join(memory_dir, "concept_graph.json"),
        "meta": os.path.join(memory_dir, "concept_meta.json"),
        "aliases": os.path.join(memory_dir, "name_aliases.json"),
        "relations": os.path.join(memory_dir, "concept_relations.md"),
    }


# ── 词汇表白名单 ──────────────────────────────────────────

VOCABULARY = {
    "domain": [
        "哲学", "心理学", "经济学", "社会学", "传播学",
        "管理学", "生物学", "物理学", "人类学", "政治学", "艺术",
    ],
    "discipline": [
        "伦理学", "行动哲学", "认识论", "心灵哲学", "形而上学",
        "语言哲学", "科学哲学", "政治哲学", "逻辑学", "美学",
        "中式哲学", "批判理论", "技术哲学", "存在主义", "现象学", "精神分析",
        "社会心理学", "认知心理学", "动机心理学", "发展心理学", "临床心理学",
        "行为经济学", "制度经济学", "信息经济学", "金融学",
        "社会学", "文化社会学", "组织社会学",
        "传播学",
        "组织行为学", "知识管理", "系统思维",
        "行为生物学", "演化生物学", "控制论",
        "量子物理", "热力学", "复杂系统", "统计物理",
        "流行病学",
        "认知科学",
        "国际关系",
        "视觉理论", "叙事学", "文学理论", "音乐理论",
    ],
    "pattern": [
        "悖论", "盲区", "冲突", "渐变", "反转", "循环", "错位", "缺位",
    ],
    "apply": [
        "自我", "关系", "制度", "创作", "自媒体",
        "商业", "组织", "决策", "领导", "教育",
    ],
    "source": [
        "寓言故事", "概念跳跃", "对话整理", "阅读沉淀", "圆桌讨论",
    ],
}


# ── Frontmatter 解析 ─────────────────────────────────────

def parse_frontmatter(content: str) -> Optional[dict]:
    """提取 YAML frontmatter，返回字段字典。不依赖 PyYAML。"""
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    result = {}
    for line in raw.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        colon_idx = line.find(':')
        if colon_idx < 0:
            continue
        key = line[:colon_idx].strip()
        val = line[colon_idx + 1:].strip()
        if val.startswith('[') and val.endswith(']'):
            items = re.findall(r'[^\[\],\s]+', val)
            result[key] = items
        elif val.startswith('"') or val.startswith("'"):
            result[key] = val.strip('"').strip("'")
        else:
            result[key] = val
    return result


def extract_wikilinks(content: str) -> List[str]:
    """提取所有 [[目标名]] 链接。"""
    raw = re.findall(r'\[\[([^\]]+)\]\]', content)
    targets = []
    for r in raw:
        target = re.split(r'[|#]', r)[0].strip()
        if target:
            targets.append(target)
    seen = set()
    unique = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def parse_tags(tags_value) -> dict:
    """拆分 tags 为 discipline/pattern/apply 三组。"""
    if isinstance(tags_value, str):
        tags_value = [tags_value]
    disciplines = []
    pattern = None
    applies = []
    for tag in tags_value:
        if tag.startswith("discipline/"):
            disciplines.append(tag[len("discipline/"):])
        elif tag.startswith("pattern/"):
            pattern = tag[len("pattern/"):]
        elif tag.startswith("apply/"):
            applies.append(tag[len("apply/"):])
    return {"discipline": disciplines, "pattern": pattern, "apply": applies}


def extract_english_name(name_field: str) -> Optional[str]:
    """从 '弱意志（Akrasia）' 提取英文名。"""
    m = re.search(r'（([^）]+)）', name_field)
    if m:
        return m.group(1).strip()
    m = re.search(r'\(([^)]+)\)', name_field)
    if m:
        return m.group(1).strip()
    return None


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
    name_cn = filename[:-3] if filename.endswith('.md') else filename
    if name_cn == 'INDEX':
        return None

    name_field = fm.get('name', name_cn)
    name_en = extract_english_name(name_field) if name_field else None

    domain = fm.get('domain', [])
    if isinstance(domain, str):
        domain = [domain]

    tags = parse_tags(fm.get('tags', []))
    source = fm.get('source', '')
    date = fm.get('date', '')

    persons = []
    raw_tags = fm.get('tags', [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    for tag in raw_tags:
        if tag.startswith("person/"):
            persons.append(tag[len("person/"):])

    out_links = extract_wikilinks(content)

    return {
        "file": filename,
        "name": name_field,
        "name_en": name_en,
        "domain": domain,
        "discipline": tags["discipline"],
        "pattern": tags["pattern"],
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
    for node in nodes.values():
        node["in_links"] = []
        node["in_degree"] = 0
    for name, node in nodes.items():
        for target in node["out_links"]:
            if target in nodes:
                nodes[target]["in_links"].append(name)
                nodes[target]["in_degree"] += 1


def compute_edges(nodes: dict) -> List[dict]:
    edges = []
    for name, node in nodes.items():
        for target in node["out_links"]:
            edges.append({"source": name, "target": target})
    return edges


def compute_orphans(nodes: dict) -> dict:
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
    broken = []
    for name, node in nodes.items():
        for target in node["out_links"]:
            if target not in nodes:
                broken.append({"source": name, "target": target})
    return broken


def compute_inverted_index(nodes: dict, field: str) -> Dict[str, List[str]]:
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
    for k in index:
        index[k].sort()
    return dict(sorted(index.items()))


def compute_name_en_index(nodes: dict) -> Dict[str, str]:
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
    names = sorted(nodes.keys())
    name_to_idx = {n: i for i, n in enumerate(names)}
    uf = UnionFind(len(names))

    for name, node in nodes.items():
        src_idx = name_to_idx[name]
        for target in node["out_links"]:
            if target in name_to_idx:
                tgt_idx = name_to_idx[target]
                uf.union(src_idx, tgt_idx)

    groups = defaultdict(list)
    for i, n in enumerate(names):
        root = uf.find(i)
        groups[root].append(n)

    result = [sorted(members) for members in groups.values() if len(members) >= 2]
    result.sort(key=len, reverse=True)
    return result


# ── 增量模式支持 ──────────────────────────────────────────

def get_existing_mtime(meta_path: str) -> dict:
    """读取已有的文件修改时间记录。"""
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("file_mtimes", {})


def scan_directory(concept_dir: str, incremental: bool = False,
                   existing_mtime: dict = None) -> dict:
    """扫描概念页目录，返回 {filename: node_dict}。"""
    if not os.path.isdir(concept_dir):
        print(f"错误：概念页目录不存在: {concept_dir}", file=sys.stderr)
        sys.exit(1)

    nodes = {}
    files = sorted(
        f for f in os.listdir(concept_dir)
        if f.endswith('.md') and f != 'INDEX.md'
    )

    if not files:
        print(f"目录 {concept_dir} 中没有 .md 文件（排除 INDEX.md）。")
        return nodes

    for filename in files:
        filepath = os.path.join(concept_dir, filename)

        # 增量模式：跳过未修改的文件
        if incremental and existing_mtime is not None:
            current_mtime = os.path.getmtime(filepath)
            stored_mtime = existing_mtime.get(filename)
            if stored_mtime and current_mtime == stored_mtime:
                continue

        node = scan_file(filepath)
        if node:
            nodes[node["name"]] = node

    return nodes


# ── 输出生成 ─────────────────────────────────────────────

def build_output(nodes: dict, paths: dict, incremental: bool = False) -> dict:
    """从扫描结果生成三个索引文件的内容。"""
    compute_in_links(nodes)
    edges = compute_edges(nodes)
    orphans = compute_orphans(nodes)
    broken = compute_broken_links(nodes)
    components = compute_connected_components(nodes)

    now = datetime.now(timezone.utc).isoformat()

    # ── lite ───────────────────────────────────────────
    names = sorted(nodes.keys())
    name_aliases = _load_aliases(paths["aliases"])
    name_en_idx = compute_name_en_index(nodes)

    lite = {
        "version": 2,
        "generated_at": now,
        "concept_count": len(names),
        "names": names,
        "name_aliases": name_aliases,
        "name_en_index": name_en_idx,
        "orphan_nodes": orphans,
        "apply_index": compute_inverted_index(nodes, "apply"),
        "domain_index": compute_inverted_index(nodes, "domain"),
        "nodes_lite": {
            name: {
                "domain": nodes[name]["domain"],
                "discipline": nodes[name]["discipline"],
                "pattern": nodes[name]["pattern"],
                "apply": nodes[name]["apply"],
                "source": nodes[name]["source"],
                "date": nodes[name]["date"],
            }
            for name in names
        },
    }

    # ── graph ──────────────────────────────────────────
    graph = {
        "version": 2,
        "generated_at": now,
        "node_count": len(names),
        "edge_count": len(edges),
        "broken_count": len(broken),
        "edges": edges,
        "broken_links": broken,
        "clusters": components,
        "nodes_graph": {
            name: {
                "out_links": nodes[name]["out_links"],
                "in_links": nodes[name]["in_links"],
                "out_degree": nodes[name]["out_degree"],
                "in_degree": nodes[name]["in_degree"],
            }
            for name in names
        },
    }

    # ── meta ──────────────────────────────────────────
    file_mtimes = {}
    for name, node in nodes.items():
        file_mtimes[node["file"]] = os.path.getmtime(
            os.path.join(paths["concept_dir"], node["file"])
        )

    meta = {
        "version": 2,
        "generated_at": now,
        "last_built": datetime.now().strftime("%Y-%m-%d"),
        "concept_count": len(names),
        "incremental": incremental,
        "file_mtimes": file_mtimes,
        "nodes_meta": {
            name: {
                "file": node["file"],
                "source": node["source"],
                "date": node["date"],
                "domain": node["domain"],
                "persons": node["persons"],
            }
            for name, node in nodes.items()
        },
    }

    return {"lite": lite, "graph": graph, "meta": meta}


def write_outputs(output: dict, paths: dict):
    """写入三个索引文件。"""
    memory_dir = paths["memory_dir"]
    os.makedirs(memory_dir, exist_ok=True)

    for key in ("lite", "graph", "meta"):
        path = paths[key]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output[key], f, ensure_ascii=False, indent=2)
        size = os.path.getsize(path)
        print(f"  ✅ {os.path.relpath(path, paths['root'])} ({size:,} bytes)")


def _load_aliases(aliases_path: str) -> dict:
    """加载别名映射表。不存在则返回空字典。"""
    if not os.path.exists(aliases_path):
        return {}
    with open(aliases_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── check 模式 ───────────────────────────────────────────

def run_check(paths: dict):
    """校验所有概念页的 frontmatter 合规性。"""
    concept_dir = paths["concept_dir"]
    if not os.path.isdir(concept_dir):
        print(f"错误：概念页目录不存在: {concept_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(f for f in os.listdir(concept_dir) if f.endswith('.md') and f != 'INDEX.md')
    issues = []

    for filename in files:
        filepath = os.path.join(concept_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        fm = parse_frontmatter(content)
        if not fm:
            issues.append((filename, "F00", "无法解析 frontmatter"))
            continue

        # 检查必填字段
        for field in ("name", "domain", "date", "source", "tags"):
            if field not in fm:
                issues.append((filename, f"F01", f"缺少字段: {field}"))

        # 检查禁用字段
        forbidden = ("title", "slug", "created", "related", "updated", "aliases", "name_en", "status", "discipline")
        for field in forbidden:
            if field in fm:
                issues.append((filename, "F02", f"禁用字段: {field}"))

        # 检查 domain 值
        domain = fm.get("domain", [])
        if isinstance(domain, str):
            domain = [domain]
        for d in domain:
            if d not in VOCABULARY["domain"]:
                issues.append((filename, "F03", f"非法 domain 值: {d}"))

        # 检查 source 值
        source = fm.get("source", "")
        if source and source not in VOCABULARY["source"]:
            issues.append((filename, "F04", f"非法 source 值: {source}"))

    if issues:
        print(f"\n发现 {len(issues)} 个问题：\n")
        for filename, code, msg in issues:
            print(f"  [{code}] {filename}: {msg}")
        sys.exit(1)
    else:
        count = len(files)
        print(f"\n✅ 全部 {count} 个概念页 frontmatter 校验通过。")


# ── main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="概念库索引生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 build_index.py --root /path/to/my-lib
  python3 build_index.py --root /path/to/my-lib --incremental
  python3 build_index.py --root /path/to/my-lib --check
        """,
    )
    parser.add_argument("--root", "-r", default=None,
                        help="概念库根目录绝对路径（不传则默认使用脚本上级目录）")
    parser.add_argument("--incremental", "-i", action="store_true",
                        help="增量模式：只处理修改过的文件")
    parser.add_argument("--check", "-c", action="store_true",
                        help="校验模式：检查 frontmatter 词汇表合规性")

    args = parser.parse_args()

    root = resolve_root(args.root)
    paths = get_paths(root)

    if args.check:
        run_check(paths)
        return

    incremental = args.incremental
    existing_mtime = None
    if incremental:
        existing_mtime = get_existing_mtime(paths["meta"])

    print(f"概念库根目录: {root}")
    print(f"模式: {'增量' if incremental else '全量'}")
    print()

    nodes = scan_directory(paths["concept_dir"], incremental, existing_mtime)

    if not nodes:
        print("没有需要处理的文件。")
        return

    output = build_output(nodes, paths, incremental)
    write_outputs(output, paths)

    print(f"\n完成: {len(nodes)} 个概念页 → 3 个索引文件")


if __name__ == "__main__":
    main()
