from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

EXEMPT_PATHS = {"/", "/health/live", "/health/ready", "/docs", "/openapi.json", "/metrics"}


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in EXEMPT_PATHS or path == '/ui' or path.startswith('/ui/'):
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Missing bearer token"}},
            status_code=401,
        )

    token = auth[7:]

    # 管理接口：使用 MEML_ADMIN_TOKEN
    if path.startswith("/admin/"):
        admin_token = getattr(request.app.state, "admin_token", "")
        if not admin_token or token != admin_token:
            return JSONResponse(
                {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid admin token"}},
                status_code=401,
            )
        request.state.is_admin = True
        return await call_next(request)

    tenant = request.app.state.tenants.get(token)
    if not tenant:
        return JSONResponse(
            {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid token"}},
            status_code=401,
        )

    if tenant.get("enabled", True) is False:
        return JSONResponse(
            {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Tenant disabled"}},
            status_code=401,
        )

    request.state.token = token
    request.state.tenant = tenant
    return await call_next(request)
