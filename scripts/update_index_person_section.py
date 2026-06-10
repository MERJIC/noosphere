#!/usr/bin/env python3
"""Refresh the person-tag section in 概念页/INDEX.md."""

import os
from collections import defaultdict
from typing import Dict, List
from urllib.parse import quote

from _common import CONCEPT_DIR, parse_frontmatter, iter_concept_files


INDEX_PATH = os.path.join(CONCEPT_DIR, "INDEX.md")
SECTION_HEADING = "## 按人物"


def _concept_label(name: str) -> str:
    return name.strip() if name else ""


def _concept_link(filename: str) -> str:
    return quote(filename)


def collect_person_groups() -> Dict[str, List[dict]]:
    groups = defaultdict(list)

    for _, path in iter_concept_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        fm = parse_frontmatter(content)
        if not fm:
            continue

        raw_tags = fm.get("tags", [])
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]

        persons = []
        seen = set()
        for tag in raw_tags:
            if not isinstance(tag, str) or not tag.startswith("person/"):
                continue
            person = tag[len("person/"):].strip()
            if person and person not in seen:
                seen.add(person)
                persons.append(person)

        if not persons:
            continue

        filename = os.path.basename(path)
        name = _concept_label(str(fm.get("name", filename[:-3])))
        item = {
            "name": name,
            "filename": filename,
        }

        for person in persons:
            groups[person].append(item)

    for items in groups.values():
        items.sort(key=lambda item: item["name"])

    return dict(groups)


def render_person_section(groups: Dict[str, List[dict]]) -> str:
    lines = [SECTION_HEADING, ""]

    for person, items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"### {person}（{len(items)} 个）")
        lines.append("")
        for item in items:
            lines.append(f"- [{item['name']}]({_concept_link(item['filename'])})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def refresh_index_person_section() -> dict:
    if not os.path.exists(INDEX_PATH):
        return {"ok": False, "reason": f"INDEX.md 不存在: {INDEX_PATH}"}

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        current = f.read().rstrip() + "\n"

    groups = collect_person_groups()
    section = render_person_section(groups)

    heading_pos = current.find(f"\n{SECTION_HEADING}\n")
    if heading_pos == -1:
        new_content = current.rstrip() + "\n\n" + section
    else:
        new_content = current[: heading_pos + 1].rstrip() + "\n\n" + section

    if new_content != current:
        with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        changed = True
    else:
        changed = False

    return {
        "ok": True,
        "changed": changed,
        "persons": len(groups),
        "items": sum(len(items) for items in groups.values()),
    }


def main() -> None:
    result = refresh_index_person_section()
    if not result.get("ok"):
        raise SystemExit(result.get("reason", "刷新失败"))

    changed = "已更新" if result.get("changed") else "无变化"
    print(
        f"{changed}: {SECTION_HEADING} "
        f"({result.get('persons', 0)} 人物, {result.get('items', 0)} 条目)"
    )


if __name__ == "__main__":
    main()
