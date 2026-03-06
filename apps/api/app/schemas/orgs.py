from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=255)
    key: str = Field(min_length=2, max_length=100)


class WorkspaceResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    key: str
