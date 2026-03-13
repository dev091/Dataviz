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


class WidgetResponse(BaseModel):
    id: str
    dashboard_id: str
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


class AutoComposeDashboardRequest(BaseModel):
    semantic_model_id: str
    goal: str | None = None
    max_widgets: int = Field(default=6, ge=1, le=12)


class AutoComposeDashboardResponse(BaseModel):
    dashboard_id: str
    widgets_added: int
    notes: list[str]


class GenerateReportPackRequest(BaseModel):
    audience: str = "Executive leadership"
    goal: str = "Board-ready summary with key changes, risks, and recommended actions"
    report_type: str = "executive_pack"
    operating_views: list[str] = Field(default_factory=list)
    exception_report_title: str | None = None


class ReportPackSection(BaseModel):
    title: str
    body: str


class ReportPackResponse(BaseModel):
    dashboard_id: str
    dashboard_name: str
    generated_at: datetime
    audience: str
    goal: str
    report_type: str
    executive_summary: str
    sections: list[ReportPackSection]
    operating_views: list[str]
    exception_report: ReportPackSection | None = None
    next_actions: list[str]
