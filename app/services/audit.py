from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings


def audit_log(action: str, actor: str, detail: dict):
    p = Path(settings.audit_log_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "action": action,
        "actor": actor,
        "detail": detail,
    }
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
