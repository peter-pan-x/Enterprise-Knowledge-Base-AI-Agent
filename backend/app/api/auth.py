from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.services.auth_service import CurrentUser, authenticate, get_current_user, issue_token

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    user = authenticate(request.username, request.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return LoginResponse(access_token=issue_token(user), user=user.profile())


@router.get("/me", response_model=UserProfile)
async def me(user: CurrentUser = Depends(get_current_user)) -> UserProfile:
    return user.profile()
