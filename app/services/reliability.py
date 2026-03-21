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
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    def get(self, key: str):
        with self.lock:
            return self.data.get(key)

    def set(self, key: str, value: dict):
        with self.lock:
            self.data[key] = value
            self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")


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
