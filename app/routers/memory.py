from __future__ import annotations

from fastapi import APIRouter, Request, Query, HTTPException
from uuid import uuid4
from datetime import datetime, timezone
import hashlib
import math

from app.models import MemoryCreate, MemoryUpdate, MilestoneCreate
from app.services.vectorstore import _pack_meta, _unpack_meta
from app.services.reliability import queue_append
from app.config import settings

router = APIRouter()


def _require_write_role(request: Request):
    role = getattr(request.state, 'role', 'editor')
    if role not in ('editor', 'admin'):
        raise HTTPException(status_code=403, detail='forbidden: write requires editor/admin role')


def _normalize_tags(tags: list[str], *, allow_fill: bool = True) -> list[str]:
    t = [x.strip() for x in tags if x and x.strip()]
    t = list(dict.fromkeys(t))
    has_type = any(x.startswith('type:') for x in t)
    has_source = any(x.startswith('source:') for x in t)
    has_scope = any(x.startswith('scope:') for x in t)
    if allow_fill:
        if not has_type:
            t.insert(0, 'type:project')
        if not has_source:
            t.append('source:runtime')
        if not has_scope:
            t.append('scope:personal')
    else:
        if not (has_type and has_source and has_scope):
            raise HTTPException(status_code=422, detail='tags must include type:/source:/scope:')
    return t


def _infer_importance(text: str, tags: list[str], meta: dict) -> float:
    if 'importance_score' in meta:
        try:
            v = float(meta.get('importance_score'))
            return max(0.0, min(1.0, v))
        except Exception:
            pass
    s = (text or '').lower()
    score = 0.35
    if any(k in s for k in ['决定','决策','milestone','里程碑','上线','发布']):
        score += 0.35
    if any(k in s for k in ['偏好','preference','习惯']):
        score += 0.2
    if any(k.startswith('type:') and k in ['type:ops', 'type:project'] for k in tags):
        score += 0.1
    return max(0.0, min(1.0, score))


def _tenant_collections(tenant: dict) -> tuple[str, str, str]:
    base = tenant["collection"]
    short_col = f"{base}_short"
    long_col = f"{base}_long"
    legacy_col = base
    return short_col, long_col, legacy_col


def _all_read_cols(tenant: dict) -> list[str]:
    s, l, b = _tenant_collections(tenant)
    # 兼容历史数据：继续读取 legacy base collection
    return [s, l, b]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@router.post("/memory")
