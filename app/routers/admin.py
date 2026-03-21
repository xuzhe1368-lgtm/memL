from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.config import settings, load_tenants, save_tenants
from app.services.audit import audit_log

router = APIRouter(prefix="/admin", tags=["admin"])


class TenantUpsert(BaseModel):
    token: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)
    collection: str = Field(..., min_length=1)
    role: Literal['viewer','editor','admin'] = 'editor'
    enabled: bool = True


@router.get("/tenants")
async def list_tenants(request: Request):
    out = []
    for token, t in request.app.state.tenants.items():
        out.append({
            "token_prefix": token[:6] + "***",
            "name": t.get("name", ""),
            "collection": t.get("collection", ""),
            "role": t.get("role", "editor"),
            "enabled": bool(t.get("enabled", True)),
        })
    return {"ok": True, "data": {"total": len(out), "tenants": out}}


@router.post("/tenants")
async def upsert_tenant(payload: TenantUpsert, request: Request):
    tenants = request.app.state.tenants
    tenants[payload.token] = {
        "name": payload.name,
        "collection": payload.collection,
        "role": payload.role,
        "enabled": payload.enabled,
    }
    save_tenants(settings.tenants_file, tenants)
    audit_log(
        action="tenant.upsert",
        actor="admin",
        detail={
            "token_prefix": payload.token[:6] + "***",
            "name": payload.name,
            "collection": payload.collection,
            "role": payload.role,
            "enabled": payload.enabled,
        },
    )
    return {"ok": True}


@router.post("/tenants/{token}/disable")
async def disable_tenant(token: str, request: Request):
    tenants = request.app.state.tenants
    if token not in tenants:
        raise HTTPException(status_code=404, detail="tenant token not found")
    cur = tenants[token]
    cur["enabled"] = False
    save_tenants(settings.tenants_file, tenants)
    audit_log(
        action="tenant.disable",
        actor="admin",
        detail={
            "token_prefix": token[:6] + "***",
            "name": cur.get("name", ""),
            "collection": cur.get("collection", ""),
        },
    )
    return {"ok": True}


@router.get('/audit')
async def get_audit(limit: int = 100):
    from pathlib import Path
    p = Path(settings.audit_log_file)
    if not p.exists():
        return {"ok": True, "data": {"total": 0, "records": []}}
    lines = p.read_text(encoding='utf-8').splitlines()[-max(1, min(limit, 1000)):]
    out = []
    import json
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return {"ok": True, "data": {"total": len(out), "records": out}}
