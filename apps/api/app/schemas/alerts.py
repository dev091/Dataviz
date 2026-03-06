from datetime import datetime

from pydantic import BaseModel, Field


class ReportScheduleCreateRequest(BaseModel):
    dashboard_id: str
    name: str
    email_to: list[str]
    schedule_type: str = Field(pattern="^(daily|weekly)$")
    daily_time: str | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    enabled: bool = True


class ReportScheduleResponse(BaseModel):
    id: str
    dashboard_id: str
    name: str
    email_to: list[str]
    schedule_type: str
    daily_time: str | None
    weekday: int | None
    enabled: bool
    last_sent_at: datetime | None


class AlertRuleCreateRequest(BaseModel):
    semantic_model_id: str
    metric_id: str
    name: str
    condition: str = Field(pattern="^(>|<|>=|<=)$")
    threshold: float
    schedule_type: str = Field(pattern="^(daily|weekly)$")
    enabled: bool = True


class AlertRuleResponse(BaseModel):
    id: str
    semantic_model_id: str
    metric_id: str
    name: str
    condition: str
    threshold: float
    schedule_type: str
    enabled: bool
    last_evaluated_at: datetime | None
