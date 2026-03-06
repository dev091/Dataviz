from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DashboardCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    layout: dict[str, Any] = Field(default_factory=dict)


class WidgetInput(BaseModel):
    title: str
    widget_type: str
    config: dict[str, Any]
    position: dict[str, Any]


class DashboardResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    layout: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SaveAIWidgetRequest(BaseModel):
    ai_query_session_id: str
    title: str = "AI Insight"
    position: dict[str, Any] = Field(default_factory=lambda: {"x": 0, "y": 0, "w": 6, "h": 4})
