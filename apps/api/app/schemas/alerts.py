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


class DeliveryLogResponse(BaseModel):
    id: str
    schedule_id: str
    schedule_name: str
    dashboard_id: str
    dashboard_name: str | None
    status: str
    provider: str | None
    message_id: str | None
    recipients: list[str]
    error: str | None
    created_at: datetime


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


class ProactiveEscalationPolicy(BaseModel):
    level: str
    owner: str
    route: str
    sla: str
    routing_depth: str | None = None
    tier_l1: str | None = None
    tier_l2: str | None = None
    tier_l3: str | None = None


class ProactiveInsightResponse(BaseModel):
    id: str
    insight_type: str
    title: str
    body: str
    severity: str
    audiences: list[str]
    investigation_paths: list[str]
    suggested_actions: list[str] = Field(default_factory=list)
    escalation_policy: ProactiveEscalationPolicy | None = None
    metric_name: str | None = None
    created_at: datetime


class ProactiveInsightRunResponse(BaseModel):
    created: int


class ProactiveDigestInsight(BaseModel):
    title: str
    insight_type: str
    severity: str


class ProactiveDigestResponse(BaseModel):
    audience: str
    generated_at: datetime
    summary: str
    recommended_recipients: list[str]
    top_insights: list[ProactiveDigestInsight] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    escalation_policies: list[ProactiveEscalationPolicy] = Field(default_factory=list)
