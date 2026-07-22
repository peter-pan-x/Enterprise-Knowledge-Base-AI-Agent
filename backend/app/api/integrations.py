from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.auth_service import CurrentUser, require_admin
from app.services.integration_service import get_business_adapter, list_channel_adapters

router = APIRouter()


class IntegrationCapabilities(BaseModel):
    channel_adapters: list[str]
    business_adapter_configured: bool
    supported_business_actions: list[str]


@router.get("/capabilities", response_model=IntegrationCapabilities)
def capabilities(_: CurrentUser = Depends(require_admin)) -> IntegrationCapabilities:
    return IntegrationCapabilities(
        channel_adapters=list_channel_adapters(),
        business_adapter_configured=get_business_adapter() is not None,
        supported_business_actions=["order_status", "create_ticket"],
    )
