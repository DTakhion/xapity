# schemas/auth.py

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


UserRole = Literal["admin", "staff", "customer", "user"]


class AuthRegisterRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=40)
    organizationName: str = Field(..., min_length=3, max_length=120)
    role: UserRole = Field(default="admin")


class AuthRegisterStartResponse(BaseModel):
    ok: bool = True
    message: str
    email: EmailStr


class AuthRegisterVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class AuthUserResponse(BaseModel):
    userId: str
    businessId: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    organizationName: str
    role: UserRole
    isActive: bool
    isDeleted: bool
    createdAt: datetime
    updatedAt: datetime
    _id: Optional[str] = None


class AuthRegisterVerifyResponse(BaseModel):
    user: AuthUserResponse


class AuthLoginResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: AuthUserResponse


class AuthMeResponse(BaseModel):
    user: AuthUserResponse

class AuthForgotPasswordRequest(BaseModel):
    email: EmailStr


class AuthForgotPasswordResponse(BaseModel):
    ok: bool = True
    message: str


class AuthResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    newPassword: str = Field(..., min_length=6, max_length=128)


class AuthResetPasswordResponse(BaseModel):
    ok: bool = True
    message: str

class AuthInviteUserRequest(BaseModel):
    email: EmailStr
    role: UserRole = Field(default="user")


class AuthInviteUserResponse(BaseModel):
    ok: bool = True
    message: str
    email: EmailStr
    role: UserRole

class AuthAcceptInvitationRequest(BaseModel):
    token: str = Field(..., min_length=20)
    name: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=40)


class AuthAcceptInvitationResponse(BaseModel):
    user: AuthUserResponse