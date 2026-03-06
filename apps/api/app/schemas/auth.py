from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    organization_name: str = Field(min_length=2, max_length=255)
    workspace_name: str = Field(min_length=2, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class WorkspaceAccess(BaseModel):
    workspace_id: str
    workspace_name: str
    organization_id: str
    organization_name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr
    workspaces: list[WorkspaceAccess]


class MeResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str
    workspaces: list[WorkspaceAccess]
