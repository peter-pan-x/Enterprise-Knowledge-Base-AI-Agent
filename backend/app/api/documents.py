from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.document import DocumentListResponse, DocumentRecord, DocumentTextPreview
from app.services.document_service import (
    DocumentServiceError,
    delete_document,
    get_document_preview,
    list_documents,
    save_uploaded_document,
)

router = APIRouter()


@router.get("", response_model=DocumentListResponse)
async def documents() -> DocumentListResponse:
    return DocumentListResponse(documents=list_documents())


@router.post("", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)) -> DocumentRecord:
    try:
        return await save_uploaded_document(file)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{document_id}/preview", response_model=DocumentTextPreview)
async def document_preview(document_id: str) -> DocumentTextPreview:
    try:
        document, preview = get_document_preview(document_id)
        return DocumentTextPreview(document=document, preview=preview)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(document_id: str) -> None:
    try:
        delete_document(document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
