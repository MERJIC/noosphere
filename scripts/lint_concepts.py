#!/usr/bin/env python3
"""
概念库全量格式质检 — lint_concepts.py

对照 page-spec.md 自检清单，逐项检查所有概念页。
输出按规则分组的报告，标注可自动修复项。

用法：
  python3 scripts/lint_concepts.py              全量质检（报告）
  python3 scripts/lint_concepts.py --fix        全量质检 + 自动修复可修复项
  python3 scripts/lint_concepts.py --file 概念名 只检查单个文件
  python3 scripts/lint_concepts.py --fix --file 概念名  单文件修复
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional

# 公共模块：路径常量、frontmatter 解析、词汇表（单一数据源）
from _common import (
    CONCEPT_DIR,
    SCHOLAR_DICT_PATH,
    VOCABULARY,
    DOMAIN_WHITELIST,
    DISCIPLINE_WHITELIST,
    APPLY_WHITELIST,
    SOURCE_WHITELIST,
    parse_frontmatter,
)

# F09 学者短名自动替换默认关闭（见 --fix-scholars）；工具函数见 scholar_annotation_utils.py
from scholar_annotation_utils import (  # noqa: E402
    build_short_unsafe,
    find_safe_short_positions,
    load_scholar_dict as _load_scholar_dict_util,
    short_match_is_safe,
)

# ── lint 专用常量（不在公共模块中） ────────────────────────
FORBIDDEN_FIELDS = {
    "title", "slug", "created", "related", "updated",
    "aliases", "name_en", "status", "discipline",
}

FORBIDDEN_SECTIONS = [
    "寓言", "关联概念", "相关概念", "衍生问题",
    "延伸", "拓展",
]

FORBIDDEN_FIELDS = {
    "title", "slug", "created", "related", "updated",
    "aliases", "name_en", "status", "discipline",
}

FORBIDDEN_SECTIONS = [
    "寓言", "关联概念", "相关概念", "衍生问题",
    "延伸", "拓展",
]

FORBIDDEN_SECTIONS_PREFIX = ["与", "和"]

REQUIRED_SECTIONS = ["核心机制", "入口场景", "现实锚点", "适用边界"]
SECTION_ORDER = ["核心机制", "入口场景", "现实锚点", "适用边界", "圆桌沉淀"]

ROUNDTABLE_TAGS = ["陈述", "质疑", "补充", "反驳", "修正", "综合"]

# 否定排比模式
NEGATION_PAIR_PATTERNS = [
    r'不是[^，。；\n]+而是',
    r'不[是在][^，。；\n]+而[是在]',
    r'不[^，。；\n]{2,20}[^是]而[^，。；\n]+',
    r'不仅仅[^，。；\n]+更[是还]',
    r'不只是[^，。；\n]+更是',
    r'并非[^，。；\n]+而是',
]

# 肤浅分析结尾词
SHALLOW_ENDINGS = ["突出", "彰显", "反映", "象征"]


def load_scholar_dict() -> dict:
    """加载学者对照表。"""
    return _load_scholar_dict_util()


# parse_frontmatter 已从 _common 导入，此处不再重复定义


def extract_sections(body: str) -> List[str]:
    """从正文中提取所有 h2 章节名（## XXX）。"""
    return re.findall(r"^## (.+)$", body, re.MULTILINE)


def extract_h1(body: str) -> List[str]:
    """提取 h1 标题。"""
    return re.findall(r"^# (.+)$", body, re.MULTILINE)


