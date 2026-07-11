#!/usr/bin/env python3
"""Live local server for the MERJIC concept wiki.

Watches concept Markdown and wiki source files, rebuilds the static site, and
exposes a tiny version endpoint used by the browser for automatic reloads.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = Path(__file__).resolve().parent
DIST_DIR = WIKI_DIR / "dist"
SOURCE_DIR = WIKI_DIR / "src"
CONCEPT_DIR = ROOT / "概念页"


class BuildState:
    def __init__(self) -> None:
        self.version = str(time.time_ns())
        self.error = ""
        self.lock = threading.Lock()


STATE = BuildState()


def file_snapshot(folder: Path, pattern: str, exclude: set[str] | None = None) -> tuple:
    excluded = exclude or set()
    result = []
    for path in folder.glob(pattern):
        if not path.is_file() or path.name in excluded:
            continue
        try:
            stat = path.stat()
            result.append((path.name, stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            continue
    return tuple(sorted(result))


def concept_snapshot() -> tuple:
    return file_snapshot(CONCEPT_DIR, "*.md", {"INDEX.md"})


def source_snapshot() -> tuple:
    return file_snapshot(SOURCE_DIR, "*") + file_snapshot(WIKI_DIR, "build.py")


def run_command(args: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    return completed.returncode == 0, completed.stdout.strip()


def rebuild(*, sync_data: bool, reason: str) -> bool:
    with STATE.lock:
        print(f"[{time.strftime('%H:%M:%S')}] 检测到{reason}，正在更新网页……", flush=True)
        commands: list[list[str]] = []
        if sync_data:
            commands.extend(
                [
                    [sys.executable, "scripts/sync_db.py", "--incremental"],
                    [sys.executable, "scripts/build_index.py", "--incremental"],
                ]
            )
        commands.append([sys.executable, "wiki/build.py"])

        for command in commands:
            ok, output = run_command(command)
            if not ok:
                STATE.error = output or "构建命令执行失败"
                print(f"更新失败：\n{STATE.error}", file=sys.stderr, flush=True)
                return False

        STATE.error = ""
        STATE.version = str(time.time_ns())
        print("网页已更新，浏览器即将自动刷新。", flush=True)
        return True


def watch_loop(interval: float) -> None:
    concepts_before = concept_snapshot()
    source_before = source_snapshot()
    while True:
        time.sleep(interval)
        concepts_after = concept_snapshot()
        source_after = source_snapshot()

        if concepts_after != concepts_before:
            time.sleep(0.35)
            rebuild(sync_data=True, reason="概念库变更")
            concepts_before = concept_snapshot()
            source_before = source_snapshot()
        elif source_after != source_before:
            time.sleep(0.2)
            rebuild(sync_data=False, reason="网页样式变更")
            source_before = source_snapshot()


class WikiHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if urlparse(self.path).path == "/__wiki_version":
            payload = json.dumps(
                {"version": STATE.version, "error": STATE.error}, ensure_ascii=False
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self) -> None:
        path = urlparse(self.path).path
        if path.endswith((".html", ".js", ".css", ".json")) or path == "/":
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        if urlparse(self.path).path != "/__wiki_version":
            super().log_message(format, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--interval", type=float, default=0.8)
    args = parser.parse_args()

    if not rebuild(sync_data=True, reason="启动检查") and not (DIST_DIR / "index.html").exists():
        raise SystemExit(1)

    watcher = threading.Thread(target=watch_loop, args=(args.interval,), daemon=True)
    watcher.start()

    handler = partial(WikiHandler, directory=str(DIST_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"概念 Wiki 持续预览：http://127.0.0.1:{args.port}", flush=True)
    print("概念页保存后会自动同步、构建并刷新浏览器。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
