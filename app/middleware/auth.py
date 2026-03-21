from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

EXEMPT_PATHS = {"/", "/health/live", "/health/ready", "/docs", "/openapi.json"}


async def auth_middleware(request: Request, call_next):
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Missing bearer token"}},
            status_code=401,
        )

    token = auth[7:]
    tenant = request.app.state.tenants.get(token)
    if not tenant:
        return JSONResponse(
            {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid token"}},
            status_code=401,
        )

    request.state.token = token
    request.state.tenant = tenant
    return await call_next(request)
