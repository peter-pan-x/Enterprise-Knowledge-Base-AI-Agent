from datetime import UTC, datetime

from fastapi import APIRouter

from app.schemas.admin import (
    DashboardMetrics,
    FeedbackListResponse,
    HandoffListResponse,
    KnowledgeGapListResponse,
    KnowledgeGapEntry,
    KnowledgeGapStatusRequest,
)
from app.services.customer_service import CustomerServiceError, get_admin_snapshot, update_knowledge_gap_status
from fastapi import HTTPException, status
from app.services.document_service import list_documents

router = APIRouter()


@router.get("/dashboard", response_model=DashboardMetrics)
async def dashboard() -> DashboardMetrics:
    snapshot = get_admin_snapshot()
    today = datetime.now(UTC).date()
    today_conversations = sum(
        1
        for item in snapshot["conversations"]
        if datetime.fromisoformat(item["created_at"]).date() == today
    )
    return DashboardMetrics(
        document_count=len(list_documents()),
        today_conversation_count=today_conversations,
        feedback_count=len(snapshot["feedback"]),
        knowledge_gap_count=len(snapshot["knowledge_gaps"]),
        handoff_count=len(snapshot["handoffs"]),
    )


@router.get("/feedback", response_model=FeedbackListResponse)
async def feedback() -> FeedbackListResponse:
    return FeedbackListResponse(feedback=get_admin_snapshot()["feedback"])


@router.get("/knowledge-gaps", response_model=KnowledgeGapListResponse)
async def knowledge_gaps() -> KnowledgeGapListResponse:
    return KnowledgeGapListResponse(knowledge_gaps=get_admin_snapshot()["knowledge_gaps"])


@router.patch("/knowledge-gaps/{gap_id}", response_model=KnowledgeGapEntry)
async def update_knowledge_gap(gap_id: str, request: KnowledgeGapStatusRequest) -> KnowledgeGapEntry:
    try:
        return KnowledgeGapEntry.model_validate(update_knowledge_gap_status(gap_id, request.status))
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/handoffs", response_model=HandoffListResponse)
async def handoffs() -> HandoffListResponse:
    return HandoffListResponse(handoffs=get_admin_snapshot()["handoffs"])
