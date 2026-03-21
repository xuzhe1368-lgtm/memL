#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="${1:-/opt/memL/data/chromadb}"
OUT_DIR="${2:-/opt/memL/backups}"
TS="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$OUT_DIR/meml-backup-$TS.tar.gz"

mkdir -p "$OUT_DIR"
if [[ ! -d "$SRC_DIR" ]]; then
  echo "source dir not found: $SRC_DIR" >&2
  exit 1
fi

tar -C "$(dirname "$SRC_DIR")" -czf "$ARCHIVE" "$(basename "$SRC_DIR")"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"

echo "backup: $ARCHIVE"
echo "checksum: $ARCHIVE.sha256"