def check_file(
    filepath: str, scholar_dict: dict, fix: bool = False, short_unsafe: Optional[set] = None
) -> List[dict]:
    """检查单个概念页，返回问题列表。fix=True 时自动修复可修复项。"""
    fname = os.path.basename(filepath)
    concept_name = fname[:-3] if fname.endswith(".md") else fname

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    issues = []
    fm = parse_frontmatter(content)
    body = content

    if fm:
        fm_end = content.find("---", content.find("---") + 3) + 3
        body = content[fm_end:]

    # ── 1. frontmatter 字段名合规 ────────────────────────────
    if fm:
        for key in fm:
            if key in FORBIDDEN_FIELDS:
                issues.append({
                    "rule": "F01", "concept": concept_name,
                    "msg": f"禁用字段 '{key}'",
                    "fixable": True, "auto_fix": "remove_field", "detail": key,
                })

    # ── 2. name 字段格式 ─────────────────────────────────────
    if fm and "name" in fm:
        name_val = fm["name"]
        if not re.search(r"（[^）]+）", name_val):
            # 检查是否有半角括号
            if re.search(r"\([^)]+\)", name_val):
                issues.append({
                    "rule": "F02", "concept": concept_name,
                    "msg": f"name 用了半角括号: {name_val}",
                    "fixable": True, "auto_fix": "fix_name_parens",
                    "detail": name_val,
                })
            else:
                issues.append({
                    "rule": "F02", "concept": concept_name,
                    "msg": f"name 缺少全角括号英文: {name_val}",
                    "fixable": False,
                })
    elif fm and "name" not in fm:
        issues.append({
            "rule": "F02", "concept": concept_name,
            "msg": "缺少 name 字段",
            "fixable": False,
        })

    # ── 3. tags 两类必填 ─────────────────────────────────────
    if fm:
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        has_discipline = any(t.startswith("discipline/") for t in tags)
        has_apply = any(t.startswith("apply/") for t in tags)

        if not has_discipline:
            issues.append({
                "rule": "F03", "concept": concept_name,
                "msg": "缺少 discipline 标签",
                "fixable": False,
            })
        if not has_apply:
            issues.append({
                "rule": "F03", "concept": concept_name,
                "msg": "缺少 apply 标签",
                "fixable": False,
            })

        # 检查未知前缀
        for tag in tags:
            if tag.startswith(("discipline/", "apply/", "person/")):
                continue
            if tag:
                issues.append({
                    "rule": "F03", "concept": concept_name,
                    "msg": f"tag \"{tag}\" 前缀不规范",
                    "fixable": False,
                })

        # 检查 discipline 值是否在词汇表内
        for tag in tags:
            if tag.startswith("discipline/"):
                val = tag[len("discipline/"):]
                if val not in DISCIPLINE_WHITELIST:
                    issues.append({
                        "rule": "F03", "concept": concept_name,
                        "msg": f"discipline/{val} 不在词汇表内",
                        "fixable": False,
                    })

        # 检查 apply 值
        for tag in tags:
            if tag.startswith("apply/"):
                val = tag[len("apply/"):]
                if val not in APPLY_WHITELIST:
                    issues.append({
                        "rule": "F03", "concept": concept_name,
                        "msg": f"apply/{val} 不在词汇表内",
                        "fixable": False,
                    })

        # 检查 person/ 标签是否为纯中文（禁止英文/下划线格式）
        for tag in tags:
            if tag.startswith("person/"):
                val = tag[len("person/"):]
                if re.search(r'[A-Za-z]', val):
                    issues.append({
                        "rule": "F03", "concept": concept_name,
                        "msg": f"person/{val} 包含英文字符，标签值必须使用中文",
                        "fixable": False,
                    })

        # 检查独立的 discipline 字段（应放在 tags 里）
        if "discipline" in fm:
            issues.append({
                "rule": "F03", "concept": concept_name,
                "msg": "禁止独立 discipline 字段，应放入 tags",
                "fixable": True, "auto_fix": "remove_discipline_field",
            })

        # 检查 tags 顺序：discipline → apply
        tag_order_prefixes = ["discipline/", "apply/"]
        order_violation = False
        max_seen_idx = -1
        for tag in tags:
            for idx, prefix in enumerate(tag_order_prefixes):
                if tag.startswith(prefix):
                    if idx < max_seen_idx:
                        order_violation = True
                    max_seen_idx = max(max_seen_idx, idx)
                    break
        if order_violation:
            # 重排：按 discipline/apply 分组，保持各组内部原有顺序
            reordered = []
            for prefix in tag_order_prefixes:
                for t in tags:
                    if t.startswith(prefix):
                        reordered.append(t)
            issues.append({
                "rule": "F03", "concept": concept_name,
                "msg": f"tags 顺序应为 discipline → apply",
                "fixable": True, "auto_fix": "reorder_tags",
                "_reordered_tags": reordered,
            })

    # ── 4. domain 合规 ───────────────────────────────────────
    if fm and "domain" in fm:
        domain = fm["domain"]
        if isinstance(domain, str):
            domain = [domain]
        for d in domain:
            if d not in DOMAIN_WHITELIST:
                issues.append({
                    "rule": "F04", "concept": concept_name,
                    "msg": f"domain '{d}' 不在 11 个顶层值内",
                    "fixable": False,
                })

    # ── 5. 正文无 h1 标题 ───────────────────────────────────
    h1_titles = extract_h1(body)
    if h1_titles:
        issues.append({
            "rule": "F05", "concept": concept_name,
            "msg": f"正文含 h1 标题: {h1_titles[0]}",
            "fixable": True, "auto_fix": "remove_h1",
            "detail": h1_titles[0],
        })

    # ── 6. 章节结构完整且顺序正确 ───────────────────────────
    sections = extract_sections(body)

    # 检查必需章节
    for req in REQUIRED_SECTIONS:
        if req not in sections:
            issues.append({
                "rule": "F06", "concept": concept_name,
                "msg": f"缺少必需章节: {req}",
                "fixable": False,
            })

    # 检查章节顺序
    present_ordered = [s for s in SECTION_ORDER if s in sections]
    actual_ordered = [s for s in sections if s in SECTION_ORDER]
    if present_ordered != actual_ordered:
        issues.append({
            "rule": "F06", "concept": concept_name,
            "msg": f"章节顺序错误: 实际={actual_ordered}, 应为={present_ordered}",
            "fixable": False,
        })

    # 检查禁止出现的章节名
    for sec in sections:
        if sec in FORBIDDEN_SECTIONS:
            issues.append({
                "rule": "F06", "concept": concept_name,
                "msg": f"禁止章节名: {sec}",
                "fixable": False,
            })
        for prefix in FORBIDDEN_SECTIONS_PREFIX:
            if sec.startswith(prefix) and ("的关系" in sec or "的区别" in sec):
                issues.append({
                    "rule": "F06", "concept": concept_name,
                    "msg": f"禁止章节名: {sec}",
                    "fixable": False,
                })
        # 非标准章节名：不在 SECTION_ORDER 里的全部报错
        if sec not in SECTION_ORDER and sec not in FORBIDDEN_SECTIONS:
            # 排除 FORBIDDEN_SECTIONS 已处理的
            if not any(sec.startswith(p) and ("的关系" in sec or "的区别" in sec) for p in FORBIDDEN_SECTIONS_PREFIX):
                issues.append({
                    "rule": "F06", "concept": concept_name,
                    "msg": f"非标准章节名: {sec}（允许的章节: {', '.join(SECTION_ORDER)}）",
                    "fixable": False,
                })

    # ── 7. 现实锚点使用 bullet point ────────────────────────
    if "现实锚点" in sections:
        anchor_match = re.search(
            r"^## 现实锚点\s*\n(.*?)(?=^## |\Z)",
            body, re.MULTILINE | re.DOTALL,
        )
        if anchor_match:
            anchor_text = anchor_match.group(1).strip()
            if not anchor_text:
                issues.append({
                    "rule": "F07", "concept": concept_name,
                    "msg": "现实锚点内容为空",
                    "fixable": False,
                })
            else:
                # 检查是否已有 - **粗体标题**： 格式
                has_bold_bullet = bool(re.search(r"^- \*\*", anchor_text, re.MULTILINE))
                has_bullet = bool(re.search(r"^- ", anchor_text, re.MULTILINE))
                if has_bold_bullet:
                    pass  # 合规
                elif has_bullet:
                    # 有 bullet 但没有加粗标题，看能否自动修复
                    bullets = re.findall(r"^- (.+)$", anchor_text, re.MULTILINE)
                    has_colon_prefix = any(re.match(r".*?[：:]", b) for b in bullets)
                    if has_colon_prefix:
                        issues.append({
                            "rule": "F07", "concept": concept_name,
                            "msg": "现实锚点 bullet 缺少粗体标题（可自动加粗冒号前关键词）",
                            "fixable": True, "auto_fix": "bold_anchor_titles",
                        })
                    else:
                        issues.append({
                            "rule": "F07", "concept": concept_name,
                            "msg": "现实锚点 bullet 为纯句子，缺少标题结构",
                            "fixable": False,
                        })
                else:
                    issues.append({
                        "rule": "F07", "concept": concept_name,
                        "msg": "现实锚点未使用 bullet point 格式",
                        "fixable": False,
                    })

    # ── 8. 概念链接 [[]] ────────────────────────────────────
    # 检查独立的「相关概念」章节（已在 F06 处理）
    # 此规则主要靠 F06 的 FORBIDDEN_SECTIONS 覆盖

    # ── 9. 学者名标注合规 ───────────────────────────────────
    if short_unsafe is None:
        short_unsafe = build_short_unsafe(scholar_dict)

    # 圆桌沉淀部分有嘉宾表格提供中英文，F09 只检查正文
    body_for_f09 = body
    if "圆桌沉淀" in sections:
        rt_start = body.find("## 圆桌沉淀")
        if rt_start != -1:
            body_for_f09 = body[:rt_start]
    body_clean = re.sub(r"\[\[.*?\]\]", "", body_for_f09)

    for key, info in scholar_dict.items():
        full_name = info["full"]
        en_name = info["en"]
        short_name = info.get("short", key)

        correct_pattern = re.escape(full_name) + r"（" + re.escape(en_name) + r"）"
        if re.search(correct_pattern, content):
            continue
        if re.search(re.escape(en_name), body_clean):
            continue

        has_full = bool(re.search(re.escape(full_name), body_clean))
        if has_full:
            issues.append({
                "rule": "F09", "concept": concept_name,
                "msg": f"学者「{full_name}」缺英文名标注（应为{full_name}（{en_name}））",
                "fixable": True, "auto_fix": "fix_scholar_name",
                "detail": {"full": full_name, "en": en_name},
            })
            continue

        if short_name == full_name or len(short_name) <= 1:
            continue

        safe_positions = find_safe_short_positions(
            body_clean, short_name, full_name, scholar_dict, short_unsafe
        )
        if safe_positions:
            issues.append({
                "rule": "F09", "concept": concept_name,
                "msg": f"学者「{short_name}」使用了短名缺标注（应为{full_name}（{en_name}））",
                "fixable": True, "auto_fix": "fix_scholar_name_short",
                "detail": {
                    "short": short_name,
                    "full": full_name,
                    "en": en_name,
                    "pos": safe_positions[0],
                },
            })

    # ── 10. 圆桌嘉宾行格式 ──────────────────────────────────
    if "圆桌沉淀" in sections:
        rt_match = re.search(
            r"^## 圆桌沉淀\s*\n(.*?)(?=^## |\Z)",
            body, re.MULTILINE | re.DOTALL,
        )
        if rt_match:
            rt_text = rt_match.group(1)

            # 检查 MBTI
            mbti_pattern = r"\b(INFJ|INFP|INTJ|INTP|ISFJ|ISFP|ISTJ|ISTP|ENFJ|ENFP|ENTJ|ENTP|ESFJ|ESFP|ESTJ|ESTP)\b"
            mbti_matches = re.findall(mbti_pattern, rt_text)
            if mbti_matches:
                issues.append({
                    "rule": "F10", "concept": concept_name,
                    "msg": f"圆桌嘉宾包含 MBTI: {', '.join(set(mbti_matches))}",
                    "fixable": True, "auto_fix": "remove_mbti",
                })

            # 检查「主持人综述」标题
            if "### 主持人综述" not in rt_text:
                if "主持人综述" in rt_text:
                    issues.append({
                        "rule": "F11", "concept": concept_name,
                        "msg": "主持人综述标题格式不正确（应为 ### 主持人综述）",
                        "fixable": False,
                    })
                else:
                    issues.append({
                        "rule": "F11", "concept": concept_name,
                        "msg": "圆桌沉淀缺少主持人综述",
                        "fixable": False,
                    })

            # 检查「留存洞见」标题
            if "### 留存洞见" not in rt_text:
                if "留存洞见" in rt_text:
                    issues.append({
                        "rule": "F11", "concept": concept_name,
                        "msg": "留存洞见标题格式不正确（应为 ### 留存洞见）",
                        "fixable": False,
                    })
                else:
                    issues.append({
                        "rule": "F11", "concept": concept_name,
                        "msg": "圆桌沉淀缺少留存洞见",
                        "fixable": False,
                    })

            # 检查 mermaid 代码块
            if "```mermaid" in rt_text:
                issues.append({
                    "rule": "F11", "concept": concept_name,
                    "msg": "圆桌图表使用了 mermaid 代码块（应使用 ```text）",
                    "fixable": True, "auto_fix": "mermaid_to_text",
                })

            # 检查发言格式：粗体发言标签
            # 错误：【人名】【**标签**】 或 **【人名】**
            bold_tag_pattern = r"\*\*【[^】]+】\*\*|【\*\*[^】]+\*\*】"
            if re.search(bold_tag_pattern, rt_text):
                issues.append({
                    "rule": "F11", "concept": concept_name,
                    "msg": "圆桌发言标签不应加粗",
                    "fixable": True, "auto_fix": "unbold_tags",
                })

    # ── 12. 中文引号合规 ────────────────────────────────────
    # 检查弯引号 ""（排除 frontmatter）
    curly_double = re.findall(r'"([^"]*)"', body)
    if curly_double:
        count = len(curly_double)
        issues.append({
            "rule": "F12", "concept": concept_name,
            "msg": f"弯引号 {count} 处",
            "fixable": True, "auto_fix": "fix_curly_quotes",
            "detail": count,
        })

    # 检查弯引号 ''（单引号变体）
    curly_single_left = len(re.findall(r"'", body))
    # 不报告单引号，因为在英语人名中会用到

    # ── 附加：否定排比检测 ──────────────────────────────────
    for pattern in NEGATION_PAIR_PATTERNS:
        matches = re.findall(pattern, body)
        if matches:
            # 取前 3 个例子
            examples = [m[:50] for m in matches[:3]]
            issues.append({
                "rule": "S01", "concept": concept_name,
                "msg": f"否定排比 {len(matches)} 处: {'; '.join(examples)}",
                "fixable": False,  # 需要人工改写
            })
            break  # 不重复报告同一文件

    # ── 附加：入口场景质量检测（召回式，宁可多报，人工再筛） ──
    # E01 格式硬伤（空/元描述/跳跃声明）| E02 匿名占位 | E03 泛指论述开头 | E04 篇幅过短
    if "入口场景" in sections:
        entry_match = re.search(
            r"^## 入口场景\s*\n(.*?)(?=^## |\Z)",
            body, re.MULTILINE | re.DOTALL,
        )
        if entry_match:
            entry_text = entry_match.group(1).strip()
            src = fm.get("source") if fm else None
            # 去掉 wikilink 标记后的纯文本，用于数字数和预览
            plain = re.sub(r"\[\[([^\]]*?)\]\]", r"\1", entry_text)
            cn_chars = len(re.findall(r"[一-鿿]", plain))
            entry_preview = re.sub(r"\s+", "", plain)[:40]

            if not entry_text:
                issues.append({
                    "rule": "E01", "concept": concept_name,
                    "msg": "入口场景内容为空",
                    "fixable": False, "source": src, "entry_preview": "",
                })
            else:
                first_line = entry_text.split("\n")[0].strip()
                # ── E01：格式硬伤（开头是元描述/跳跃声明/圆桌声明） ──
                if re.search(r"^讨论\[?\[?.*?\]?\]?时", first_line):
                    issues.append({
                        "rule": "E01", "concept": concept_name,
                        "msg": "入口场景以「讨论XX时」开头，应为故事体",
                        "fixable": False, "source": src, "entry_preview": entry_preview,
                    })
                elif re.search(r"^从\[?\[?.*?\]?\]?(跳跃|跨域)", first_line):
                    issues.append({
                        "rule": "E01", "concept": concept_name,
                        "msg": "入口场景以「从XX跳跃」开头，应为故事体",
                        "fixable": False, "source": src, "entry_preview": entry_preview,
                    })
                elif re.search(r"圆桌中", first_line):
                    issues.append({
                        "rule": "E01", "concept": concept_name,
                        "msg": "入口场景以「XX圆桌中」开头，应为故事体",
                        "fixable": False, "source": src, "entry_preview": entry_preview,
                    })
                elif re.match(r"^(这个概念|该概念|这个模型|这个理论|这个效应|这个现象|本概念)", first_line):
                    issues.append({
                        "rule": "E01", "concept": concept_name,
                        "msg": f"入口场景以元描述开头（{first_line[:20]}）",
                        "fixable": False, "source": src, "entry_preview": entry_preview,
                    })

                # ── E02：匿名占位（缺①具名的人） ──
                # 只抓明确的不具名占位词；不含「一个人/有人」——它们大量出现在
                # 「所有人/没有人」等复合词及合理叙事中，误报率过高
                anon = re.findall(r"某[人位甲乙君]|某个人|此人(?!们)", entry_text)
                if anon:
                    issues.append({
                        "rule": "E02", "concept": concept_name,
                        "msg": f"匿名占位（{'、'.join(sorted(set(anon)))}），疑缺具名人物",
                        "fixable": False, "source": src, "entry_preview": entry_preview,
                    })

                # ── E03：泛指/论述开头（是论述不是场景） ──
                if re.match(r"^(往往|通常|一般来说|一般而言|很多时候|有时候|有时|我们|人们|大家|每当|当我们|在.{0,12}(中|时|里)[，,])", first_line):
                    issues.append({
                        "rule": "E03", "concept": concept_name,
                        "msg": f"泛指/论述开头（{first_line[:20]}）",
                        "fixable": False, "source": src, "entry_preview": entry_preview,
                    })

                # ── E04：篇幅过短（场景没展开） ──
                threshold = 150 if src == "寓言故事" else 60
                if cn_chars < threshold:
                    issues.append({
                        "rule": "E04", "concept": concept_name,
                        "msg": f"篇幅过短（{cn_chars}字 < {threshold}，来源={src}）",
                        "fixable": False, "source": src, "entry_preview": entry_preview,
                    })

    # ── 附加：source 合规 ────────────────────────────────────
    if fm and "source" in fm:
        src = fm["source"]
        if src not in SOURCE_WHITELIST:
            issues.append({
                "rule": "F01", "concept": concept_name,
                "msg": f"source '{src}' 不在 5 个合法值内",
                "fixable": False,
            })

    return issues


