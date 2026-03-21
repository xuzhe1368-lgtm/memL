from __future__ import annotations

from fastapi import APIRouter, Request, Query, HTTPException
from uuid import uuid4
from datetime import datetime, timezone

from app.models import MemoryCreate, MemoryUpdate
from app.services.vectorstore import _pack_meta, _unpack_meta
from app.config import settings

router = APIRouter()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@router.post("/memory")
async def create_memory(payload: MemoryCreate, request: Request):
    tenant = request.state.tenant
    col = tenant["collection"]
    mem_id = f"m_{uuid4().hex[:12]}"
    ts = now_iso()

    try:
        embedding = await request.app.state.embedding.embed(payload.text)
    except Exception:
        request.app.state.metrics.inc("embedding_fail_total")
        raise

    # 去重：与最相近的一条做阈值比较，命中则直接返回已有记录
    if settings.dedup_enabled:
        raw = request.app.state.vs.query(col, embedding, n_results=1)
        ids = raw.get("ids", [[]])[0]
        docs = raw.get("documents", [[]])[0]
        mds = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]
        if ids:
            score = 1.0 / (1.0 + float(dists[0]))
            if score >= settings.dedup_threshold:
                request.app.state.metrics.inc("dedup_hits_total")
                tags, meta, created, updated = _unpack_meta(mds[0])
                return {
                    "ok": True,
                    "data": {
                        "id": ids[0],
                        "text": docs[0],
                        "tags": tags,
                        "meta": meta,
                        "created": created,
                        "updated": updated,
                        "dedup": True,
                        "score": round(score, 6),
                    },
                }

    md = _pack_meta(payload.meta, payload.tags, ts, ts)
    request.app.state.vs.add(col, mem_id, payload.text, embedding, md)
    request.app.state.metrics.inc("memory_writes_total")

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
    request.app.state.metrics.inc("memory_search_total")

    def tag_ok(mem_tags: list[str]) -> bool:
        if not tags:
            return True
        if tag_mode == "all":
            return all(t in mem_tags for t in tags)
        return any(t in mem_tags for t in tags)

    out = []

    if q and q.strip():
        ql = q.lower().strip()
        try:
            emb = await request.app.state.embedding.embed(q)
            raw = vs.query(col, emb, n_results=min(1000, max(50, offset + limit * 8)))
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            mds = raw.get("metadatas", [[]])[0]
            dists = raw.get("distances", [[]])[0]

            alpha = max(0.0, min(1.0, settings.hybrid_alpha))
            beta = 1.0 - alpha
            for i in range(len(ids)):
                mtags, mmeta, created, updated = _unpack_meta(mds[i])
                if not tag_ok(mtags):
                    continue
                vec_score = 1.0 / (1.0 + float(dists[i]))
                kw_score = 1.0 if ql in (docs[i] or "").lower() else 0.0
                hybrid = alpha * vec_score + beta * kw_score
                out.append({
                    "id": ids[i],
                    "text": docs[i],
                    "tags": mtags,
                    "meta": mmeta,
                    "created": created,
                    "updated": updated,
                    "score": round(hybrid, 6),
                    "_vec": vec_score,
                    "_kw": kw_score,
                })
            out.sort(key=lambda x: x["score"], reverse=True)
        except Exception:
            request.app.state.metrics.inc("embedding_fail_total")
            # 降级：embedding 不可用时，走关键词 + 标签过滤
            all_rows = vs.list_all(col)
            for i in range(len(all_rows["ids"])):
                doc = all_rows["documents"][i]
                if ql not in (doc or "").lower():
                    continue
                mtags, mmeta, created, updated = _unpack_meta(all_rows["metadatas"][i])
                if not tag_ok(mtags):
                    continue
                out.append({
                    "id": all_rows["ids"][i],
                    "text": doc,
                    "tags": mtags,
                    "meta": mmeta,
                    "created": created,
                    "updated": updated,
                    "score": 1.0,
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
    for x in out:
        x.pop("_vec", None)
        x.pop("_kw", None)
    return {"ok": True, "data": {"total": total, "results": out}}


@router.get("/stats")
async def stats(request: Request):
    col = request.state.tenant["collection"]
    total = request.app.state.vs.count(col)
    return {"ok": True, "data": {"total_memories": total}}
