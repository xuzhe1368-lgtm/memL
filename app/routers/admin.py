from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from app.config import settings, load_tenants, save_tenants

router = APIRouter(prefix="/admin", tags=["admin"])


class TenantUpsert(BaseModel):
    token: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)
    collection: str = Field(..., min_length=1)
    enabled: bool = True


@router.get("/tenants")
async def list_tenants(request: Request):
    out = []
    for token, t in request.app.state.tenants.items():
        out.append({
            "token_prefix": token[:6] + "***",
            "name": t.get("name", ""),
            "collection": t.get("collection", ""),
            "enabled": bool(t.get("enabled", True)),
        })
    return {"ok": True, "data": {"total": len(out), "tenants": out}}


@router.post("/tenants")
async def upsert_tenant(payload: TenantUpsert, request: Request):
    tenants = request.app.state.tenants
    tenants[payload.token] = {
        "name": payload.name,
        "collection": payload.collection,
        "enabled": payload.enabled,
    }
    save_tenants(settings.tenants_file, tenants)
    return {"ok": True}


@router.post("/tenants/{token}/disable")
async def disable_tenant(token: str, request: Request):
    tenants = request.app.state.tenants
    if token not in tenants:
        raise HTTPException(status_code=404, detail="tenant token not found")
    cur = tenants[token]
    cur["enabled"] = False
    save_tenants(settings.tenants_file, tenants)
    return {"ok": True}