def _extract_body(content: str) -> tuple[int, str]:
    """返回 (frontmatter 结束偏移, 正文)。兼容有无 --- 分隔的 frontmatter。"""
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if m:
        return m.end(), content[m.end():]
    # 无 --- 分隔：找第一个 ## 作为正文起点
    h2 = re.search(r"\n## ", content)
    if h2:
        return h2.start(), content[h2.start():]
    return 0, content


def fix_issue(content: str, issue: dict) -> str:
    """根据 issue 的 auto_fix 类型执行修复。"""
    fix_type = issue.get("auto_fix")
    if not fix_type:
        return content

    if fix_type == "remove_field":
        field = issue["detail"]
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{field}:"):
                continue
            new_lines.append(line)
        return "\n".join(new_lines)

    if fix_type == "fix_name_parens":
        name_val = issue["detail"]
        m = re.search(r"\(([^)]+)\)", name_val)
        if m:
            en_name = m.group(1)
            new_name = name_val.replace(f"({en_name})", f"（{en_name}）")
            return content.replace(f"name: {name_val}", f"name: {new_name}")
        return content

    if fix_type == "remove_h1":
        title = issue["detail"]
        return re.sub(rf"^# {re.escape(title)}\s*\n", "", content, count=1, flags=re.MULTILINE)

    if fix_type == "remove_discipline_field":
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if re.match(r"^discipline:", line.strip()):
                continue
            new_lines.append(line)
        return "\n".join(new_lines)

    if fix_type == "fix_curly_quotes":
        # 替换正文中的弯引号为直角引号
        fm_end = content.find("---", content.find("---") + 3) + 3
        if fm_end < 10:
            return content
        fm = content[:fm_end]
        body = content[fm_end:]
        # 简单的配对替换
        # " 替换为「或」
        result = []
        quote_open = False
        for ch in body:
            if ch == "“":  # "
                result.append("「")  # 「
                quote_open = True
            elif ch == "”":  # "
                result.append("」")  # 」
                quote_open = False
            else:
                result.append(ch)
        return fm + "".join(result)

    if fix_type == "remove_mbti":
        mbti_pattern = r"\b(INFJ|INFP|INTJ|INTP|ISFJ|ISFP|ISTJ|ISTP|ENFJ|ENFP|ENTJ|ENTP|ESFJ|ESFP|ESTJ|ESTP)\b"
        fm_end = content.find("---", content.find("---") + 3) + 3
        if fm_end < 10:
            return content
        fm = content[:fm_end]
        body = content[fm_end:]
        body = re.sub(mbti_pattern, "", body)
        # 清理多余空格
        body = re.sub(r"  +", " ", body)
        return fm + body

    if fix_type == "mermaid_to_text":
        return content.replace("```mermaid", "```text")

    if fix_type == "unbold_tags":
        # 【**人名**】【**标签**】 → 【人名】【标签】
        content = re.sub(r"\*\*【([^】]+)】\*\*", r"【\1】", content)
        # 【**人名**】 → 【人名】
        content = re.sub(r"【\*\*([^】]+)\*\*】", r"【\1】", content)
        return content

    if fix_type == "bold_anchor_titles":
        # 在现实锚点 section 中，将 - 关键词：描述 → - **关键词**：描述
        def _bold_bullet_line(match):
            indent = match.group(1)  # 可能的缩进
            prefix = match.group(2)  # - 开头
            rest = match.group(3)    # 冒号前的内容
            colon = match.group(4)   # ：或:
            after = match.group(5)   # 冒号后的内容
            return f"{indent}{prefix}**{rest.strip()}**{colon}{after}"

        # 只处理现实锚点 section
        anchor_match = re.search(
            r"(^## 现实锚点\s*\n)(.*?)(?=^## |\Z)",
            content, re.MULTILINE | re.DOTALL,
        )
        if anchor_match:
            section_header = anchor_match.group(1)
            section_body = anchor_match.group(2)
            # 匹配 - 关键词：描述（关键词不含 [] 或 ** 等 markdown 语法）
            section_body = re.sub(
                r"^(\s*)(- )([^*\[\n：:]+?)([：:])(.*)$",
                _bold_bullet_line,
                section_body,
                flags=re.MULTILINE,
            )
            content = content[:anchor_match.start()] + section_header + section_body + content[anchor_match.end():]
        return content

    if fix_type == "reorder_tags":
        reordered = issue.get("_reordered_tags")
        if reordered:
            tags_str = ", ".join(reordered)
            new_tags_line = f"tags: [{tags_str}]"
            content = re.sub(
                r"^tags:.*$",
                new_tags_line,
                content,
                count=1,
                flags=re.MULTILINE,
            )
        return content

    if fix_type == "fix_scholar_name":
        detail = issue.get("detail", {})
        full_name = detail["full"]
        en_name = detail["en"]
        fm_offset, body = _extract_body(content)
        replacement = f"{full_name}（{en_name}）"
        new_body = re.sub(re.escape(full_name), replacement, body, count=1)
        if new_body != body:
            return content[:fm_offset] + new_body
        return content

    if fix_type == "fix_scholar_name_short":
        detail = issue.get("detail", {})
        short_name = detail["short"]
        full_name = detail["full"]
        en_name = detail["en"]
        pos = detail.get("pos")
        fm_offset, body = _extract_body(content)
        replacement = f"{full_name}（{en_name}）"
        if pos is not None:
            new_body = body[:pos] + replacement + body[pos + len(short_name):]
        else:
            new_body = body
        if new_body != body:
            return content[:fm_offset] + new_body
        return content

    return content


