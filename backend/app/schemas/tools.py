from typing import Any, Literal

from pydantic import BaseModel, Field


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    carrier: str | None = None
    tracking_number: str | None = None
    estimated_delivery: str | None = None


class TicketCreateRequest(BaseModel):
    description: str = Field(min_length=2, max_length=2000)


class TicketResponse(BaseModel):
    ticket_id: str
    status: Literal["open"]
    description: str


class ToolCallRecord(BaseModel):
    id: str
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    created_at: str


class ToolLogListResponse(BaseModel):
    logs: list[ToolCallRecord]
