from typing import Literal

from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    document_count: int
    today_conversation_count: int
    feedback_count: int
    knowledge_gap_count: int
    handoff_count: int


class FeedbackEntry(BaseModel):
    id: str
    conversation_id: str
    message_id: str
    rating: str
    created_at: str
    updated_at: str | None = None


class KnowledgeGapEntry(BaseModel):
    id: str
    conversation_id: str
    message_id: str
    question: str
    status: str
    created_at: str


class KnowledgeGapStatusRequest(BaseModel):
    status: Literal["open", "resolved"]


class HandoffEntry(BaseModel):
    id: str
    conversation_id: str
    message_id: str | None = None
    note: str
    status: str
    created_at: str


class FeedbackListResponse(BaseModel):
    feedback: list[FeedbackEntry]


class KnowledgeGapListResponse(BaseModel):
    knowledge_gaps: list[KnowledgeGapEntry]


class HandoffListResponse(BaseModel):
    handoffs: list[HandoffEntry]
