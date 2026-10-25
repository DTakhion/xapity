# schemas/mcp_auth.py
from pydantic import BaseModel, EmailStr, Field

class MCPRegisterStartRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    provisioningToken: str = Field(min_length=20)

class MCPRegisterStartResponse(BaseModel):
    message: str

class MCPRegisterVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r'^\d{6}$')

class MCPRegisterVerifyResponse(BaseModel):
    user: dict


class MCPLoginRequest(BaseModel):
    email: EmailStr
    password: str


class MCPLoginResponse(BaseModel):
    user: dict

