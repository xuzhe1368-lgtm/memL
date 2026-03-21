from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import time
from pathlib import Path

from app.config import settings


@dataclass
class Metrics:
    lock: Lock = field(default_factory=Lock)
    started_at: float = field(default_factory=time)
    requests_total: int = 0
    memory_writes_total: int = 0
    memory_search_total: int = 0
    dedup_hits_total: int = 0
    embedding_fail_total: int = 0

    def inc(self, field_name: str, n: int = 1):
        with self.lock:
            setattr(self, field_name, getattr(self, field_name) + n)

    def snapshot(self) -> dict:
        qlen = 0
        qf = Path(settings.queue_file)
        if qf.exists():
            try:
                qlen = sum(1 for _ in qf.open('r', encoding='utf-8'))
            except Exception:
                qlen = 0

        with self.lock:
            return {
                "uptime_sec": int(time() - self.started_at),
                "requests_total": self.requests_total,
                "memory_writes_total": self.memory_writes_total,
                "memory_search_total": self.memory_search_total,
                "dedup_hits_total": self.dedup_hits_total,
                "embedding_fail_total": self.embedding_fail_total,
                "pending_queue_size": qlen,
            }
