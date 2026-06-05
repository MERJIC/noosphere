#!/usr/bin/env python3
"""Shared helpers for scholar name lint / repair (F09)."""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Set, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_ROOT = os.path.dirname(SCRIPT_DIR)
SCHOLAR_DICT_PATH = os.path.join(
    LIB_ROOT, "skills/concept-studio/modules/scholar-dict.json"
)

# 非学者专有短语：短名不得在其中做子串替换
PROTECTED_PHRASES = [
    "星巴克",
    "巴克莱",
    "福克斯",
    "扎克伯格",
    "马尔克斯",
    "帕克斯",
    "尼克斯",
    "明斯基",
]

# 已知 --fix 误伤（最长优先）
EXACT_DAMAGE_REPLACEMENTS: List[Tuple[str, str]] = [
    (
        "埃德蒙·胡约翰·塞尔（John Searle）（Edmund Husserl）（Husserl）",
        "埃德蒙·胡塞尔（Edmund Husserl）",
    ),
    (
        "埃德蒙·胡约翰·塞尔（John Searle）（Edmund Husserl）",
        "埃德蒙·胡塞尔（Edmund Husserl）",
    ),
    ("星罗杰·巴克（Roger Barker）", "星巴克"),
    (
        "尤尔根·哈贝马斯（Jürgen Habermas）（Habermas）和约翰·理查德·罗尔（Richard Roll）斯（John Rawls）（Rawls）",
        "尤尔根·哈贝马斯（Jürgen Habermas）和约翰·罗尔斯（John Rawls）",
    ),
    (
        "理查德·罗尔（Richard Roll）斯（Rawls）",
        "约翰·罗尔斯（John Rawls）",
    ),
    (
        "诺埃尔·卡理查德·罗尔（Richard Roll）（Noël Carroll）",
        "诺埃尔·卡罗尔（Noël Carroll）",
    ),
    ("罗杰·巴克（Roger Barker）（Per Bak）", "珀·巴克（Per Bak）"),
    ("（森（Sen））", "（阿马蒂亚·森（Amartya Sen））"),
    ("（森（Sen）", "（阿马蒂亚·森（Amartya Sen）"),
]

REDUNDANT_SUFFIX = re.compile(
    r"([\u4e00-\u9fff·A-Za-z\s\-]+?)（([^）]+)）（([A-Za-z][A-Za-z.\-\s']*)）"
)


def load_scholar_dict() -> dict:
    if not os.path.exists(SCHOLAR_DICT_PATH):
        return {}
    with open(SCHOLAR_DICT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_short_unsafe(scholar_dict: dict) -> Set[str]:
    """短名若出现在任一学者全名的真子串中，禁止短名自动替换。"""
    unsafe: Set[str] = set()
    full_names = [info["full"] for info in scholar_dict.values()]
    for info in scholar_dict.values():
        short = info.get("short", info["full"])
        full = info["full"]
        if not short or short == full or len(short) <= 1:
            continue
        for other in full_names:
            if short in other and short != other:
                unsafe.add(short)
                break
    return unsafe


def strip_redundant_surname_parens(text: str) -> str:
    """皮埃尔·布迪厄（Pierre Bourdieu）（Bourdieu） → 皮埃尔·布迪厄（Pierre Bourdieu）"""

    def _repl(m: re.Match) -> str:
        prefix, en_main, en_extra = m.group(1), m.group(2).strip(), m.group(3).strip()
        if not en_main or not en_extra:
            return m.group(0)
        tokens = en_main.split()
        last = tokens[-1] if tokens else ""
        if en_extra == last:
            return f"{prefix}（{en_main}）"
        if en_main.endswith(" " + en_extra) or en_main.endswith(en_extra):
            return f"{prefix}（{en_main}）"
        # 扩展名重复：Theodor Adorno）（Theodor W. Adorno）
        if en_extra.startswith(en_main) or en_main in en_extra:
            return f"{prefix}（{en_main}）"
        return m.group(0)

    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur = REDUNDANT_SUFFIX.sub(_repl, cur)
    return cur


def repair_known_damage(text: str) -> Tuple[str, int]:
    n = 0
    for old, new in EXACT_DAMAGE_REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            n += 1
    text2 = strip_redundant_surname_parens(text)
    if text2 != text:
        n += 1
        text = text2
    return text, n


def short_match_is_safe(
    body: str,
    start: int,
    end: int,
    short_name: str,
    full_name: str,
    scholar_dict: dict,
    short_unsafe: Set[str],
) -> bool:
    if short_name in short_unsafe:
        return False
    for phrase in PROTECTED_PHRASES:
        for pm in re.finditer(re.escape(phrase), body):
            if pm.start() <= start < pm.end():
                return False
    for info in scholar_dict.values():
        ofull = info["full"]
        for om in re.finditer(re.escape(ofull), body):
            if om.start() <= start < om.end():
                return False
    if end < len(body) and body[end] == "（":
        return False
    if start > 0 and body[start - 1] == "（":
        return False
    return True


def find_safe_short_positions(
    body: str, short_name: str, full_name: str, scholar_dict: dict, short_unsafe: Set[str]
) -> List[int]:
    positions = []
    for m in re.finditer(re.escape(short_name), body):
        if short_match_is_safe(
            body, m.start(), m.end(), short_name, full_name, scholar_dict, short_unsafe
        ):
            positions.append(m.start())
    return positions