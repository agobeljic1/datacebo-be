from pydantic import BaseModel, EmailStr, Field
from typing import Literal


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: Literal["user", "admin"]
    balance: int

    class Config:
        from_attributes = True


class UpdateUserRoleRequest(BaseModel):
    role: Literal["user", "admin"]

