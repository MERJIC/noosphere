#!/usr/bin/env python3
"""
Scholar Tagger - 保守的学者人名标注工具
只在“核心机制”部分寻找“提出/系统讨论”类表述
"""

import os
import re
import sys
from typing import Dict, List, Set

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_ROOT = os.path.dirname(SCRIPT_DIR)
CONCEPT_DIR = os.path.join(LIB_ROOT, "概念页")

# 尝试导入工具
try:
    sys.path.append(SCRIPT_DIR)
    from scholar_annotation_utils import load_scholar_dict, build_short_unsafe
except ImportError:
    if __name__ == "__main__":
        print("无法导入 scholar_annotation_utils.py")
        sys.exit(1)
    raise

CONSERVATIVE_KEYWORDS = [
    "提出", "系统提出", "系统讨论", "系统阐述", "核心贡献", "认为……是",
    "其核心在于", "奠定了", "开创了", "发展了", "系统化",
    "关键在于", "本质是", "标志着", "代表了",
]

def parse_frontmatter(content: str):
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
            items = re.findall(r"[^[\],\s]+", val)
            result[key] = items
        else:
            result[key] = val
    return result

def extract_core_mechanism(content: str) -> str:
    match = re.search(r"##\s*核心机制\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""

def find_conservative_scholars(core_text: str, scholar_dict: dict, short_unsafe: Set[str]) -> List[str]:
    if not scholar_dict:
        return []
    found = []
    for dict_key, info in scholar_dict.items():
        full_name = info.get("full", dict_key)
        short = info.get("short", full_name)
        context_window = 80
        matched = False

        for m in re.finditer(re.escape(full_name), core_text):
            start = max(0, m.start() - context_window)
            end = min(len(core_text), m.end() + context_window)
            window = core_text[start:end]
            if any(kw in window for kw in CONSERVATIVE_KEYWORDS):
                matched = True
                break

        if not matched and short not in short_unsafe:
            for m in re.finditer(re.escape(short), core_text):
                start = max(0, m.start() - context_window)
                end = min(len(core_text), m.end() + context_window)
                window = core_text[start:end]
                if any(kw in window for kw in CONSERVATIVE_KEYWORDS):
                    matched = True
                    break

        if matched and short not in found:
            found.append(short)
    return found

def annotate_file(filepath: str, scholar_dict: dict, short_unsafe: Set[str]) -> bool:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(content)
    if not fm or "tags" not in fm:
        return False

    core = extract_core_mechanism(content)
    if not core:
        return False

    scholars = find_conservative_scholars(core, scholar_dict, short_unsafe)
    if not scholars:
        return False

    tags = [str(tag).strip().strip('"').strip("'") for tag in fm.get("tags", [])]

    current = set()
    for tag in tags:
        if tag.startswith("person/"):
            current.add(tag[len("person/"):])

    new_ones = [s for s in scholars if s not in current]
    if not new_ones:
        return False

    new_tags = [t for t in tags if not t.startswith("person/")]
    for p in sorted(set(list(current) + new_ones)):
        new_tags.append(f"person/{p}")

    new_content = re.sub(
        r"^tags:\s*\[[^\]]*\]\s*$",
        "tags: [" + ", ".join(new_tags) + "]",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True

def main():
    scholar_dict = load_scholar_dict()
    if not scholar_dict:
        print("scholar-dict.json 为空或不存在")
        return

    short_unsafe = build_short_unsafe(scholar_dict)

    print(f"Loaded {len(scholar_dict)} scholars")
    print("开始保守标注...")

    count = 0
    for fname in os.listdir(CONCEPT_DIR):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        path = os.path.join(CONCEPT_DIR, fname)
        if annotate_file(path, scholar_dict, short_unsafe):
            count += 1
            print(f"  已标注: {fname}")

    print(f"\n完成，共标注 {count} 个概念页")

if __name__ == "__main__":
    main()
