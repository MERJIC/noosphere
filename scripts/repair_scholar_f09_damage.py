#!/usr/bin/env python3
"""
修复 F09 --fix 误伤：星巴克→星罗杰·巴克、胡塞尔→胡约翰·塞尔、双层括号等。

用法：
  python3 scripts/repair_scholar_f09_damage.py           # 预览
  python3 scripts/repair_scholar_f09_damage.py --apply   # 写回
  python3 scripts/repair_scholar_f09_damage.py --file 身份消费 --apply
"""
from __future__ import annotations

import argparse
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_ROOT = os.path.dirname(SCRIPT_DIR)
CONCEPT_DIR = os.path.join(LIB_ROOT, "概念页")

sys.path.insert(0, SCRIPT_DIR)
from scholar_annotation_utils import (  # noqa: E402
    EXACT_DAMAGE_REPLACEMENTS,
    repair_known_damage,
    strip_redundant_surname_parens,
)

SCAN_PATTERNS = [
    ("星罗杰·巴克", "星巴克误替换"),
    ("胡约翰·塞尔", "胡塞尔被塞尔短名误伤"),
    ("理查德·罗尔（Richard Roll）", "罗尔斯误替换"),
    ("卡理查德·罗尔", "卡罗尔误替换"),
    (r"（[A-Za-z][^）]{2,60}）（[A-Za-z][^）]{1,40}）", "双层英文括号"),
]


def scan_file(path: str) -> list[str]:
    text = open(path, encoding="utf-8").read()
    hits = []
    for pat, label in SCAN_PATTERNS:
        if pat.startswith("("):
            if re.search(pat, text):
                hits.append(label)
        elif pat in text:
            hits.append(label)
    return hits


def repair_file(path: str, apply: bool) -> dict:
    with open(path, encoding="utf-8") as f:
        original = f.read()
    repaired, n_exact = repair_known_damage(original)
    changed = repaired != original
    if apply and changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(repaired)
    return {
        "path": path,
        "changed": changed,
        "exact_hits": n_exact,
        "signals": scan_file(path) if changed else scan_file(path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写回文件")
    ap.add_argument("--file", help="只处理单个概念 stem")
    args = ap.parse_args()

    if args.file:
        paths = [os.path.join(CONCEPT_DIR, f"{args.file}.md")]
    else:
        paths = sorted(
            os.path.join(CONCEPT_DIR, f)
            for f in os.listdir(CONCEPT_DIR)
            if f.endswith(".md") and f != "INDEX.md"
        )

    changed_files = []
    for path in paths:
        if not os.path.isfile(path):
            print(f"跳过（不存在）: {path}")
            continue
        r = repair_file(path, args.apply)
        if r["changed"]:
            stem = os.path.basename(path)[:-3]
            changed_files.append(stem)
            print(f"{'✓' if args.apply else '△'} {stem}: {', '.join(r['signals']) or '冗余括号清理'}")

    print(f"\n{'已修复' if args.apply else '将修复'} {len(changed_files)} 个文件")
    if not args.apply and changed_files:
        print("加上 --apply 写回。")
    print(f"\n已知硬编码替换规则: {len(EXACT_DAMAGE_REPLACEMENTS)} 条")


if __name__ == "__main__":
    main()