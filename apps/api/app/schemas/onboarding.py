from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.dashboards import ReportPackResponse


class LaunchPackTemplateResponse(BaseModel):
    id: str
    title: str
    department: str
    summary: str
    deliverables: list[str]
    focus_metrics: list[str]
    operating_views: list[str]
    exception_report_title: str
    report_type: str
    report_audience: str
    default_dashboard_name: str
    default_schedule_type: str
    default_weekday: int | None = Field(default=None, ge=0, le=6)
    default_daily_time: str | None = None


class LaunchPackAlertSuggestion(BaseModel):
    metric_id: str
    metric_name: str
    metric_label: str
    suggested_condition: str
    reason: str


class LaunchPackProvisionRequest(BaseModel):
    template_id: str
    semantic_model_id: str
    email_to: list[str] = Field(default_factory=list)
    create_schedule: bool = True


class LaunchPackProvisionResponse(BaseModel):
    template_id: str
    dashboard_id: str
    dashboard_name: str
    widgets_added: int
    notes: list[str]
    report_schedule_id: str | None = None
    report_schedule_name: str | None = None
    report_pack: ReportPackResponse
    suggested_alerts: list[LaunchPackAlertSuggestion]
    generated_at: datetime


class LaunchPackValidationCheckResponse(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    owner_role: str
    requires_human_review: bool = False


class LaunchPackMilestoneResponse(BaseModel):
    title: str
    status: str
    detail: str
    owner_role: str


class LaunchPackAdoptionSignalResponse(BaseModel):
    signal: str
    label: str
    value: int
    target: int
    status: str
    detail: str


class LaunchPackPlaybookResponse(BaseModel):
    template_id: str
    semantic_model_id: str
    dashboard_id: str | None = None
    readiness_score: float
    readiness_summary: str
    trust_gap_count: int
    recommended_stakeholders: list[str] = Field(default_factory=list)
    validation_checks: list[LaunchPackValidationCheckResponse] = Field(default_factory=list)
    milestones: list[LaunchPackMilestoneResponse] = Field(default_factory=list)
    adoption_signals: list[LaunchPackAdoptionSignalResponse] = Field(default_factory=list)
