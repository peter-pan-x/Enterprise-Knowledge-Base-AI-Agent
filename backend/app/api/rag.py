from fastapi import APIRouter, Depends

from app.schemas.rag import RagLogListResponse, RagReindexResponse, RagSearchRequest, RagSearchResponse
from app.services.rag_service import list_rag_logs, reindex_all_documents, search_knowledge_base
from app.services.auth_service import CurrentUser, get_current_user, require_admin

router = APIRouter()


@router.post("/search", response_model=RagSearchResponse)
async def rag_search(request: RagSearchRequest, _: CurrentUser = Depends(get_current_user)) -> RagSearchResponse:
    return RagSearchResponse(sources=search_knowledge_base(request.query, request.top_k, request.knowledge_base_id, request.category))


@router.post("/reindex", response_model=RagReindexResponse)
async def rag_reindex(_: CurrentUser = Depends(require_admin)) -> RagReindexResponse:
    indexed_documents, indexed_chunks = reindex_all_documents()
    return RagReindexResponse(
        indexed_documents=indexed_documents,
        indexed_chunks=indexed_chunks,
    )


@router.get("/logs", response_model=RagLogListResponse)
async def rag_logs(_: CurrentUser = Depends(require_admin)) -> RagLogListResponse:
    return RagLogListResponse(logs=list_rag_logs())
