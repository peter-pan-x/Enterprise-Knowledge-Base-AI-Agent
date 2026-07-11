from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.schemas.document import DocumentListResponse, DocumentRecord, DocumentTextPreview
from app.services.document_service import (
    DocumentServiceError,
    delete_document,
    get_document_preview,
    list_documents,
    reprocess_document,
    save_uploaded_document,
    set_document_enabled,
)
from app.services.auth_service import CurrentUser, require_admin

router = APIRouter()


class DocumentEnabledRequest(BaseModel):
    is_enabled: bool


@router.get("", response_model=DocumentListResponse)
async def documents(_: CurrentUser = Depends(require_admin)) -> DocumentListResponse:
    return DocumentListResponse(documents=list_documents())


@router.post("", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...), knowledge_base_id: str = Form("default"), category: str = Form("general"),
    _: CurrentUser = Depends(require_admin),
) -> DocumentRecord:
    try:
        return await save_uploaded_document(file, knowledge_base_id, category)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{document_id}/preview", response_model=DocumentTextPreview)
async def document_preview(document_id: str, _: CurrentUser = Depends(require_admin)) -> DocumentTextPreview:
    try:
        document, preview = get_document_preview(document_id)
        return DocumentTextPreview(document=document, preview=preview)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{document_id}/reprocess", response_model=DocumentRecord)
def retry_document_processing(document_id: str, _: CurrentUser = Depends(require_admin)) -> DocumentRecord:
    try:
        return reprocess_document(document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{document_id}/enabled", response_model=DocumentRecord)
def set_enabled(document_id: str, request: DocumentEnabledRequest, _: CurrentUser = Depends(require_admin)) -> DocumentRecord:
    try:
        return set_document_enabled(document_id, request.is_enabled)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(document_id: str, _: CurrentUser = Depends(require_admin)) -> None:
    try:
        delete_document(document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
