from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import AlertEvent, AlertRule, Dashboard, ReportSchedule, User
from app.schemas.alerts import (
    AlertRuleCreateRequest,
    AlertRuleResponse,
    ReportScheduleCreateRequest,
    ReportScheduleResponse,
)
from app.services.audit import write_audit_log
from app.services.nl import evaluate_alert_metric


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
