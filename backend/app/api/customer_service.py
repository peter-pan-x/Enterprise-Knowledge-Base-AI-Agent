from fastapi import APIRouter, HTTPException, status

from app.schemas.customer_service import (
    ConversationDetail,
    ConversationListResponse,
    FeedbackRequest,
    FeedbackResponse,
    HandoffRequest,
    HandoffResponse,
)
from app.services.customer_service import (
    CustomerServiceError,
    create_handoff,
    get_conversation,
    list_conversations,
    save_feedback,
)

router = APIRouter()


@router.get("/conversations", response_model=ConversationListResponse)
async def conversations() -> ConversationListResponse:
    return ConversationListResponse(conversations=list_conversations())


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def conversation_detail(conversation_id: str) -> ConversationDetail:
    try:
        return get_conversation(conversation_id)
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest) -> FeedbackResponse:
    try:
        result = save_feedback(request.conversation_id, request.message_id, request.rating)
        return FeedbackResponse(id=result["id"], rating=result["rating"])
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/handoffs", response_model=HandoffResponse, status_code=status.HTTP_201_CREATED)
async def handoff(request: HandoffRequest) -> HandoffResponse:
    try:
        result = create_handoff(request.conversation_id, request.message_id, request.note)
        return HandoffResponse(id=result["id"], status=result["status"])
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
