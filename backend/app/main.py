from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.rag import router as rag_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)

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
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(rag_router, prefix="/api/rag", tags=["rag"])
