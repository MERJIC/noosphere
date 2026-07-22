#!/usr/bin/env python3
"""Build the MERJIC concept wiki from the existing Markdown vault and SQLite index."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "memory" / "concepts.db"
SOURCE_DIR = Path(__file__).resolve().parent / "src"
DIST_DIR = Path(__file__).resolve().parent / "dist"
CONCEPT_DATA_DIR = DIST_DIR / "concepts"


def json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.S)
        if match:
            return text[match.end() :]
    return text


def concept_href(target: str) -> str:
    return f"#/concept/{quote(target.strip(), safe='')}"


def inline_markdown(text: str) -> str:
    code_tokens: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_tokens.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00CODE{len(code_tokens) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash_code, text)
    text = html.escape(text, quote=True)

    def wiki_link(match: re.Match[str]) -> str:
        raw = html.unescape(match.group(1))
        target, _, label = raw.partition("|")
        label = label or target
        return (
            f'<a class="wiki-link" href="{concept_href(target)}" '
            f'data-concept="{html.escape(target, quote=True)}">'
            f'{html.escape(label)}</a>'
        )

    text = re.sub(r"\[\[([^\]]+)\]\]", wiki_link, text)

    def normal_link(match: re.Match[str]) -> str:
        label, url = html.unescape(match.group(1)), html.unescape(match.group(2))
        safe_url = html.escape(url, quote=True)
        external = url.startswith(("http://", "https://"))
        attrs = ' target="_blank" rel="noreferrer"' if external else ""
        return f'<a href="{safe_url}"{attrs}>{html.escape(label)}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", normal_link, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    for index, token in enumerate(code_tokens):
        text = text.replace(f"\x00CODE{index}\x00", token)
    return text


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render_markdown(markdown: str) -> tuple[str, list[dict[str, str]]]:
    lines = strip_frontmatter(markdown).replace("\r\n", "\n").split("\n")
    output: list[str] = []
    headings: list[dict[str, str]] = []
    index = 0

    def starts_block(line: str, next_line: str = "") -> bool:
        stripped = line.strip()
        return bool(
            not stripped
            or re.match(r"^(#{1,6})\s+", line)
            or re.match(r"^\s*([-*+] |\d+[.)] )", line)
            or line.startswith(">")
            or line.startswith("```")
            or stripped in {"---", "***", "___"}
            or ("|" in line and is_table_separator(next_line))
        )

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        fence = re.match(r"^```\s*([\w+-]*)", line)
        if fence:
            language = fence.group(1)
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            lang_class = f' class="language-{html.escape(language)}"' if language else ""
            output.append(f"<pre><code{lang_class}>{html.escape(chr(10).join(code))}</code></pre>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            plain_title = re.sub(r"[*_`~]", "", title)
            anchor = f"section-{len(headings) + 1}"
            headings.append({"id": anchor, "title": plain_title, "level": str(level)})
            output.append(f'<h{level} id="{anchor}">{inline_markdown(title)}</h{level}>')
            index += 1
            continue

        if index + 1 < len(lines) and "|" in line and is_table_separator(lines[index + 1]):
            headers = split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(split_table_row(lines[index]))
                index += 1
            head_html = "".join(f"<th>{inline_markdown(cell)}</th>" for cell in headers)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{inline_markdown(cell)}</td>" for cell in row) + "</tr>"
                for row in rows
            )
            output.append(f'<div class="table-wrap"><table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table></div>')
            continue

        list_match = re.match(r"^\s*([-*+]|\d+[.)])\s+(.+)", line)
        if list_match:
            ordered = list_match.group(1)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while index < len(lines):
                current = re.match(r"^\s*([-*+]|\d+[.)])\s+(.+)", lines[index])
                if not current or current.group(1)[0].isdigit() != ordered:
                    break
                items.append(f"<li>{inline_markdown(current.group(2))}</li>")
                index += 1
            output.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        if line.startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].startswith(">"):
                quote_lines.append(lines[index].lstrip("> "))
                index += 1
            output.append(f"<blockquote>{inline_markdown(' '.join(quote_lines))}</blockquote>")
            continue

        if stripped in {"---", "***", "___"}:
            output.append("<hr>")
            index += 1
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines):
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if starts_block(lines[index], next_line):
                break
            paragraph.append(lines[index].strip())
            index += 1
        output.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")

    return "\n".join(output), headings


def excerpt_from(markdown: str, limit: int = 150) -> str:
    body = strip_frontmatter(markdown)
    body = re.sub(r"```.*?```", " ", body, flags=re.S)
    body = re.sub(r"^#+\s+.*$", " ", body, flags=re.M)
    body = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), body)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"[*_`>#|~-]", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body if len(body) <= limit else body[:limit].rstrip() + "…"


def build() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    concept_rows = connection.execute("SELECT * FROM concepts ORDER BY name COLLATE NOCASE").fetchall()
    link_rows = connection.execute("SELECT * FROM links ORDER BY id").fetchall()
    aliases_by_name: dict[str, list[str]] = {}
    for alias in connection.execute("SELECT canonical, variant FROM name_aliases ORDER BY id"):
        aliases_by_name.setdefault(alias["canonical"], []).append(alias["variant"])

    outgoing: dict[int, list[dict[str, object]]] = {}
    backlinks: dict[int, list[dict[str, object]]] = {}
    row_by_id = {row["id"]: row for row in concept_rows}
    for link in link_rows:
        outgoing.setdefault(link["source_id"], []).append(
            {
                "name": link["target_name"],
                "resolved": bool(link["resolved"]),
                "targetId": link["target_id"],
                "context": link["context"],
            }
        )
        if link["target_id"]:
            source = row_by_id.get(link["source_id"])
            if source:
                backlinks.setdefault(link["target_id"], []).append(
                    {"id": source["id"], "name": source["name"], "context": link["context"]}
                )

    concepts: list[dict[str, object]] = []
    domain_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for row in concept_rows:
        filepath = ROOT / row["filepath"]
        if not filepath.exists():
            continue
        raw = filepath.read_text(encoding="utf-8")
        rendered, headings = render_markdown(raw)
        domains = json_list(row["domains"])
        tags = json_list(row["tags"])
        domain_counts.update(domains)
        if row["source"]:
            source_counts[row["source"]] += 1
        concepts.append(
            {
                "id": row["id"],
                "name": row["name"],
                "nameEn": row["name_en"] or "",
                "aliases": aliases_by_name.get(row["name"], []),
                "domains": domains,
                "date": row["date"],
                "source": row["source"],
                "tags": tags,
                "disciplines": json_list(row["disciplines"]),
                "applies": json_list(row["applies"]),
                "persons": json_list(row["persons"]),
                "wordCount": row["body_word_count"],
                "excerpt": excerpt_from(raw),
                "html": rendered,
                "headings": headings,
                "outgoing": outgoing.get(row["id"], []),
                "backlinks": backlinks.get(row["id"], []),
            }
        )

    payload = {
        "generatedAt": connection.execute("SELECT datetime('now')").fetchone()[0],
        "stats": {
            "concepts": len(concepts),
            "links": sum(1 for link in link_rows if link["resolved"]),
            "domains": len(domain_counts),
            "sources": len(source_counts),
        },
        "domains": [{"name": name, "count": count} for name, count in domain_counts.most_common()],
        "sources": [{"name": name, "count": count} for name, count in source_counts.most_common()],
        "concepts": concepts,
    }

    index_concepts = [
        {
            key: concept[key]
            for key in (
                "id", "name", "nameEn", "aliases", "domains", "date", "source",
                "tags", "disciplines", "applies", "persons", "wordCount", "excerpt",
            )
        }
        for concept in concepts
    ]
    index_payload = {
        "generatedAt": payload["generatedAt"],
        "stats": payload["stats"],
        "domains": payload["domains"],
        "sources": payload["sources"],
        "concepts": index_concepts,
    }

    (DIST_DIR / "concepts.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (DIST_DIR / "concept-index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    if CONCEPT_DATA_DIR.exists():
        shutil.rmtree(CONCEPT_DATA_DIR)
    CONCEPT_DATA_DIR.mkdir(parents=True)
    for concept in concepts:
        (CONCEPT_DATA_DIR / f"{concept['id']}.json").write_text(
            json.dumps(concept, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    for filename in ("index.html", "styles.css", "app.js"):
        shutil.copy2(SOURCE_DIR / filename, DIST_DIR / filename)
    print(
        f"Built {len(concepts)} concepts, {payload['stats']['links']} resolved links "
        f"across {len(domain_counts)} domains → {DIST_DIR}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    build()
