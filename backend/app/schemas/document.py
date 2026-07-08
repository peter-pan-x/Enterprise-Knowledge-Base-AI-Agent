from datetime import datetime
from typing import Literal

from pydantic import BaseModel


DocumentStatus = Literal["processed", "failed"]


class DocumentRecord(BaseModel):
    id: str
    filename: str
    content_type: str
    status: DocumentStatus
    size_bytes: int
    text_length: int
    created_at: datetime
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentRecord]


class DocumentTextPreview(BaseModel):
    document: DocumentRecord
    preview: str
