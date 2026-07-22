from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseListResponse, KnowledgeBaseRecord, KnowledgeBaseUpdate
from app.services.auth_service import CurrentUser, require_admin
from app.services.document_service import (
    DocumentServiceError, create_knowledge_base, delete_knowledge_base, list_knowledge_bases, update_knowledge_base,
)

router = APIRouter()


@router.get("", response_model=KnowledgeBaseListResponse)
def list_items(_: CurrentUser = Depends(require_admin)) -> KnowledgeBaseListResponse:
    return KnowledgeBaseListResponse(knowledge_bases=list_knowledge_bases())


@router.post("", response_model=KnowledgeBaseRecord, status_code=status.HTTP_201_CREATED)
def create_item(request: KnowledgeBaseCreate, _: CurrentUser = Depends(require_admin)) -> KnowledgeBaseRecord:
    return create_knowledge_base(request)


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseRecord)
def update_item(knowledge_base_id: str, request: KnowledgeBaseUpdate, _: CurrentUser = Depends(require_admin)) -> KnowledgeBaseRecord:
    try:
        return update_knowledge_base(knowledge_base_id, request)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(knowledge_base_id: str, _: CurrentUser = Depends(require_admin)) -> None:
    try:
        delete_knowledge_base(knowledge_base_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
