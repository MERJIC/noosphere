#!/usr/bin/env python3
"""
概念查重工具 — check_duplicate.py（concept-studio-spread 版）

用法：
  python3 check_duplicate.py --root /path/to/lib "概念中文名"
  python3 check_duplicate.py --root /path/to/lib "中文名" "English Name"
  python3 check_duplicate.py --root /path/to/lib --batch
  python3 check_duplicate.py --root /path/to/lib --file candidates.txt

  # 不传 --root 时默认使用脚本所在目录的上级作为概念库根目录
  python3 check_duplicate.py "概念中文名"

输出：
  可用 → 绿色，无任何命中
  ⚠ 命中 → 黄色，弱匹配（子串/关键词重叠），需人工判断
  ❌ 重复 → 红色，强匹配（精确/别名/同概念变体），确认重复

匹配策略（按优先级从高到低）：
  1. 中文名精确匹配 names[]
  2. 英文名精确匹配 name_en_index{}
  3. 别名正/反查 name_aliases{}
  4. 中文名子串双向包含（≥2字且非单字通用词）
  5. 英文名词级重叠（共享关键词 ≥2 个）
  6. 中文名编辑距离（≤2 且长度 ≤6 时触发）
  7. 已知跨名映射表（手动维护的「同一概念不同叫法」）
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher


def resolve_root(args_root: str = None) -> str:
    """解析概念库根目录路径。"""
    if args_root:
        return args_root
    # 默认：脚本所在目录的上级目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def get_lite_path(root: str) -> str:
    return os.path.join(root, "memory", "concept_lite.json")


# ── 跨名映射表（同一概念的多种叫法，手动维护）─────────
CROSS_NAME_MAP = {
    "明希豪森三重困境": ["阿格里帕三难", "Agrippa's Trilemma"],
    "格雷欣法则": ["葛雷欣法则", "Gresham's Law"],
    "抛入性": ["被抛性", "Geworfenheit"],
    "多数无知": ["多元无知", "Pluralistic Ignorance"],
    "证实偏差": ["确认偏误", "Confirmation Bias"],
    "叙事认同": ["叙事同一性", "Narrative Identity"],
    "虚假记忆": ["假体记忆", "False Memory"],
}

_CROSS_REVERSE = {}
for canonical, variants in CROSS_NAME_MAP.items():
    for v in variants:
        _CROSS_REVERSE[v.lower()] = canonical
    _CROSS_REVERSE[canonical.lower()] = canonical

# ── 通用停用词 ────────────────────────────────────────────
STOP_WORDS_CN = set(
    "的 了 在 是 有 和 与 或 对 关于 以及 及 其 中 之 以 于 而 但"
    " 且 如 若 虽然 即使 因为 所以 如果 那么 这 那 哪 什么 怎么"
    " 一个 一种 一样 一些 一般 问题 效应 原理 定律 理论 悖论 现象"
    " 效果 方法 机制 模型 假设 概念 偏误 偏差 错觉 幻觉 困境 难题"
    "".split()
)

STOP_WORDS_EN = set(
    "the of and a an in is are was were it its to for with on at"
    " by from as or not no if then but so about into through over"
    " under between effect theory problem paradox principle law model"
    " hypothesis phenomenon bias fallacy illusion mechanism method"
    "".split())


def load_index(lite_path: str) -> dict:
    """加载 concept_lite.json。"""
    if not os.path.exists(lite_path):
        print(f"错误：找不到索引文件 {lite_path}", file=sys.stderr)
        print(f"提示：请先运行 build_index.py --root {os.path.dirname(os.path.dirname(lite_path))} 初始化索引", file=sys.stderr)
        sys.exit(1)
    with open(lite_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 匹配引擎 ──────────────────────────────────────────────

class MatchResult:
    def __init__(self, name_cn: str, name_en: str = ""):
        self.name_cn = name_cn
        self.name_en = name_en
        self.hits = []
        self.verdict = None

    def add_hit(self, strategy: str, target: str, detail: str):
        self.hits.append((strategy, target, detail))

    def finalize(self):
        if not self.hits:
            self.verdict = "可用"
        else:
            strong = any(s in (1, 2, 3, 7) for s, _, _ in self.hits)
            self.verdict = "❌ 重复" if strong else "⚠ 弱命中"


def _check_exact_cn(name_cn: str, idx: dict, result: MatchResult):
    names = idx.get("names", [])
    for n in names:
        if n == name_cn:
            result.add_hit(1, n, f"中文名精确匹配: 「{n}」")


def _check_exact_en(name_en: str, idx: dict, result: MatchResult):
    if not name_en:
        return
    nei = idx.get("name_en_index", {})
    en_lower = name_en.lower()
    if en_lower in nei:
        result.add_hit(2, nei[en_lower], f"英文名精确匹配: '{name_en}' → 「{nei[en_lower]}」")


def _check_aliases(name_cn: str, name_en: str, idx: dict, result: MatchResult):
    aliases = idx.get("name_aliases", {})
    for alias, canonical in aliases.items():
        if name_cn in alias:
            result.add_hit(3, canonical, f"别名正查: 输入名「{name_cn}」包含于别名「{alias}」→ 正名「{canonical}」")
    if name_en:
        for alias, canonical in aliases.items():
            if name_en.lower() in alias.lower():
                result.add_hit(3, canonical, f"别名反查: 英文名'{name_en}'含于别名「{alias}」→ 正名「{canonical}」")


def _check_substring_cn(name_cn: str, idx: dict, result: MatchResult):
    if len(name_cn) < 3:
        return
    names = idx.get("names", [])
    for n in names:
        if n == name_cn:
            continue
        if name_cn in n and len(name_cn) >= 2:
            overlap = name_cn
            if overlap in STOP_WORDS_CN or len(overlap) < 2:
                continue
            result.add_hit(4, n, f"子串包含: 「{name_cn}」⊂「{n}」")
        elif n in name_cn and len(n) >= 2:
            overlap = n
            if overlap in STOP_WORDS_CN or len(overlap) < 2:
                continue
            result.add_hit(4, n, f"子串包含: 「{n}」⊂「{name_cn}」")


def _check_keyword_en(name_en: str, idx: dict, result: MatchResult):
    if not name_en or len(name_en.split()) < 2:
        return
    nei = idx.get("name_en_index", {})
    input_words = set(
        w.lower() for w in re.split(r'[\s\-]+', name_en)
        if w.lower() not in STOP_WORDS_EN and len(w) > 2
    )
    if not input_words:
        return
    for en_key, cn_name in nei.items():
        if en_key == name_en.lower():
            continue
        existing_words = set(
            w.lower() for w in re.split(r'[\s\-]+', en_key)
            if w.lower() not in STOP_WORDS_EN and len(w) > 2
        )
        overlap = input_words & existing_words
        if len(overlap) >= 2:
            result.add_hit(
                5, cn_name,
                f"英文名关键词重叠({len(overlap)}词): {sorted(overlap)} "
                f"与 '{en_key}'（「{cn_name}」）共享",
            )


def _check_edit_distance(name_cn: str, idx: dict, result: MatchResult):
    if len(name_cn) > 6:
        return
    names = idx.get("names", [])
    for n in names:
        if n == name_cn:
            continue
        if abs(len(n) - len(name_cn)) > 2:
            continue
        dist = _levenshtein(name_cn, n)
        if dist <= 2 and dist > 0:
            ratio = SequenceMatcher(None, name_cn, n).ratio()
            if ratio >= 0.6:
                result.add_hit(6, n, f"编辑距离={dist}, 相似度={ratio:.2f}: 「{name_cn}」vs「{n}」")


def _check_cross_map(name_cn: str, name_en: str, idx: dict, result: MatchResult):
    key = name_cn.lower()
    if key in _CROSS_REVERSE:
        canonical = _CROSS_REVERSE[key]
        names = idx.get("names", [])
        if canonical in names:
            result.add_hit(7, canonical, f"跨名映射: 「{name_cn}」是「{canonical}」的已知别称")
    if name_en:
        key_en = name_en.lower()
        if key_en in _CROSS_REVERSE:
            canonical = _CROSS_REVERSE[key_en]
            names = idx.get("names", [])
            if canonical in names:
                result.add_hit(7, canonical, f"跨名映射: '{name_en}' 是「{canonical}」的已知英文名称变体")


def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + j + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def check_one(name_cn: str, name_en: str = "", idx: dict = None, lite_path: str = None) -> MatchResult:
    if idx is None:
        idx = load_index(lite_path or get_lite_path(resolve_root()))
    result = MatchResult(name_cn, name_en)
    _check_exact_cn(name_cn, idx, result)
    _check_exact_en(name_en, idx, result)
    _check_aliases(name_cn, name_en, idx, result)
    _check_substring_cn(name_cn, idx, result)
    _check_keyword_en(name_en, idx, result)
    _check_edit_distance(name_cn, idx, result)
    _check_cross_map(name_cn, name_en, idx, result)
    result.finalize()
    return result


# ── 格式化输出 ────────────────────────────────────────────

STRATEGY_LABELS = {
    1: "精确[中文名]", 2: "精确[英文名]", 3: "别名",
    4: "子串", 5: "关键词[英文]", 6: "编辑距离", 7: "跨名映射",
}
VERDICT_COLORS = {"可用": "\033[32m", "⚠ 弱命中": "\033[33m", "❌ 重复": "\033[31m"}
RESET = "\033[0m"


def format_result(result: MatchResult, verbose: bool = True) -> str:
    color = VERDICT_COLORS.get(result.verdict, "")
    lines = [f"{color}{result.verdict}{RESET}  「{result.name_cn}」"
             f"{f' ({result.name_en})' if result.name_en else ''}"]
    if verbose and result.hits:
        for strategy, target, detail in result.hits:
            label = STRATEGY_LABELS.get(strategy, f"策略{strategy}")
            lines.append(f"    [{label}] {detail}")
    elif not verbose and result.hits:
        targets = sorted(set(t for _, t, _ in result.hits))
        lines[0] += f"  → 命中: {', '.join('「' + t + '」' for t in targets)}"
    return "\n".join(lines)


def run_batch(idx: dict):
    print("批量查重模式（每行输入: 中文名 [英文名]，空行结束）\n")
    results = []
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        parts = line.split(maxsplit=1)
        cn = parts[0]
        en = parts[1].strip('"').strip("'") if len(parts) > 1 else ""
        r = check_one(cn, en, idx)
        results.append(r)
        print(format_result(r))
        print()
    if results:
        ok = sum(1 for r in results if r.verdict == "可用")
        weak = sum(1 for r in results if r.verdict == "⚠ 弱命中")
        dup = sum(1 for r in results if r.verdict == "❌ 重复")
        print(f"\n汇总: {len(results)} 条 | {VERDICT_COLORS['可用']}可用 {ok}{RESET}"
              f" | {VERDICT_COLORS['⚠ 弱命中']}弱命中 {weak}{RESET}"
              f" | {VERDICT_COLORS['❌ 重复']}重复 {dup}{RESET}")


def run_file(filepath: str, idx: dict):
    with open(filepath, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()
    entries = []
    for line_no, raw in enumerate(raw_lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        cn = parts[0]
        en = parts[1].strip('"').strip("'") if len(parts) > 1 else ""
        entries.append((line_no, cn, en))
    if not entries:
        print("文件中没有有效条目。")
        return
    print(f"从文件读取 {len(entries)} 条候选\n")
    all_ok = True
    for line_no, cn, en in entries:
        r = check_one(cn, en, idx)
        status = format_result(r, verbose=False)
        print(f"  L{line_no:3d} {status}")
        if r.verdict != "可用":
            all_ok = False
    if all_ok:
        print(f"\n{VERDICT_COLORS['可用']}全部可用，无重复{RESET}")
    else:
        print(f"\n存在命中项，建议加 --verbose 查看详情")


def main():
    parser = argparse.ArgumentParser(
        description="概念库查重工具 — 检测候选概念是否已存在于库中",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 check_duplicate.py --root /path/to/lib "证言问题" "Problem of Testimony"
  python3 check_duplicate.py --root /path/to/lib --batch
  python3 check_duplicate.py --root /path/to/lib --file candidates.txt
        """,
    )
    parser.add_argument("--root", "-r", default=None,
                        help="概念库根目录绝对路径（不传则默认使用脚本上级目录）")
    parser.add_argument("name_cn", nargs="?", help="概念中文名")
    parser.add_argument("name_en", nargs="?", default="", help="英文名（可选）")
    parser.add_argument("--batch", "-b", action="store_true", help="交互式批量模式")
    parser.add_argument("--file", "-f", help="从文件读取候选列表")
    parser.add_argument("--verbose", "-v", action="store_true", default=True,
                        help="详细输出匹配路径（默认开启）")
    parser.add_argument("--brief", action="store_true", help="简洁模式")

    args = parser.parse_args()

    if args.brief:
        args.verbose = False

    root = resolve_root(args.root)
    lite_path = get_lite_path(root)
    idx = load_index(lite_path)

    if args.batch:
        run_batch(idx)
    elif args.file:
        run_file(args.file, idx)
    elif args.name_cn:
        result = check_one(args.name_cn, args.name_en, idx, lite_path)
        print(format_result(result, verbose=args.verbose))
        if not sys.stdout.isatty():
            print(f"\n__VERDICT__: {result.verdict}", file=sys.stderr)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
