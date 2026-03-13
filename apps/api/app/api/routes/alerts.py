from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import AlertEvent, AlertRule, AuditLog, Dashboard, InsightArtifact, ReportSchedule, SemanticMetric, User
from app.schemas.alerts import (
    AlertRuleCreateRequest,
    AlertRuleResponse,
    DeliveryLogResponse,
    ProactiveDigestResponse,
    ProactiveInsightResponse,
    ProactiveInsightRunResponse,
    ReportScheduleCreateRequest,
    ReportScheduleResponse,
)
from app.services.audit import write_audit_log
from app.services.nl import evaluate_alert_metric
from app.services.proactive_insights import build_proactive_digest, run_proactive_insight_agents


router = APIRouter()


def _is_triggered(value: float, condition: str, threshold: float) -> bool:
    if condition == ">":
        return value > threshold
    if condition == "<":
        return value < threshold
    if condition == ">=":
        return value >= threshold
    if condition == "<=":
        return value <= threshold
    return False


@router.post("/report-schedules", response_model=ReportScheduleResponse)
def create_report_schedule(
    payload: ReportScheduleCreateRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> ReportScheduleResponse:
    dashboard = db.scalar(select(Dashboard).where(Dashboard.id == payload.dashboard_id, Dashboard.workspace_id == workspace_id))
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    schedule = ReportSchedule(
        workspace_id=workspace_id,
        dashboard_id=payload.dashboard_id,
        created_by=current_user.id,
        name=payload.name,
        email_to=payload.email_to,
        schedule_type=payload.schedule_type,
        daily_time=payload.daily_time,
        weekday=payload.weekday,
        enabled=payload.enabled,
    )
    db.add(schedule)
    db.flush()

    write_audit_log(
        db,
        action="report_schedule.create",
        entity_type="report_schedule",
        entity_id=schedule.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"dashboard_id": payload.dashboard_id, "schedule_type": payload.schedule_type},
    )
    db.commit()

    return ReportScheduleResponse(
        id=schedule.id,
        dashboard_id=schedule.dashboard_id,
        name=schedule.name,
        email_to=schedule.email_to,
        schedule_type=schedule.schedule_type,
        daily_time=schedule.daily_time,
        weekday=schedule.weekday,
        enabled=schedule.enabled,
        last_sent_at=schedule.last_sent_at,
    )


