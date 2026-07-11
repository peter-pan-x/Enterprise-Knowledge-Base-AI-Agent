import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.customer_service import router as customer_service_router
from app.api.documents import router as documents_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.rag import router as rag_router
from app.api.tools import router as tools_router
from app.core.config import settings
from app.services.auth_service import initialize_auth_storage
from app.services.document_service import initialize_document_storage
from app.services.customer_service import initialize_customer_storage
from app.services.audit_service import initialize_audit_storage, record_audit_event

app = FastAPI(title=settings.app_name)
if settings.app_env.lower() in {"production", "prod"} and settings.auth_secret == "development-only-change-me":
    raise RuntimeError("AUTH_SECRET must be configured outside local development")
initialize_auth_storage()
initialize_document_storage()
initialize_customer_storage()
initialize_audit_storage()

_RATE_WINDOWS: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_and_audit(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _RATE_WINDOWS[client]
    while window and now - window[0] >= 60:
        window.popleft()
    if len(window) >= settings.api_rate_limit_per_minute:
        record_audit_event("rate_limited", request.url.path, 429, client)
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
    window.append(now)
    response = await call_next(request)
    if request.method not in {"GET", "OPTIONS"} or response.status_code >= 400:
        record_audit_event("api_request", request.url.path, response.status_code, client, request.method)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(knowledge_bases_router, prefix="/api/knowledge-bases", tags=["knowledge-bases"])
app.include_router(rag_router, prefix="/api/rag", tags=["rag"])
app.include_router(customer_service_router, prefix="/api/customer-service", tags=["customer-service"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(tools_router, prefix="/api/tools", tags=["tools"])
