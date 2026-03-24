from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock

from app.config import settings


class IdempotencyStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        self.data = {}
        self.ttl_sec = max(60, int(getattr(settings, "idemp_ttl_sec", 7 * 24 * 3600)))
        self.max_entries = max(1000, int(getattr(settings, "idemp_max_entries", 20000)))
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        self._compact_locked(force=True)

    def _now(self) -> int:
        return int(time.time())

    def _entry_ts(self, value: dict) -> int:
        if not isinstance(value, dict):
            return 0
        ts = value.get("_ts")
        if isinstance(ts, (int, float)):
            return int(ts)
        return 0

    def _compact_locked(self, force: bool = False):
        now = self._now()
        # TTL 清理
        removed = 0
        for k in list(self.data.keys()):
            ts = self._entry_ts(self.data.get(k, {}))
            if ts and now - ts > self.ttl_sec:
                self.data.pop(k, None)
                removed += 1

        # 容量上限：按时间戳保留最新 N 条
        overflow = len(self.data) - self.max_entries
        if overflow > 0:
            ordered = sorted(
                self.data.items(),
                key=lambda kv: self._entry_ts(kv[1]) or 0,
                reverse=True,
            )
            self.data = dict(ordered[: self.max_entries])
            removed += max(0, overflow)

        if force or removed > 0:
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False), encoding="utf-8"
            )

    def get(self, key: str):
        with self.lock:
            v = self.data.get(key)
            if not v:
                return None
            ts = self._entry_ts(v)
            if ts and self._now() - ts > self.ttl_sec:
                self.data.pop(key, None)
                self.path.write_text(
                    json.dumps(self.data, ensure_ascii=False), encoding="utf-8"
                )
                return None
            return v

    def set(self, key: str, value: dict):
        with self.lock:
            stored = dict(value or {})
            stored.setdefault("_ts", self._now())
            self.data[key] = stored
            self._compact_locked(force=True)


class TenantLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.lock = Lock()
        self.bucket = {}

    def allow(self, tenant_name: str) -> bool:
        now = int(time.time())
        slot = now // 60
        key = f"{tenant_name}:{slot}"
        with self.lock:
            count = self.bucket.get(key, 0)
            if count >= self.per_minute:
                return False
            self.bucket[key] = count + 1
            # lazy cleanup
            old = [k for k in self.bucket.keys() if not k.endswith(f":{slot}")]
            for k in old[:200]:
                self.bucket.pop(k, None)
            return True


def queue_append(record: dict):
    p = Path(settings.queue_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

