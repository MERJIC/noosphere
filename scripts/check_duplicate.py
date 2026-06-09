#!/usr/bin/env python3
"""
⚠️ 已弃用 — 概念查重工具 check_duplicate.py

功能已完全整合到 sync_db.py 中，推荐使用：
  python3 scripts/sync_db.py -d "候选概念名"          # 单个候选查重
  python3 scripts/sync_db.py --full-dup               # 全库内部查重

本文件保留仅作为轻量独立入口（交互式批量模式）。
后续版本可能移除。

---
用法（兼容旧接口，但不推荐新项目使用）：
  python3 scripts/check_duplicate.py "概念中文名"                    # 单个中文
  python3 scripts/check_duplicate.py "中文名" "English Name"        # 中英双语
  python3 scripts/check_duplicate.py --batch                       # 交互式批量（逐个输入）
  python3 scripts/check_duplicate.py --file candidates.txt         # 从文件批量读取

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

# ── 路径常量 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_ROOT = os.path.dirname(SCRIPT_DIR)
MEMORY_DIR = os.path.join(LIB_ROOT, "memory")
LITE_PATH = os.path.join(MEMORY_DIR, "concept_lite.json")

# ── 跨名映射表（同一概念的多种叫法，手动维护）─────────
# 当两个名字指向同一个学术概念但用词完全不同时在此登记
# 格式: 标准名 -> [变体列表]
CROSS_NAME_MAP = {
    "明希豪森三重困境": ["阿格里帕三难", "Agrippa's Trilemma"],
    "格雷欣法则": ["葛雷欣法则", "Gresham's Law"],
    "抛入性": ["被抛性", "Geworfenheit"],
    "多数无知": ["多元无知", "Pluralistic Ignorance"],
    "证实偏差": ["确认偏误", "Confirmation Bias"],
    "叙事认同": ["叙事同一性", "Narrative Identity"],
    "虚假记忆": ["假体记忆", "False Memory"],
}

# 反向索引：任意变体 → 标准名
_CROSS_REVERSE = {}
for canonical, variants in CROSS_NAME_MAP.items():
    for v in variants:
        _CROSS_REVERSE[v.lower()] = canonical
    _CROSS_REVERSE[canonical.lower()] = canonical

# ── 通用停用词（子串匹配时排除）───────────────────────
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


def load_index() -> dict:
    """加载 concept_lite.json。"""
    if not os.path.exists(LITE_PATH):
        print(f"错误：找不到索引文件 {LITE_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(LITE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 匹配引擎 ──────────────────────────────────────────────

class MatchResult:
    """单次查重结果。"""

    def __init__(self, name_cn: str, name_en: str = ""):
        self.name_cn = name_cn
        self.name_en = name_en
        self.hits = []       # [(策略名, 命中目标, 匹配详情), ...]
        self.verdict = None  # "可用" / "⚠ 弱命中" / "❌ 重复"

    def add_hit(self, strategy: str, target: str, detail: str):
        self.hits.append((strategy, target, detail))

    def finalize(self):
        if not self.hits:
            self.verdict = "可用"
        else:
            # 有任何强匹配就是重复，否则是弱命中
            strong = any(s in (1, 2, 3, 7) for s, _, _ in self.hits)
            self.verdict = "❌ 重复" if strong else "⚠ 弱命中"


def _check_exact_cn(name_cn: str, idx: dict, result: MatchResult):
    """策略1：中文名精确匹配。"""
    names = idx.get("names", [])
    for n in names:
        if n == name_cn:
            result.add_hit(1, n, f"中文名精确匹配: 「{n}」")


def _check_exact_en(name_en: str, idx: dict, result: MatchResult):
    """策略2：英文名精确匹配。"""
    if not name_en:
        return
    nei = idx.get("name_en_index", {})
    en_lower = name_en.lower()
    if en_lower in nei:
        result.add_hit(2, nei[en_lower], f"英文名精确匹配: '{name_en}' → 「{nei[en_lower]}」")


def _check_aliases(name_cn: str, name_en: str, idx: dict, result: MatchResult):
    """策略3：别名正反查。"""
    aliases = idx.get("name_aliases", {})

    # 正查：输入的中文名是否是某个已有概念的别名
    for alias, canonical in aliases.items():
        if name_cn in alias:
            result.add_hit(3, canonical, f"别名正查: 输入名「{name_cn}」包含于别名「{alias}」→ 正名「{canonical}」")

    # 反查：输入的英文名是否在别名里
    if name_en:
        for alias, canonical in aliases.items():
            if name_en.lower() in alias.lower():
                result.add_hit(3, canonical, f"别名反查: 英文名'{name_en}'含于别名「{alias}」→ 正名「{canonical}」")


def _check_substring_cn(name_cn: str, idx: dict, result: MatchResult):
    """策略4：中文名子串双向包含。"""
    if len(name_cn) < 3:
        return  # 太短不跑子串
    names = idx.get("names", [])
    for n in names:
        if n == name_cn:
            continue  # 精确匹配已处理
        # 双向包含检查
        if name_cn in n and len(name_cn) >= 2:
            # 排除纯通用后缀命中（如"问题"单独命中太多）
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
    """策略5：英文名词级重叠。"""
    if not name_en or len(name_en.split()) < 2:
        return
    nei = idx.get("name_en_index", {})

    # 分词（简单按空格和连字符）
    input_words = set(
        w.lower() for w in re.split(r'[\s\-]+', name_en)
        if w.lower() not in STOP_WORDS_EN and len(w) > 2
    )
    if not input_words:
        return

    for en_key, cn_name in nei.items():
        if en_key == name_en.lower():
            continue  # 精确匹配已处理
        existing_words = set(
            w.lower() for w in re.split(r'[\s\-]+', en_key)
            if w.lower() not in STOP_WORDS_EN and len(w) > 2
        )
        overlap = input_words & existing_words
        if len(overlap) >= 2:
            result.add_hit(
                5, cn_name,
                f"英文名关键词重叠({len(overlap)}词): {sorted(overlap)} "
                f"与 '{en_key}'（「{cn_name}」）共享"
            )


def _check_edit_distance(name_cn: str, idx: dict, result: MatchResult):
    """策略6：编辑距离（仅对短名称启用）。"""
    if len(name_cn) > 6:
        return  # 长名称编辑距离噪音太大
    names = idx.get("names", [])
    for n in names:
        if n == name_cn:
            continue
        if abs(len(n) - len(name_cn)) > 2:
            continue  # 长度差太大不可能接近
        dist = _levenshtein(name_cn, n)
        if dist <= 2 and dist > 0:
            ratio = SequenceMatcher(None, name_cn, n).ratio()
            if ratio >= 0.6:
                result.add_hit(6, n, f"编辑距离={dist}, 相似度={ratio:.2f}: 「{name_cn}」vs「{n}」")


def _check_cross_map(name_cn: str, name_en: str, idx: dict, result: MatchResult):
    """策略7：跨名映射表。"""
    key = name_cn.lower()
    if key in _CROSS_REVERSE:
        canonical = _CROSS_REVERSE[key]
        names = idx.get("names", [])
        if canonical in names:
            result.add_hit(
                7, canonical,
                f"跨名映射: 「{name_cn}」是「{canonical}」的已知别称"
            )
    if name_en:
        key_en = name_en.lower()
        if key_en in _CROSS_REVERSE:
            canonical = _CROSS_REVERSE[key_en]
            names = idx.get("names", [])
            if canonical in names:
                result.add_hit(
                    7, canonical,
                    f"跨名映射: '{name_en}' 是「{canonical}」的已知英文名称变体"
                )


def _levenshtein(s1: str, s2: str) -> int:
    """Levenshtein 编辑距离。"""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


# ── 主查重函数 ────────────────────────────────────────────

def check_one(name_cn: str, name_en: str = "", idx: dict = None) -> MatchResult:
    """查重单个概念，返回 MatchResult。"""
    if idx is None:
        idx = load_index()

    result = MatchResult(name_cn, name_en)

    # 按优先级执行各策略
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
    1: "精确[中文名]",
    2: "精确[英文名]",
    3: "别名",
    4: "子串",
    5: "关键词[英文]",
    6: "编辑距离",
    7: "跨名映射",
}

VERDICT_COLORS = {
    "可用": "\033[32m",      # 绿
    "⚠ 弱命中": "\033[33m",   # 黄
    "❌ 重复": "\033[31m",     # 红
}
RESET = "\033[0m"


def format_result(result: MatchResult, verbose: bool = True) -> str:
    """格式化单条结果为可读字符串。"""
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


# ── 批量模式 ──────────────────────────────────────────────

def run_batch(idx: dict):
    """交互式批量模式，逐个输入直到空行退出。"""
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

    # 汇总
    if results:
        ok = sum(1 for r in results if r.verdict == "可用")
        weak = sum(1 for r in results if r.verdict == "⚠ 弱命中")
        dup = sum(1 for r in results if r.verdict == "❌ 重复")
        print(f"\n汇总: {len(results)} 条 | {VERDICT_COLORS['可用']}可用 {ok}{RESET}"
              f" | {VERDICT_COLORS['⚠ 弱命中']}弱命中 {weak}{RESET}"
              f" | {VERDICT_COLORS['❌ 重复']}重复 {dup}{RESET}")


def run_file(filepath: str, idx: dict):
    """从文件读取候选列表并批量查重。

    文件格式：每行「中文名 英文名」，英文名可选，# 开头为注释。
    """
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


# ── main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="概念库查重工具 — 检测候选概念是否已存在于库中",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 scripts/check_duplicate.py "证言问题" "Problem of Testimony"
  python3 scripts/check_duplicate.py "阿格里帕三难" "Agrippa's Trilemma"
  python3 scripts/check_duplicate.py --batch
  python3 scripts/check_duplicate.py --file candidates.txt
  python3 scripts/check_duplicate.py "道德运气" --verbose
        """,
    )
    parser.add_argument("name_cn", nargs="?", help="概念中文名")
    parser.add_argument("name_en", nargs="?", default="", help="英文名（可选）")
    parser.add_argument("--batch", "-b", action="store_true", help="交互式批量模式")
    parser.add_argument("--file", "-f", help="从文件读取候选列表")
    parser.add_argument("--verbose", "-v", action="store_true",
                        default=True, help="详细输出匹配路径（默认开启）")
    parser.add_argument("--brief", action="store_true",
                        help="简洁模式，只显示结论不展开匹配路径")

    args = parser.parse_args()

    if args.brief:
        args.verbose = False

    idx = load_index()

    if args.batch:
        run_batch(idx)
    elif args.file:
        run_file(args.file, idx)
    elif args.name_cn:
        result = check_one(args.name_cn, args.name_en, idx)
        print(format_result(result, verbose=args.verbose))

        # 兼容旧接口：脚本方式调用时额外输出纯文本 verdict
        # 供 parable.md 等 module 内嵌调用获取布尔结果
        if not sys.stdout.isatty():
            print(f"\n__VERDICT__: {result.verdict}", file=sys.stderr)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
