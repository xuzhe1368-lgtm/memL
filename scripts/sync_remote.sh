#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/sync_remote.sh root@192.168.2.240 /root/.openclaw/workspace/projects/memL
#
# Safe sync for memL code updates:
# - keeps remote runtime env (.env) untouched
# - keeps remote venv untouched
# - keeps runtime data untouched

TARGET="${1:-root@192.168.2.240}"
SRC="${2:-$(pwd)}"
DEST="/opt/memL/"

TS="$(date +%Y%m%d-%H%M%S)"
ssh "$TARGET" "cp -a /opt/memL /opt/memL.bak.$TS"

rsync -az --delete \
  --exclude '.env' \
  --exclude 'venv/' \
  --exclude 'data/' \
  --exclude 'backups/' \
  -e "ssh" \
  "$SRC/" "$TARGET:$DEST"

ssh "$TARGET" 'chown -R meml:meml /opt/memL && systemctl restart memL && sleep 1 && systemctl is-active memL'

echo "sync complete -> $TARGET:$DEST"
