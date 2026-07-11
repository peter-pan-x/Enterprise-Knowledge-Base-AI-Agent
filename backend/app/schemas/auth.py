from typing import Literal

from pydantic import BaseModel, Field


UserRole = Literal["user", "admin"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=256)


class UserProfile(BaseModel):
    id: str
    username: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserProfile
