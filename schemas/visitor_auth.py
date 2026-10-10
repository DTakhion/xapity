# schemas/visitor_auth.py

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ============================================================
# XAPITY ACCESS — GLOBAL VISITOR ONBOARDING
# ============================================================


class VisitorRegisterStartRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)

    rut: str = Field(..., min_length=8, max_length=12)

    phone: Optional[str] = Field(default=None, max_length=40)

    emergencyPhone: str = Field(..., min_length=8, max_length=40)

    email: EmailStr

    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("rut")
    @classmethod
    def normalize_rut(cls, value: str) -> str:
        normalized = value.strip().upper().replace(".", "").replace("-", "")

        
        if (
            len(normalized) < 8
            or len(normalized) > 9
            or not normalized[:-1].isdigit()
        ):
            raise ValueError("RUT inválido.")


        body = normalized[:-1]
        verifier = normalized[-1]

        if verifier not in "0123456789K":
            raise ValueError("Dígito verificador inválido.")

        total = sum(
            int(digit) * factor
            for digit, factor in zip(
                reversed(body),
                [2, 3, 4, 5, 6, 7] * 2,
            )
        )

        remainder = 11 - (total % 11)

        expected = (
            "0" if remainder == 11
            else "K" if remainder == 10
            else str(remainder)
        )

        if verifier != expected:
            raise ValueError("El RUT no supera la validación.")

        return f"{body}-{verifier}"


class VisitorRegisterStartResponse(BaseModel):
    ok: bool = True
    message: str
    email: EmailStr


class VisitorRegisterVerifyRequest(BaseModel):
    email: EmailStr
    
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^[0-9]{6}$",
    )


class VisitorUserResponse(BaseModel):
    userId: str

    name: str
    rut: str

    phone: Optional[str] = None
    emergencyPhone: str

    email: EmailStr

    isEmailVerified: bool
    isActive: bool
    isDeleted: bool

    createdAt: datetime
    updatedAt: datetime


class VisitorRegisterVerifyResponse(BaseModel):
    user: VisitorUserResponse
