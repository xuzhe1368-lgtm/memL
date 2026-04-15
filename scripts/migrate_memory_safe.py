#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe memory migration utility for memL."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

ILLEGAL_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def clean_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = ILLEGAL_CTRL_RE.sub("", s)
    return s


def read_text_safe(path: Path) -> str:
    return clean_text(path.read_text(encoding="utf-8-sig", errors="replace"))


def chunk_markdown(text: str, max_chars: int = 1200) -> list[str]:
    lines = text.splitlines()
    chunks: list[str] = []
    buf: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal buf, size
        if buf:
            block = "\n".join(buf).strip()
            if block:
                chunks.append(block)
        buf = []
        size = 0

    for line in lines:
        if line.startswith("#") and buf:
            flush()
        buf.append(line)
        size += len(line) + 1
        if size >= max_chars:
            flush()

    flush()
    return chunks


def iter_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for p in sorted(input_path.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".md", ".json", ".jsonl", ".txt"}:
            yield p


def migrate(input_path: Path, output_path: Path, fail_path: Path) -> dict:
    stats = {"ok": 0, "failed": 0, "records": 0}

    with output_path.open("w", encoding="utf-8") as out, fail_path.open("w", encoding="utf-8") as ferr:
        for p in iter_files(input_path):
            rel = str(p)
            try:
                text = read_text_safe(p)
                ext = p.suffix.lower()

                if ext == ".md":
                    for i, c in enumerate(chunk_markdown(text), 1):
                        out.write(json.dumps({"source": rel, "type": "markdown_chunk", "chunk_index": i, "content": c}, ensure_ascii=False) + "\n")
                        stats["records"] += 1
                elif ext == ".json":
                    out.write(json.dumps({"source": rel, "type": "json", "content": json.loads(text)}, ensure_ascii=False) + "\n")
                    stats["records"] += 1
                elif ext == ".jsonl":
                    for idx, line in enumerate(text.splitlines(), 1):
                        line = line.strip()
                        if not line:
                            continue
                        out.write(json.dumps({"source": rel, "type": "jsonl", "line": idx, "content": json.loads(line)}, ensure_ascii=False) + "\n")
                        stats["records"] += 1
                else:
                    out.write(json.dumps({"source": rel, "type": "text", "content": text}, ensure_ascii=False) + "\n")
                    stats["records"] += 1

                stats["ok"] += 1
            except Exception as e:
                stats["failed"] += 1
                ferr.write(json.dumps({"source": rel, "error": str(e)}, ensure_ascii=False) + "\n")

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Safe memory migration")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="migration_output.jsonl")
    ap.add_argument("--fail-log", default="migration_failures.jsonl")
    args = ap.parse_args()

    stats = migrate(Path(args.input), Path(args.output), Path(args.fail_log))
    print(json.dumps({"status": "done", **stats, "output": args.output, "fail_log": args.fail_log}, ensure_ascii=False))


if __name__ == "__main__":
    main()
