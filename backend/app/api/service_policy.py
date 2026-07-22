from fastapi import APIRouter, Depends

from app.schemas.service_policy import PublicServicePolicy, ServicePolicy
from app.services.auth_service import CurrentUser, get_current_user, require_admin
from app.services.service_policy_service import get_service_policy, update_service_policy

router = APIRouter()


@router.get("/public", response_model=PublicServicePolicy)
def get_public_policy(_: CurrentUser = Depends(get_current_user)) -> PublicServicePolicy:
    return PublicServicePolicy(welcome_message=get_service_policy().welcome_message)


@router.get("", response_model=ServicePolicy)
def get_policy(_: CurrentUser = Depends(require_admin)) -> ServicePolicy:
    return get_service_policy()


@router.put("", response_model=ServicePolicy)
def put_policy(policy: ServicePolicy, _: CurrentUser = Depends(require_admin)) -> ServicePolicy:
    return update_service_policy(policy)
