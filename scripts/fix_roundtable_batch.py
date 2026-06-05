#!/usr/bin/env python3
"""One-off batch fixes for roundtable F11 compliance."""
from __future__ import annotations

import os
import re

CONCEPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "概念页")


def read(name: str) -> str:
    with open(os.path.join(CONCEPT_DIR, f"{name}.md"), encoding="utf-8") as f:
        return f.read()


def write(name: str, content: str) -> None:
    with open(os.path.join(CONCEPT_DIR, f"{name}.md"), "w", encoding="utf-8") as f:
        f.write(content)


def remove_roundtable_section(content: str) -> str:
    return re.sub(r"\n## 圆桌沉淀\n.*", "", content, flags=re.DOTALL).rstrip() + "\n"


def main():
    # Placeholders — no roundtable yet
    for name in ("信号成本理论", "信息级联", "寄生社交关系"):
        write(name, remove_roundtable_section(read(name)))
        print(f"removed placeholder RT: {name}")

    # Cross-ref stubs — full RT lives on 董事会捕获 / 套牢问题
    for name in ("互套", "平庸之恶", "渐进式捕获"):
        write(name, remove_roundtable_section(read(name)))
        print(f"removed stub RT: {name}")

    # 序言悖论 — add 留存洞见
    p = read("序言悖论")
    if "### 留存洞见" not in p:
        block = """

### 留存洞见

- 悖论多在「信念 = 逻辑真值承诺」框架下才成立；五条进路（归纳、可错度、语法、网络、双系统）指向同一诊断
- 理性是否要求信念体系全局一致，仍是开放问题；概率论与非单调逻辑给出不同答案，无定论
- 集体版序言悖论（委员会、陪审团）与[[阿比林悖论]]对照：局部合理与全局不一致是制度日常
- 信念 vs 接受（Cohen）、程序正义（法律）、致良知（心学）提供不同层面的消解路径
- 衍生追问：知道作品是 AI 生成之后，「氛围体验」是否仍是同一体验（与波伏瓦/本雅明张力相关时可回看[[氛围]]）
"""
        # insert before **衍生问题** if present, else append to roundtable
        if "\n**衍生问题**" in p:
            p = p.replace("\n**衍生问题**", block + "\n**衍生问题**", 1)
        else:
            p = p.rstrip() + block + "\n"
        write("序言悖论", p)
        print("fixed 序言悖论 留存洞见")

    # 迪昂-奎因论题 — normalize headers
    q = read("迪昂-奎因论题")
    q = q.replace("**日期**：", "**日期：**")
    q = q.replace("### 主持人综述·第一轮", "### 主持人综述")
    q = q.replace("### 未穷尽的开放问题", "### 留存洞见")
    q = re.sub(
        r"【波普尔】\n",
        "【波普尔】【陈述】：\n",
        q,
        count=1,
    )
    if "**触发问题：**" not in q and "### 开场定义" in q:
        trigger = (
            "「保护假设」和「合理修正辅助条件」逻辑结构相同——"
            "凭什么区分？区分是否真实存在？"
        )
        q = q.replace(
            "**日期：** 2026-05-12\n**嘉宾：**",
            f"**日期：** 2026-05-12\n**触发问题：** {trigger}\n\n**嘉宾：**",
        )
    write("迪昂-奎因论题", q)
    print("fixed 迪昂-奎因论题 headers")


if __name__ == "__main__":
    main()