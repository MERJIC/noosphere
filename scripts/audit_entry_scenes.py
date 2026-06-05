#!/usr/bin/env python3
"""Audit 入口场景 length for 寓言故事 / 概念跳跃 concept pages."""
import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1] / "概念页"
MIN_CHARS = 280
DEFAULT_SOURCES = {"寓言故事", "概念跳跃"}


def parse_page(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2]
    m = re.search(r"## 入口场景\s*\n(.*?)(?=\n## |\Z)", body, re.S)
    scene = m.group(1).strip() if m else ""
    return {
        "file": path.name,
        "stem": path.stem,
        "name": fm.get("name", path.stem),
        "source": fm.get("source", ""),
        "chars": len(scene),
        "paras": len([b for b in re.split(r"\n\s*\n", scene) if b.strip()]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS)
    ap.add_argument(
        "--sources",
        default=",".join(sorted(DEFAULT_SOURCES)),
        help="Comma-separated source values (default: 寓言故事,概念跳跃)",
    )
    ap.add_argument("--require-quotes", action="store_true", help="Flag if 入口场景 lacks 「」 dialogue")
    ap.add_argument("--jsonl", type=Path, help="Write flagged rows to JSONL")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    allowed_sources = {s.strip() for s in args.sources.split(",") if s.strip()}

    flagged = []
    for p in sorted(ROOT.glob("*.md")):
        if p.name == "INDEX.md":
            continue
        row = parse_page(p)
        if row.get("source") not in allowed_sources:
            continue
        if row["chars"] < args.min_chars:
            flagged.append(row)
            continue
        if args.require_quotes:
            scene_m = re.search(
                r"## 入口场景\s*\n(.*?)(?=\n## |\Z)", p.read_text(encoding="utf-8").split("---", 2)[2], re.S
            )
            scene = scene_m.group(1) if scene_m else ""
            if "「" not in scene:
                row = {**row, "reason": "no_dialogue_quotes"}
                flagged.append(row)

    flagged.sort(key=lambda r: r["chars"])
    if args.limit:
        flagged = flagged[: args.limit]

    if args.jsonl:
        args.jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.jsonl.open("w", encoding="utf-8") as f:
            for row in flagged:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"FLAGGED: {len(flagged)} (sources={sorted(allowed_sources)}, min_chars={args.min_chars})\n")
    for row in flagged:
        print(f"{row['chars']:4d}字 {row['paras']}段 | {row['source']:8s} | {row['name']}")

    return 0 if not flagged else 1


if __name__ == "__main__":
    raise SystemExit(main())