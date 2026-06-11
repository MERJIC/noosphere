#!/usr/bin/env python3
"""
概念库脚本公共模块 — _common.py

所有 scripts/ 下脚本的共享基础设施：
  - 路径常量
  - frontmatter 解析（唯一权威实现）
  - 词汇表白名单（单一数据源）
  - wikilink / 英文名提取
  - tags 分组解析
  - concept_relations.md 集群解析

设计原则：
  - 本模块不 import 同目录下其他脚本，避免循环依赖
  - 不包含业务逻辑（查重/lint/sync 各自管各自的）
  - scholar 相关工具在 scholar_annotation_utils.py 中
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

# ══════════════════════════════════════════════════════════
#  路径常量
# ══════════════════════════════════════════════════════════

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_ROOT = os.path.dirname(SCRIPT_DIR)
CONCEPT_DIR = os.path.join(LIB_ROOT, "概念页")
MEMORY_DIR = os.path.join(LIB_ROOT, "memory")

# 输出文件路径
DB_PATH = os.path.join(MEMORY_DIR, "concepts.db")
LITE_PATH = os.path.join(MEMORY_DIR, "concept_lite.json")
GRAPH_PATH = os.path.join(MEMORY_DIR, "concept_graph.json")
META_PATH = os.path.join(MEMORY_DIR, "concept_meta.json")
ALIASES_PATH = os.path.join(MEMORY_DIR, "name_aliases.json")
RELATIONS_PATH = os.path.join(MEMORY_DIR, "concept_relations.md")
# scholar-dict.json 路径：优先查找 skills/concept-studio-spread/modules/（传播版），
# 回退到 skills/concept-studio/modules/（原版），再回退到 modules/（skill 自身目录）
_skill_modules_canditates = [
    os.path.join(LIB_ROOT, "skills/concept-studio-spread/modules/scholar-dict.json"),
    os.path.join(LIB_ROOT, "skills/concept-studio/modules/scholar-dict.json"),
    os.path.join(SCRIPT_DIR, "..", "modules", "scholar-dict.json"),
]
SCHOLAR_DICT_PATH = next((p for p in _skill_modules_canditates if os.path.exists(p)), _skill_modules_canditates[-1])

# ══════════════════════════════════════════════════════════
#  词汇表白名单（单一数据源）
#  page-spec.md 是规范文档供人读；本文件是机器可读的权威副本。
#  两者必须保持同步。新增词汇时两边都要改。
# ══════════════════════════════════════════════════════════

DOMAIN_WHITELIST = [
    "哲学", "心理学", "经济学", "社会学", "传播学",
    "管理学", "生物学", "物理学", "人类学", "政治学", "艺术",
]

DISCIPLINE_WHITELIST = [
    # 哲学
    "伦理学", "行动哲学", "认识论", "心灵哲学", "形而上学",
    "语言哲学", "科学哲学", "政治哲学", "逻辑学", "美学",
    "中式哲学", "批判理论", "技术哲学", "存在主义", "现象学", "精神分析",
    # 心理学
    "社会心理学", "认知心理学", "动机心理学", "发展心理学", "临床心理学",
    "人格心理学", "教育心理学",
    # 经济学
    "行为经济学", "制度经济学", "信息经济学", "金融学",
    # 社会学
    "社会学", "文化社会学", "组织社会学", "流行病学",
    # 传播学
    "传播学",
    # 管理学
    "组织行为学", "知识管理", "系统思维",
    # 生物学
    "行为生物学", "演化生物学", "控制论",
    # 物理学
    "量子物理", "热力学", "复杂系统", "统计物理",
    # 认知科学（跨域）
    "认知科学",
    # 政治学
    "政治哲学", "国际关系",
    # 艺术
    "视觉理论", "叙事学", "文学理论", "音乐理论",
]

APPLY_WHITELIST = [
    "自我", "关系", "制度", "创作", "自媒体",
    "商业", "组织", "决策", "领导", "教育",
]

SOURCE_WHITELIST = [
    "寓言故事", "概念跳跃", "对话整理", "阅读沉淀", "圆桌讨论",
]

# 词汇表合集（方便整体引用）
VOCABULARY = {
    "domain": DOMAIN_WHITELIST,
    "discipline": DISCIPLINE_WHITELIST,
    "apply": APPLY_WHITELIST,
    "source": SOURCE_WHITELIST,
}

# ══════════════════════════════════════════════════════════
#  Frontmatter 解析（唯一权威实现）
# ══════════════════════════════════════════════════════════

def parse_frontmatter(content: str) -> Optional[dict]:
    """提取 YAML frontmatter，返回字段字典。不依赖 PyYAML。

    返回示例：
      {"name": "弱意志（Akrasia）", "domain": ["哲学"], "tags": [...], ...}
    数组值（如 tags/domain）返回 list[str]；
    标量值返回 str。
    """
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


# ══════════════════════════════════════════════════════════
#  字段提取辅助函数
# ══════════════════════════════════════════════════════════

def extract_english_name(name_field: str) -> Optional[str]:
    """从 '弱意志（Akrasia）' 提取英文名。全角括号优先。"""
    m = re.search(r"（([^）]+)）", name_field)
    if m:
        return m.group(1).strip()
    m = re.search(r"\(([^)]+)\)", name_field)
    if m:
        return m.group(1).strip()
    return None


def extract_wikilinks(content: str) -> List[str]:
    """提取所有 [[目标名]] 链接，去重保序。

    处理 [[名|显示文本]] 和 [[名#章节]] 变体，
    只返回纯净的目标概念名。
    """
    raw = re.findall(r"\[\[([^\]]+)\]\]", content)
    targets = []
    seen = set()
    for r in raw:
        target = re.split(r"[|#]", r)[0].strip()
        if target and target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


def parse_tags(tags_value) -> dict:
    """拆分 tags 数组为 discipline / apply / person 三组。

    参数可以是 list[str] 或 str（单值退化）。
    返回 {"discipline": [...], "apply": [...], "persons": [...]}
    """
    if isinstance(tags_value, str):
        tags_value = [tags_value]

    disciplines = []
    applies = []
    persons = []

    for tag in tags_value:
        if tag.startswith("discipline/"):
            disciplines.append(tag[len("discipline/"):])
        elif tag.startswith("apply/"):
            applies.append(tag[len("apply/"):])
        elif tag.startswith("person/"):
            persons.append(tag[len("person/"):])

    return {"discipline": disciplines, "apply": applies, "persons": persons}


# ══════════════════════════════════════════════════════════
#  concept_relations.md 集群解析（唯一权威实现）
# ══════════════════════════════════════════════════════════

def parse_relations_clusters(content: str) -> List[dict]:
    """解析 concept_relations.md 中的集群定义。

    返回 [{"id": "A", "name": "...", "description": "...", "members": [...]}, ...]
    """
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
        header_match = re.match(
            r"###\s+([A-Z])\s*[·•]\s*(.+?)(?:\s*✅)?\s*$", line
        )
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
#  文件扫描辅助
# ══════════════════════════════════════════════════════════

def iter_concept_files():
    """迭代概念页目录下所有 .md 文件（排除 INDEX.md）。

    Yields: (filename_without_ext, full_filepath)
    """
    if not os.path.isdir(CONCEPT_DIR):
        return
    for fname in sorted(os.listdir(CONCEPT_DIR)):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        fpath = os.path.join(CONCEPT_DIR, fname)
        if os.path.isfile(fpath):
            yield fname[:-3], fpath


def load_scholar_dict() -> dict:
    """加载学者对照表。"""
    if not os.path.exists(SCHOLAR_DICT_PATH):
        return {}
    with open(SCHOLAR_DICT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: str, data: dict, compact: bool = False) -> None:
    """原子写入 JSON 文件（先写 .tmp 再 rename）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