async def create_memory(payload: MemoryCreate, request: Request):
    _require_write_role(request)
    tenant = request.state.tenant
    tenant_name = tenant.get("name", tenant.get("collection", "default"))
    short_col, long_col, base_col = _tenant_collections(tenant)
    ts = now_iso()

    # 强制标准标签体系
    tags = _normalize_tags(payload.tags, allow_fill=True)

    # 高价值判定（可显式传 importance_score 覆盖）
    importance = payload.importance_score if payload.importance_score is not None else _infer_importance(payload.text, tags, payload.meta)
    promote = bool(payload.promote_to_longterm or importance >= settings.importance_longterm_threshold)

    # tenant 配额（条数）- short + long + legacy 总和
    total_count = request.app.state.vs.count(short_col) + request.app.state.vs.count(long_col) + request.app.state.vs.count(base_col)
    if total_count >= settings.tenant_max_memories:
        raise HTTPException(status_code=429, detail="tenant memory quota exceeded")

    # tenant 限流（每分钟写入）
    if not request.app.state.limiter.allow(tenant_name):
        raise HTTPException(status_code=429, detail="tenant write rate limit exceeded")

    # 幂等 key（支持 header 覆盖）
    idk = request.headers.get("Idempotency-Key")
    if not idk:
        raw = f"{tenant_name}|{payload.text}|{','.join(sorted(tags))}"
        idk = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    hit = request.app.state.idemp.get(idk)
    if hit:
        return {"ok": True, "data": {**hit, "idempotent": True}}

    mem_id = f"m_{uuid4().hex[:12]}"
    embedding = None
    async_mode = False
    try:
        embedding = await request.app.state.embedding.embed(payload.text)
    except Exception:
        request.app.state.metrics.inc("embedding_fail_total")
        async_mode = True

    # 去重：仅在拿到 embedding 时执行
    if settings.dedup_enabled and embedding is not None:
        found = None
        for c in _all_read_cols(tenant):
            raw = request.app.state.vs.query(c, embedding, n_results=1)
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            mds = raw.get("metadatas", [[]])[0]
            dists = raw.get("distances", [[]])[0]
            if ids:
                score = 1.0 / (1.0 + float(dists[0]))
                if (found is None) or (score > found[0]):
                    found = (score, ids[0], docs[0], mds[0])
        if found and found[0] >= settings.dedup_threshold:
            request.app.state.metrics.inc("dedup_hits_total")
            score, fid, fdoc, fmd = found
            tags, meta, created, updated = _unpack_meta(fmd)
            out = {
                "id": fid,
                "text": fdoc,
                "tags": tags,
                "meta": meta,
                "created": created,
                "updated": updated,
                "dedup": True,
                "score": round(score, 6),
            }
            request.app.state.idemp.set(idk, out)
            return {"ok": True, "data": out}

    rich_meta = {**payload.meta, "importance_score": importance, "promoted": promote}
    md = _pack_meta(rich_meta, tags, ts, ts)
    target_col = long_col if promote else short_col

    if async_mode:
        # 先排队，避免 add() 触发 Chroma 默认 embedding 回退
        queue_append({
            "collection": target_col,
            "id": mem_id,
            "text": payload.text,
            "tags": tags,
            "meta": {**payload.meta, "importance_score": importance, "promoted": promote},
            "created": ts,
            "updated": ts,
        })
    else:
        request.app.state.vs.add(target_col, mem_id, payload.text, embedding, md)

    request.app.state.metrics.inc("memory_writes_total")
    out = {
        "id": mem_id,
        "text": payload.text,
        "tags": tags,
        "meta": {**payload.meta, "importance_score": importance, "promoted": promote},
        "created": ts,
        "updated": ts,
        "embedding_pending": async_mode,
    }
    request.app.state.idemp.set(idk, out)
    return {"ok": True, "data": out}


@router.get("/memory/{mem_id}")
async def get_memory(mem_id: str, request: Request):
    row = None
    for c in _all_read_cols(request.state.tenant):
        row = request.app.state.vs.get(c, mem_id)
        if row:
            break
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
    _require_write_role(request)
    col = None
    row = None
    for c in _all_read_cols(request.state.tenant):
        row = request.app.state.vs.get(c, mem_id)
        if row:
            col = c
            break
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    tags, meta, created, _updated = _unpack_meta(row["metadata"])
    text = row["text"]
    text_changed = False

    if payload.text is not None:
        text = payload.text
        text_changed = True
    if payload.tags is not None:
        tags = payload.tags
    if payload.meta is not None:
        meta = payload.meta

    updated = now_iso()
    md = _pack_meta(meta, tags, created, updated)

    new_embedding = None
    text_for_update = None
    if text_changed:
        text_for_update = text
        new_embedding = await request.app.state.embedding.embed(text)

    request.app.state.vs.update(col, mem_id, text=text_for_update, embedding=new_embedding, metadata=md)

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
    _require_write_role(request)
    deleted = False
    for c in _all_read_cols(request.state.tenant):
        try:
            request.app.state.vs.delete(c, mem_id)
            deleted = True
        except Exception:
            pass
    if not deleted:
        raise HTTPException(status_code=404, detail='not found')
    return {"ok": True}


