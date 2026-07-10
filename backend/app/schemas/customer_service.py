from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.rag import RagSource


class StoredMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[RagSource] = Field(default_factory=list)
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[StoredMessage]


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    rating: Literal["helpful", "unhelpful"]


class FeedbackResponse(BaseModel):
    id: str
    rating: Literal["helpful", "unhelpful"]


class HandoffRequest(BaseModel):
    conversation_id: str
    message_id: str | None = None
    note: str = Field(default="", max_length=1000)


class HandoffResponse(BaseModel):
    id: str
    status: Literal["pending"]