ENTRY_RULES = ["E01", "E02", "E03", "E04"]


def print_entry_report(all_issues: List[dict], n_files: int) -> None:
    """入口场景候选清单：聚合 E01-E04，按命中信号数降序排列。"""
    by_concept: Dict[str, dict] = {}
    for it in all_issues:
        if it["rule"] not in ENTRY_RULES:
            continue
        c = it["concept"]
        if c not in by_concept:
            by_concept[c] = {
                "source": it.get("source"),
                "preview": it.get("entry_preview", ""),
                "signals": [],
            }
        by_concept[c]["signals"].append(it["rule"])

    rows = sorted(
        by_concept.items(),
        key=lambda kv: (-len(set(kv[1]["signals"])), kv[0]),
    )

    print(f"入口场景候选清单 — 扫描 {n_files} 页，命中 {len(rows)} 页")
    print("=" * 70)
    print("命中越多越可疑；这是召回不是判决，最终改不改由人工读了定。\n")
    by_count: Dict[int, int] = defaultdict(int)
    for concept, info in rows:
        sigs = sorted(set(info["signals"]))
        by_count[len(sigs)] += 1
        src = info["source"] or "?"
        print(f"[{len(sigs)}] {concept}（{src}） {'+'.join(sigs)}")
        print(f"      {info['preview']}…")
    print(f"\n{'-' * 70}")
    for n in sorted(by_count.keys(), reverse=True):
        print(f"  命中 {n} 类信号: {by_count[n]} 页")
    print(f"  合计候选: {len(rows)} 页")


