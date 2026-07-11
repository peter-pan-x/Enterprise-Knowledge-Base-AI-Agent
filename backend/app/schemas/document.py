from datetime import datetime
from typing import Literal

from pydantic import BaseModel


DocumentStatus = Literal["processed", "failed"]
DocumentIndexStatus = Literal["not_indexed", "indexed", "failed"]


class DocumentRecord(BaseModel):
    id: str
    filename: str
    content_type: str
    status: DocumentStatus
    size_bytes: int
    text_length: int
    created_at: datetime
    error_message: str | None = None
    index_status: DocumentIndexStatus = "not_indexed"
    indexed_chunks: int = 0
    index_error_message: str | None = None
    is_enabled: bool = True
    knowledge_base_id: str = "default"
    category: str = "general"


class DocumentListResponse(BaseModel):
    documents: list[DocumentRecord]


class DocumentTextPreview(BaseModel):
    document: DocumentRecord
    preview: str
