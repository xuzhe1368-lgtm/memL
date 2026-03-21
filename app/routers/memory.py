from __future__ import annotations

from fastapi import APIRouter, Request, Query, HTTPException
from uuid import uuid4
from datetime import datetime, timezone

from app.models import MemoryCreate, MemoryUpdate
from app.services.vectorstore import _pack_meta, _unpack_meta

router = APIRouter()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@router.post("/memory")
async def create_memory(payload: MemoryCreate, request: Request):
    tenant = request.state.tenant
    col = tenant["collection"]
    mem_id = f"m_{uuid4().hex[:12]}"
    ts = now_iso()

    embedding = await request.app.state.embedding.embed(payload.text)
    md = _pack_meta(payload.meta, payload.tags, ts, ts)
    request.app.state.vs.add(col, mem_id, payload.text, embedding, md)

    return {
        "ok": True,
        "data": {
            "id": mem_id,
            "text": payload.text,
            "tags": payload.tags,
            "meta": payload.meta,
            "created": ts,
            "updated": ts,
        },
    }


@router.get("/memory/{mem_id}")
async def get_memory(mem_id: str, request: Request):
    col = request.state.tenant["collection"]
    row = request.app.state.vs.get(col, mem_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    tags, meta, created, updated = _unpack_meta(row["metadata"])
    return {
        "ok": True,
        "data": {
            "id": row["id"],
            "text": row["text"],
            "tags": tags,
            "meta": meta,
            "created": created,
            "updated": updated,
        },
    }


@router.patch("/memory/{mem_id}")
async def update_memory(mem_id: str, payload: MemoryUpdate, request: Request):
    col = request.state.tenant["collection"]
    row = request.app.state.vs.get(col, mem_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    tags, meta, created, _updated = _unpack_meta(row["metadata"])
    text = row["text"]

    if payload.text is not None:
        text = payload.text
    if payload.tags is not None:
        tags = payload.tags
    if payload.meta is not None:
        meta = payload.meta

    updated = now_iso()
    md = _pack_meta(meta, tags, created, updated)

    new_embedding = None
    if payload.text is not None:
        new_embedding = await request.app.state.embedding.embed(text)

    request.app.state.vs.update(col, mem_id, text=text, embedding=new_embedding, metadata=md)

    return {
        "ok": True,
        "data": {
            "id": mem_id,
            "text": text,
            "tags": tags,
            "meta": meta,
            "created": created,
            "updated": updated,
        },
    }


@router.delete("/memory/{mem_id}")
async def delete_memory(mem_id: str, request: Request):
    col = request.state.tenant["collection"]
    request.app.state.vs.delete(col, mem_id)
    return {"ok": True}


@router.get("/memory")
async def search_memory(
    request: Request,
    q: str | None = None,
    tags: list[str] = Query(default=[]),  # 支持 ?tags=a&tags=b
    tag_mode: str = "any",
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    col = request.state.tenant["collection"]
    vs = request.app.state.vs

    def tag_ok(mem_tags: list[str]) -> bool:
        if not tags:
            return True
        if tag_mode == "all":
            return all(t in mem_tags for t in tags)
        return any(t in mem_tags for t in tags)

    out = []

    if q and q.strip():
        try:
            emb = await request.app.state.embedding.embed(q)
            raw = vs.query(col, emb, n_results=min(1000, offset + limit * 5))
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            mds = raw.get("metadatas", [[]])[0]
            dists = raw.get("distances", [[]])[0]

            for i in range(len(ids)):
                mtags, mmeta, created, updated = _unpack_meta(mds[i])
                if not tag_ok(mtags):
                    continue
                score = 1.0 / (1.0 + float(dists[i]))  # 简单归一化
                out.append({
                    "id": ids[i],
                    "text": docs[i],
                    "tags": mtags,
                    "meta": mmeta,
                    "created": created,
                    "updated": updated,
                    "score": round(score, 6),
                })
        except Exception:
            # 降级：embedding 不可用时，若有 tags 则走标签检索
            if not tags:
                raise HTTPException(status_code=503, detail="embedding unavailable")
            all_rows = vs.list_all(col)
            for i in range(len(all_rows["ids"])):
                mtags, mmeta, created, updated = _unpack_meta(all_rows["metadatas"][i])
                if not tag_ok(mtags):
                    continue
                out.append({
                    "id": all_rows["ids"][i],
                    "text": all_rows["documents"][i],
                    "tags": mtags,
                    "meta": mmeta,
                    "created": created,
                    "updated": updated,
                    "score": None,
                })
    else:
        all_rows = vs.list_all(col)
        for i in range(len(all_rows["ids"])):
            mtags, mmeta, created, updated = _unpack_meta(all_rows["metadatas"][i])
            if not tag_ok(mtags):
                continue
            out.append({
                "id": all_rows["ids"][i],
                "text": all_rows["documents"][i],
                "tags": mtags,
                "meta": mmeta,
                "created": created,
                "updated": updated,
                "score": None,
            })

    total = len(out)
    out = out[offset: offset + limit]
    return {"ok": True, "data": {"total": total, "results": out}}


@router.get("/stats")
async def stats(request: Request):
    col = request.state.tenant["collection"]
    total = request.app.state.vs.count(col)
    return {"ok": True, "data": {"total_memories": total}}
