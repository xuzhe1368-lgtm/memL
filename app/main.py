from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings, load_tenants
from app.middleware.auth import auth_middleware
from app.services.embedding import EmbeddingService
from app.services.vectorstore import VectorStore
from app.services.metrics import Metrics
from app.routers.memory import router as memory_router
from app.routers.admin import router as admin_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("memL")

app = FastAPI(title="memL", version="0.1.0")

# middlewares
app.middleware("http")(auth_middleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = rid
    request.app.state.metrics.inc("requests_total")
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        {
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "request_id": getattr(request.state, "request_id", None),
            },
        },
        status_code=422,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error rid=%s", getattr(request.state, "request_id", "-"))
    return JSONResponse(
        {
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "internal server error",
                "request_id": getattr(request.state, "request_id", None),
            },
        },
        status_code=500,
    )


@app.on_event("startup")
async def startup():
    app.state.tenants = load_tenants(settings.tenants_file)
    app.state.admin_token = settings.admin_token
    app.state.embedding = EmbeddingService()
    app.state.vs = VectorStore()
    app.state.metrics = Metrics()
    logger.info("memL started, tenants=%d", len(app.state.tenants))


@app.on_event("shutdown")
async def shutdown():
    await app.state.embedding.close()
    logger.info("memL stopped")


@app.get("/")
async def root():
    return {"ok": True, "service": "memL"}


@app.get("/health/live")
async def health_live():
    return {"ok": True}


@app.get("/health/ready")
async def health_ready():
    # 这里可继续增强：检查 embedding API 可达性
    return {"ok": True}


@app.get("/metrics")
async def metrics():
    return {"ok": True, "data": app.state.metrics.snapshot()}


@app.get('/ui')
async def ui_index():
    return FileResponse('app/ui/index.html')


@app.get('/ui/{asset}')
async def ui_assets(asset: str):
    return FileResponse(f'app/ui/{asset}')


app.include_router(memory_router)
app.include_router(admin_router)