def dump_entries(out_path: str) -> None:
    """导出所有概念页的入口场景全文到一个聚合文件，供人工分批通读筛查。"""
    blocks = []
    n = 0
    for fname in sorted(os.listdir(CONCEPT_DIR)):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        fpath = os.path.join(CONCEPT_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        fm = parse_frontmatter(content)
        body = content
        if fm:
            body = content[content.find("---", content.find("---") + 3) + 3:]
        m = re.search(r"^## 入口场景\s*\n(.*?)(?=^## |\Z)", body,
                      re.MULTILINE | re.DOTALL)
        entry = m.group(1).strip() if m else "（缺入口场景章节）"
        src = (fm or {}).get("source", "?")
        cn = len(re.findall(r"[一-鿿]", re.sub(r"\[\[([^\]]*?)\]\]", r"\1", entry)))
        concept = fname[:-3]
        n += 1
        blocks.append(f"### {concept}　|　来源:{src}　|　{cn}字\n{entry}\n")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# 入口场景全量导出（{n} 页）\n\n" + "\n".join(blocks))
    print(f"已导出 {n} 页入口场景 → {out_path}")


def run_lint(
    fix: bool = False,
    target_file: Optional[str] = None,
    entry_report: bool = False,
    fix_scholars: bool = False,
) -> None:
    """运行全量质检。F09 学者短名替换默认不随 --fix 执行，需 --fix-scholars。"""
    scholar_dict = load_scholar_dict()
    short_unsafe = build_short_unsafe(scholar_dict)
    start = time.time()

    if target_file:
        # 单文件模式
        filepath = os.path.join(CONCEPT_DIR, f"{target_file}.md")
        if not os.path.exists(filepath):
            print(f"文件不存在: {filepath}")
            sys.exit(1)
        files = [(target_file, filepath)]
    else:
        files = []
        for fname in sorted(os.listdir(CONCEPT_DIR)):
            if not fname.endswith(".md") or fname == "INDEX.md":
                continue
            fpath = os.path.join(CONCEPT_DIR, fname)
            if os.path.isfile(fpath):
                files.append((fname[:-3], fpath))

    all_issues = []
    fix_count = 0

    scholar_fix_types = {"fix_scholar_name", "fix_scholar_name_short"}

    for name, fpath in files:
        issues = check_file(fpath, scholar_dict, fix=fix, short_unsafe=short_unsafe)
        if fix and issues:
            fixable = [i for i in issues if i.get("fixable")]
            if not fix_scholars:
                fixable = [
                    i for i in fixable
                    if i.get("auto_fix") not in scholar_fix_types
                ]
            if fixable:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                for issue in fixable:
                    content = fix_issue(content, issue)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                fix_count += len(fixable)
        all_issues.extend(issues)

    elapsed = time.time() - start

    if entry_report:
        print_entry_report(all_issues, len(files))
        return

    # ── 报告 ────────────────────────────────────────────────
    print(f"概念库格式质检 — {len(files)} 个概念页, {elapsed:.1f}s")
    print("=" * 60)

    if not all_issues:
        print("全部通过，无问题。")
        if fix:
            print(f"自动修复: {fix_count} 处")
        return

    # 按规则分组
    by_rule = defaultdict(list)
    for issue in all_issues:
        by_rule[issue["rule"]].append(issue)

    rule_labels = {
        "F01": "frontmatter 字段合规（禁用字段/source）",
        "F02": "name 字段格式",
        "F03": "tags 合规（discipline/apply）",
        "F04": "domain 合规",
        "F05": "正文无 h1 标题",
        "F06": "章节结构完整且顺序正确",
        "F07": "现实锚点 bullet point 格式",
        "F08": "概念链接 [[]]",
        "F09": "学者名标注",
        "F10": "圆桌嘉宾行格式",
        "F11": "圆桌沉淀格式",
        "F12": "中文引号（弯引号）",
        "S01": "否定排比",
        "E01": "入口场景格式硬伤（空/元描述/跳跃声明开头）",
        "E02": "入口场景匿名占位（疑缺具名人物）",
        "E03": "入口场景泛指/论述开头（疑非具体场景）",
        "E04": "入口场景篇幅过短（场景没展开）",
    }

    total_fixable = 0
    total_unfixable = 0

    for rule in sorted(by_rule.keys()):
        items = by_rule[rule]
        label = rule_labels.get(rule, rule)
        fixable_n = sum(1 for i in items if i.get("fixable"))
        total_fixable += fixable_n
        total_unfixable += len(items) - fixable_n

        print(f"\n## {rule} — {label} ({len(items)} 处, 可自动修复 {fixable_n})")
        print("-" * 50)
        for item in items[:20]:  # 每类最多显示 20 条
            fix_mark = "🔧" if item.get("fixable") else "  "
            print(f"  {fix_mark} {item['concept']}: {item['msg']}")
        if len(items) > 20:
            print(f"  ... 还有 {len(items) - 20} 条")

    print(f"\n{'=' * 60}")
    print(f"合计: {len(all_issues)} 处问题")
    print(f"  可自动修复: {total_fixable}")
    print(f"  需手动处理: {total_unfixable}")

    if fix:
        print(f"\n已自动修复: {fix_count} 处")
    elif total_fixable > 0:
        print(
            f"\n提示: python3 scripts/lint_concepts.py --fix 可自动修复非 F09 项；"
            f"学者标注需加 --fix-scholars（慎用，先跑 repair_scholar_f09_damage.py）"
        )


def main():
    parser = argparse.ArgumentParser(description="概念库全量格式质检")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题（不含 F09）")
    parser.add_argument(
        "--fix-scholars",
        action="store_true",
        help="与 --fix 联用时才自动改学者名（默认关闭，避免短名误伤）",
    )
    parser.add_argument("--file", type=str, help="只检查指定概念（不含 .md 后缀）")
    parser.add_argument("--entry-report", action="store_true",
                        help="只输出入口场景候选清单（按命中信号数排序）")
    parser.add_argument("--dump-entries", type=str, metavar="OUT",
                        help="导出所有入口场景全文到指定文件，供分批通读")
    args = parser.parse_args()
    if args.dump_entries:
        dump_entries(args.dump_entries)
        return
    run_lint(
        fix=args.fix,
        target_file=args.file,
        entry_report=args.entry_report,
        fix_scholars=args.fix_scholars,
    )


if __name__ == "__main__":
    main()