@router.get("/report-schedules", response_model=list[ReportScheduleResponse])
def list_report_schedules(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[ReportScheduleResponse]:
    _ = current_user
    rows = db.scalars(
        select(ReportSchedule).where(ReportSchedule.workspace_id == workspace_id).order_by(ReportSchedule.created_at.desc())
    ).all()
    return [
        ReportScheduleResponse(
            id=row.id,
            dashboard_id=row.dashboard_id,
            name=row.name,
            email_to=row.email_to,
            schedule_type=row.schedule_type,
            daily_time=row.daily_time,
            weekday=row.weekday,
            enabled=row.enabled,
            last_sent_at=row.last_sent_at,
        )
        for row in rows
    ]


@router.get("/delivery-logs", response_model=list[DeliveryLogResponse])
def list_delivery_logs(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[DeliveryLogResponse]:
    _ = current_user
    rows = db.execute(
        select(AuditLog, ReportSchedule, Dashboard)
        .join(ReportSchedule, ReportSchedule.id == AuditLog.entity_id, isouter=True)
        .join(Dashboard, Dashboard.id == ReportSchedule.dashboard_id, isouter=True)
        .where(
            AuditLog.workspace_id == workspace_id,
            AuditLog.action.in_(["report_schedule.delivered", "report_schedule.delivery_failed"]),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    ).all()

    payload: list[DeliveryLogResponse] = []
    for audit, schedule, dashboard in rows:
        metadata = audit.metadata_json or {}
        payload.append(
            DeliveryLogResponse(
                id=audit.id,
                schedule_id=audit.entity_id,
                schedule_name=schedule.name if schedule else metadata.get("schedule_name", "Unknown schedule"),
                dashboard_id=(schedule.dashboard_id if schedule else metadata.get("dashboard_id", "")),
                dashboard_name=dashboard.name if dashboard else None,
                status="delivered" if audit.action.endswith("delivered") else "failed",
                provider=metadata.get("provider"),
                message_id=metadata.get("message_id"),
                recipients=list(metadata.get("email_to", [])) if isinstance(metadata.get("email_to", []), list) else [],
                error=metadata.get("error"),
                created_at=audit.created_at,
            )
        )
    return payload


@router.post("/rules", response_model=AlertRuleResponse)
def create_alert_rule(
    payload: AlertRuleCreateRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> AlertRuleResponse:
    rule = AlertRule(
        workspace_id=workspace_id,
        semantic_model_id=payload.semantic_model_id,
        metric_id=payload.metric_id,
        created_by=current_user.id,
        name=payload.name,
        condition=payload.condition,
        threshold=payload.threshold,
        schedule_type=payload.schedule_type,
        enabled=payload.enabled,
    )
    db.add(rule)
    db.flush()

    write_audit_log(
        db,
        action="alert_rule.create",
        entity_type="alert_rule",
        entity_id=rule.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"metric_id": payload.metric_id, "condition": payload.condition, "threshold": payload.threshold},
    )
    db.commit()

    return AlertRuleResponse(
        id=rule.id,
        semantic_model_id=rule.semantic_model_id,
        metric_id=rule.metric_id,
        name=rule.name,
        condition=rule.condition,
        threshold=rule.threshold,
        schedule_type=rule.schedule_type,
        enabled=rule.enabled,
        last_evaluated_at=rule.last_evaluated_at,
    )


@router.get("/rules", response_model=list[AlertRuleResponse])
def list_rules(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[AlertRuleResponse]:
    _ = current_user
    rows = db.scalars(select(AlertRule).where(AlertRule.workspace_id == workspace_id).order_by(AlertRule.created_at.desc())).all()
    return [
        AlertRuleResponse(
            id=row.id,
            semantic_model_id=row.semantic_model_id,
            metric_id=row.metric_id,
            name=row.name,
            condition=row.condition,
            threshold=row.threshold,
            schedule_type=row.schedule_type,
            enabled=row.enabled,
            last_evaluated_at=row.last_evaluated_at,
        )
        for row in rows
    ]


@router.post("/rules/{rule_id}/evaluate")
def evaluate_rule(
    rule_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> dict:
    rule = db.scalar(select(AlertRule).where(AlertRule.id == rule_id, AlertRule.workspace_id == workspace_id))
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    value = evaluate_alert_metric(db, semantic_model_id=rule.semantic_model_id, metric_id=rule.metric_id)
    triggered = _is_triggered(value, rule.condition, rule.threshold)

    event = AlertEvent(
        alert_rule_id=rule.id,
        status="triggered" if triggered else "ok",
        value=value,
        message=f"Metric value {value:.2f} {'met' if triggered else 'did not meet'} condition {rule.condition} {rule.threshold}",
    )
    db.add(event)

    rule.last_evaluated_at = datetime.now(timezone.utc)
    db.flush()

    write_audit_log(
        db,
        action="alert_rule.evaluate",
        entity_type="alert_event",
        entity_id=event.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"rule_id": rule.id, "status": event.status, "value": value},
    )
    db.commit()

    return {
        "alert_event_id": event.id,
        "status": event.status,
        "value": event.value,
        "message": event.message,
        "triggered_at": event.triggered_at,
    }


@router.get("/events")
def list_events(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = current_user
    rows = db.execute(
        select(AlertEvent, AlertRule)
        .join(AlertRule, AlertRule.id == AlertEvent.alert_rule_id)
        .where(AlertRule.workspace_id == workspace_id)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": event.id,
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": event.status,
            "value": event.value,
            "message": event.message,
            "triggered_at": event.triggered_at,
        }
        for event, rule in rows
    ]


@router.get("/proactive-insights", response_model=list[ProactiveInsightResponse])
def list_proactive_insights(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[ProactiveInsightResponse]:
    _ = current_user
    rows = db.execute(
        select(InsightArtifact, SemanticMetric)
        .join(SemanticMetric, SemanticMetric.id == InsightArtifact.metric_id, isouter=True)
        .where(InsightArtifact.workspace_id == workspace_id)
        .order_by(InsightArtifact.created_at.desc())
        .limit(100)
    ).all()
    payload: list[ProactiveInsightResponse] = []
    for artifact, metric in rows:
        data = artifact.data or {}
        payload.append(
            ProactiveInsightResponse(
                id=artifact.id,
                insight_type=artifact.insight_type,
                title=artifact.title,
                body=artifact.body,
                severity=str(data.get("severity") or "default"),
                audiences=list(data.get("audiences", [])) if isinstance(data.get("audiences", []), list) else [],
                investigation_paths=list(data.get("investigation_paths", [])) if isinstance(data.get("investigation_paths", []), list) else [],
                suggested_actions=list(data.get("suggested_actions", [])) if isinstance(data.get("suggested_actions", []), list) else [],
                escalation_policy=data.get("escalation_policy") if isinstance(data.get("escalation_policy"), dict) else None,
                metric_name=metric.label if metric else data.get("metric"),
                created_at=artifact.created_at,
            )
        )
    return payload


@router.get("/proactive-digest", response_model=ProactiveDigestResponse)
def get_proactive_digest(
    audience: str | None = None,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> ProactiveDigestResponse:
    _ = current_user
    return ProactiveDigestResponse(**build_proactive_digest(db, workspace_id=workspace_id, audience=audience))


@router.post("/proactive-insights/run", response_model=ProactiveInsightRunResponse)
def run_proactive_insights(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> ProactiveInsightRunResponse:
    _ = workspace_id
    created = run_proactive_insight_agents(db)
    write_audit_log(
        db,
        action="insight.proactive.manual_run",
        entity_type="insight_artifact",
        entity_id=current_user.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"created": created},
    )
    db.commit()
    return ProactiveInsightRunResponse(created=created)