from fastapi import APIRouter, HTTPException, status

from app.schemas.tools import OrderStatusResponse, TicketCreateRequest, TicketResponse, ToolLogListResponse
from app.services.tool_service import ToolServiceError, create_ticket, get_order_status, list_tool_logs

router = APIRouter()


@router.get("/orders/{order_id}", response_model=OrderStatusResponse)
async def order_status(order_id: str) -> OrderStatusResponse:
    try:
        return get_order_status(order_id)
    except ToolServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def ticket(request: TicketCreateRequest) -> TicketResponse:
    return create_ticket(request.description)


@router.get("/logs", response_model=ToolLogListResponse)
async def tool_logs() -> ToolLogListResponse:
    return ToolLogListResponse(logs=list_tool_logs())
