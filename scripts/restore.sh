#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${1:-}"
TARGET_DIR="${2:-/opt/memL/data/chromadb}"

if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
  echo "Usage: $0 <backup.tar.gz> [target_dir]" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
PARENT="$(dirname "$TARGET_DIR")"
BASE="$(basename "$TARGET_DIR")"

rm -rf "$TARGET_DIR"
mkdir -p "$PARENT"
tar -C "$PARENT" -xzf "$ARCHIVE"

if [[ ! -d "$TARGET_DIR" ]]; then
  # archive may contain a different base dir; best-effort move
  CANDIDATE=$(tar -tzf "$ARCHIVE" | head -n1 | cut -d/ -f1)
  if [[ -n "$CANDIDATE" && -d "$PARENT/$CANDIDATE" && "$CANDIDATE" != "$BASE" ]]; then
    mv "$PARENT/$CANDIDATE" "$TARGET_DIR"
  fi
fi

echo "restored to: $TARGET_DIR"
