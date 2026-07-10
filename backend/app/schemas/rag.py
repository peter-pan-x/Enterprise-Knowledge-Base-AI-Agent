from pydantic import BaseModel, Field, field_validator


class RagSource(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    chunk_index: int
    page_number: int | None = None
    score: float
    preview: str
    # Full chunk text is only used to build the LLM prompt. It must not be
    # returned to the browser or persisted in the lightweight RAG log.
    content: str = Field(default="", exclude=True)


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query 不能为空")
        return value


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
