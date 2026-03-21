from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.config import settings
from app.services.vectorstore import _pack_meta


async def process_pending_writes(app):
    p = Path(settings.queue_file)
    if not p.exists():
        return

    lines = p.read_text(encoding="utf-8").splitlines()
    if not lines:
        return

    remain = []
    for line in lines:
        try:
            rec = json.loads(line)
            col = rec["collection"]
            mem_id = rec["id"]
            text = rec["text"]
            tags = rec.get("tags", [])
            meta = rec.get("meta", {})
            created = rec["created"]
            updated = rec["updated"]

            emb = await app.state.embedding.embed(text)
            md = _pack_meta(meta, tags, created, updated)
            # 异步补算采用 upsert 语义：不存在就 add，存在就 update
            row = app.state.vs.get(col, mem_id)
            if row:
                app.state.vs.update(col, mem_id, text=text, embedding=emb, metadata=md)
            else:
                app.state.vs.add(col, mem_id, text=text, embedding=emb, metadata=md)
        except Exception:
            remain.append(line)

    p.write_text("\n".join(remain) + ("\n" if remain else ""), encoding="utf-8")


async def queue_worker_loop(app):
    while True:
        try:
            await process_pending_writes(app)
        except Exception:
            pass
        await asyncio.sleep(5)
