from fastapi import APIRouter, Depends, HTTPException, status

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
    delete_conversation,
    get_conversation,
    list_conversations,
    save_feedback,
)
from app.services.auth_service import CurrentUser, get_current_user

router = APIRouter()


@router.get("/conversations", response_model=ConversationListResponse)
async def conversations(user: CurrentUser = Depends(get_current_user)) -> ConversationListResponse:
    return ConversationListResponse(conversations=list_conversations(user.id, user.role == "admin"))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def conversation_detail(conversation_id: str, user: CurrentUser = Depends(get_current_user)) -> ConversationDetail:
    try:
        return get_conversation(conversation_id, user.id, user.role == "admin")
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_conversation(conversation_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    try:
        delete_conversation(conversation_id, user.id, user.role == "admin")
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest, user: CurrentUser = Depends(get_current_user)) -> FeedbackResponse:
    try:
        result = save_feedback(user.id, request.conversation_id, request.message_id, request.rating)
        return FeedbackResponse(id=result["id"], rating=result["rating"])
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/handoffs", response_model=HandoffResponse, status_code=status.HTTP_201_CREATED)
async def handoff(request: HandoffRequest, user: CurrentUser = Depends(get_current_user)) -> HandoffResponse:
    try:
        result = create_handoff(user.id, request.conversation_id, request.message_id, request.note)
        return HandoffResponse(id=result["id"], status=result["status"])
    except CustomerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
