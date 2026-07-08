from fastapi import APIRouter

from app.schemas.rag import RagLogListResponse, RagReindexResponse, RagSearchRequest, RagSearchResponse
from app.services.rag_service import list_rag_logs, reindex_all_documents, search_knowledge_base

router = APIRouter()


@router.post("/search", response_model=RagSearchResponse)
async def rag_search(request: RagSearchRequest) -> RagSearchResponse:
    return RagSearchResponse(sources=search_knowledge_base(request.query, request.top_k))


@router.post("/reindex", response_model=RagReindexResponse)
async def rag_reindex() -> RagReindexResponse:
    indexed_documents, indexed_chunks = reindex_all_documents()
    return RagReindexResponse(
        indexed_documents=indexed_documents,
        indexed_chunks=indexed_chunks,
    )


@router.get("/logs", response_model=RagLogListResponse)
async def rag_logs() -> RagLogListResponse:
    return RagLogListResponse(logs=list_rag_logs())
