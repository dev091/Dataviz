from pathlib import Path
import sys
from datetime import datetime, time, timezone
import uuid

from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[3]
for path in [ROOT / "apps" / "api", ROOT / "packages" / "connectors", ROOT / "packages" / "semantic", ROOT / "packages" / "analytics"]:
    value = str(path)
    if value not in sys.path:
        sys.path.append(value)

from app.db.base import SessionLocal  # noqa: E402
from app.models.entities import AlertEvent, AlertRule, DataConnection, ReportSchedule, SyncJob  # noqa: E402
from app.services.audit import write_audit_log  # noqa: E402
from app.services.email_delivery import email_service  # noqa: E402
from app.services.nl import evaluate_alert_metric  # noqa: E402
from app.services.proactive_insights import run_proactive_insight_agents  # noqa: E402
from app.services.sync import mark_job_executed, run_sync  # noqa: E402


def _is_due(last_run: datetime | None, schedule_type: str, weekday: int | None, now: datetime) -> bool:
    if schedule_type == "daily":
        return last_run is None or last_run.date() < now.date()

    if schedule_type == "weekly":
        if weekday is None:
            weekday = 0
        if now.weekday() != weekday:
            return False
        return last_run is None or (now.date() - last_run.date()).days >= 7

    return False


def run_due_sync_jobs() -> dict:
    now = datetime.now(timezone.utc)
    processed = 0
    with SessionLocal() as db:
        jobs = db.scalars(
            select(SyncJob)
            .where(SyncJob.enabled.is_(True), SyncJob.next_run_at.is_not(None), SyncJob.next_run_at <= now)
            .order_by(SyncJob.next_run_at.asc())
        ).all()

        for job in jobs:
            connection = db.get(DataConnection, job.connection_id)
            if not connection:
                continue
            run_sync(db, connection, job_id=job.id)
            mark_job_executed(db, job)
            processed += 1

        db.commit()
    return {"processed": processed}


def _triggered(value: float, condition: str, threshold: float) -> bool:
    if condition == ">":
        return value > threshold
    if condition == "<":
        return value < threshold
    if condition == ">=":
        return value >= threshold
    if condition == "<=":
        return value <= threshold
    return False


def run_due_alerts() -> dict:
    now = datetime.now(timezone.utc)
    processed = 0
    with SessionLocal() as db:
        rules = db.scalars(select(AlertRule).where(AlertRule.enabled.is_(True))).all()
        for rule in rules:
            due = _is_due(rule.last_evaluated_at, rule.schedule_type, 0, now)
            if not due:
                continue

            value = evaluate_alert_metric(db, semantic_model_id=rule.semantic_model_id, metric_id=rule.metric_id)
            fired = _triggered(value, rule.condition, rule.threshold)
            event = AlertEvent(
                alert_rule_id=rule.id,
                status="triggered" if fired else "ok",
                value=value,
                message=f"Worker evaluation value={value:.2f} condition={rule.condition}{rule.threshold}",
            )
            db.add(event)
            rule.last_evaluated_at = now
            processed += 1
        db.commit()
    return {"processed": processed}


def run_due_reports() -> dict:
    now = datetime.now(timezone.utc)
    delivered = 0
    failed = 0
    with SessionLocal() as db:
        schedules = db.scalars(select(ReportSchedule).where(ReportSchedule.enabled.is_(True))).all()
        for schedule in schedules:
            due = _is_due(schedule.last_sent_at, schedule.schedule_type, schedule.weekday, now)
            if not due:
                continue

            # Respect configured delivery time when present.
            if schedule.daily_time:
                hour, minute = [int(part) for part in schedule.daily_time.split(":")]
                if now.time() < time(hour=hour, minute=minute, tzinfo=timezone.utc):
                    continue

            result = email_service.send_report_schedule(db, schedule=schedule, delivered_at=now)
            if result.ok:
                schedule.last_sent_at = now
                write_audit_log(
                    db,
                    action="report_schedule.delivered",
                    entity_type="report_schedule",
                    entity_id=schedule.id,
                    user=None,
                    organization_id=None,
                    workspace_id=schedule.workspace_id,
                    metadata={
                        "dashboard_id": schedule.dashboard_id,
                        "email_to": schedule.email_to,
                        "provider": result.provider,
                        "message_id": result.message_id,
                    },
                )
                delivered += 1
            else:
                write_audit_log(
                    db,
                    action="report_schedule.delivery_failed",
                    entity_type="report_schedule",
                    entity_id=schedule.id,
                    user=None,
                    organization_id=None,
                    workspace_id=schedule.workspace_id,
                    metadata={
                        "dashboard_id": schedule.dashboard_id,
                        "email_to": schedule.email_to,
                        "provider": result.provider,
                        "error": result.error,
                    },
                )
                failed += 1
        db.commit()
    return {"delivered": delivered, "failed": failed}


def run_proactive_insights() -> dict:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        created = run_proactive_insight_agents(db)
        if created:
            write_audit_log(
                db,
                action="insight.proactive.run",
                entity_type="insight_artifact",
                entity_id=str(uuid.uuid4()),
                user=None,
                organization_id=None,
                workspace_id=None,
                metadata={"created": created, "ran_at": now.isoformat()},
            )
        db.commit()
    return {"created": created}
