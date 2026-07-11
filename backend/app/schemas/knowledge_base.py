from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    product_name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    product_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    is_enabled: bool | None = None


class KnowledgeBaseRecord(BaseModel):
    id: str
    name: str
    product_name: str
    description: str = ""
    is_enabled: bool = True
    created_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    knowledge_bases: list[KnowledgeBaseRecord]