@router.get("/memory")
async def search_memory(
    request: Request,
    q: str | None = None,
    tags: list[str] = Query(default=[]),  # 支持 ?tags=a&tags=b
    tag_mode: str = "any",
    explain: bool = Query(default=False),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    tenant = request.state.tenant
    cols = _all_read_cols(tenant)
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
            alpha = max(0.0, min(1.0, settings.hybrid_alpha))
            beta = 1.0 - alpha
            for col in cols:
                raw = vs.query(col, emb, n_results=min(1000, max(50, offset + limit * 8)))
                ids = raw.get("ids", [[]])[0]
                docs = raw.get("documents", [[]])[0]
                mds = raw.get("metadatas", [[]])[0]
                dists = raw.get("distances", [[]])[0]

                for i in range(len(ids)):
                    mtags, mmeta, created, updated = _unpack_meta(mds[i])
                    if not tag_ok(mtags):
                        continue
                    vec_score = 1.0 / (1.0 + float(dists[i]))
                    kw_score = 1.0 if ql in (docs[i] or "").lower() else 0.0

                    # 时间衰减：30 天半衰期
                    recency = 1.0
                    try:
                        if updated:
                            s = updated.replace('Z', '+00:00')
                            ts = datetime.fromisoformat(s)
                            age_days = max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0)
                            recency = math.exp(-age_days / 30.0)
                    except Exception:
                        recency = 1.0

                    # 标签加权：命中筛选标签则加分
                    tag_boost = 1.0
                    if tags:
                        hit = sum(1 for t in tags if t in mtags)
                        tag_boost = 1.0 + min(0.3, 0.1 * hit)

                    hybrid = (alpha * vec_score + beta * kw_score) * recency * tag_boost
                    item = {
                        "id": ids[i],
                        "text": docs[i],
                        "tags": mtags,
                        "meta": mmeta,
                        "created": created,
                        "updated": updated,
                        "score": round(hybrid, 6),
                    }
                    if explain:
                        item["explain"] = {
                            "vec_score": round(vec_score, 6),
                            "kw_score": round(kw_score, 6),
                            "recency": round(recency, 6),
                            "tag_boost": round(tag_boost, 6),
                            "alpha": round(alpha, 3),
                            "beta": round(beta, 3),
                        }
                    out.append(item)
            # 同 id 去重（跨 short/long/legacy）
            best = {}
            for it in out:
                bid = it['id']
                if bid not in best or (it.get('score') or 0) > (best[bid].get('score') or 0):
                    best[bid] = it
            out = list(best.values())
            out.sort(key=lambda x: x["score"], reverse=True)
        except Exception:
            request.app.state.metrics.inc("embedding_fail_total")
            # 降级：embedding 不可用时，走关键词 + 标签过滤
            for col in cols:
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
        for col in cols:
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
        # 跨仓同 id 去重
        uniq = {}
        for it in out:
            uniq[it['id']] = it
        out = list(uniq.values())

    total = len(out)
    out = out[offset: offset + limit]
    return {"ok": True, "data": {"total": total, "results": out}}


@router.post('/memory/milestone')
async def create_milestone(payload: MilestoneCreate, request: Request):
    _require_write_role(request)
    text = f"[Milestone] project={payload.project}; stage={payload.stage}; summary={payload.summary}"
    if payload.next_step:
        text += f"; next={payload.next_step}"

    tags = ['type:milestone', 'source:runtime', 'scope:personal', f"project:{payload.project}"] + payload.tags

    # 直接复用 create_memory 逻辑
    mc = MemoryCreate(
        text=text,
        tags=tags,
        meta={"project": payload.project, "stage": payload.stage, "next_step": payload.next_step},
        importance_score=0.95,
        promote_to_longterm=True,
    )
    return await create_memory(mc, request)


@router.get("/stats")
async def stats(request: Request):
    tenant = request.state.tenant
    short_col, long_col, base_col = _tenant_collections(tenant)
    short_total = request.app.state.vs.count(short_col)
    long_total = request.app.state.vs.count(long_col)
    legacy_total = request.app.state.vs.count(base_col)
    return {"ok": True, "data": {
        "total_memories": short_total + long_total + legacy_total,
        "short_term": short_total,
        "long_term": long_total,
        "legacy": legacy_total,
    }}
