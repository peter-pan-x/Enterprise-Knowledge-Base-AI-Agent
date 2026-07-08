from pydantic import BaseModel


class RagSource(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    chunk_index: int
    page_number: int | None = None
    score: float
    preview: str


class RagSearchRequest(BaseModel):
    query: str
    top_k: int | None = None


class RagSearchResponse(BaseModel):
    sources: list[RagSource]


class RagReindexResponse(BaseModel):
    indexed_documents: int
    indexed_chunks: int


class RagLogEntry(BaseModel):
    id: str
    query: str
    top_k: int
    source_count: int
    sources: list[RagSource]
    created_at: str


class RagLogListResponse(BaseModel):
    logs: list[RagLogEntry]
