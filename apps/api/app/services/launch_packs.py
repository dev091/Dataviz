from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_package_paths
from app.models.entities import Dashboard, DashboardWidget, ReportSchedule, SemanticMetric, SemanticModel
from app.services.dashboard_composer import compose_dashboard_widgets
from app.services.reporting import generate_dashboard_report_pack

bootstrap_package_paths()
from executive.launch_packs import (  # noqa: E402
    get_launch_pack as registry_get_launch_pack,
    list_launch_packs as registry_list_launch_packs,
    matches_focus_metric,
)


def list_launch_packs() -> list[dict[str, Any]]:
    return registry_list_launch_packs()


def get_launch_pack(template_id: str) -> dict[str, Any] | None:
    return registry_get_launch_pack(template_id)


def suggest_alert_candidates(db: Session, semantic_model_id: str, focus_metrics: list[str]) -> list[dict[str, str]]:
    metrics = db.scalars(
        select(SemanticMetric).where(SemanticMetric.semantic_model_id == semantic_model_id).order_by(SemanticMetric.name.asc())
    ).all()
    preferred = [metric for metric in metrics if matches_focus_metric(metric.name, focus_metrics)]
    selected = (preferred or metrics)[:3]
    suggestions: list[dict[str, str]] = []
    for metric in selected:
        suggestions.append(
            {
                "metric_id": metric.id,
                "metric_name": metric.name,
                "metric_label": metric.label,
                "suggested_condition": "<" if metric.aggregation in {"sum", "count", "avg"} else ">",
                "reason": f"Monitor {metric.label.lower()} automatically as part of the launch pack watchlist.",
            }
        )
    return suggestions


def provision_launch_pack(
    db: Session,
    *,
    workspace_id: str,
    semantic_model: SemanticModel,
    pack: dict[str, Any],
    created_by: str,
    email_to: list[str],
    create_schedule: bool,
    dashboard_name_override: str | None = None,
    description_override: str | None = None,
    report_goal_override: str | None = None,
) -> dict[str, Any]:
    dashboard_name = dashboard_name_override or pack["default_dashboard_name"]
    dashboard_description = description_override or pack["summary"]
    dashboard = Dashboard(
        workspace_id=workspace_id,
        created_by=created_by,
        name=dashboard_name,
        description=dashboard_description,
        layout={
            "cols": 12,
            "rowHeight": 32,
            "template_id": pack["id"],
            "report_type": pack["report_type"],
            "operating_views": pack["operating_views"],
            "exception_report_title": pack["exception_report_title"],
        },
    )
    db.add(dashboard)
    db.flush()

    widget_payloads, notes = compose_dashboard_widgets(
        db,
        dashboard_id=dashboard.id,
        semantic_model=semantic_model,
        goal=pack["auto_compose_goal"],
        max_widgets=6,
    )

    for widget_payload in widget_payloads:
        db.add(
            DashboardWidget(
                dashboard_id=dashboard.id,
                title=widget_payload["title"],
                widget_type=widget_payload["widget_type"],
                config=widget_payload["config"],
                position=widget_payload["position"],
            )
        )
    db.flush()

    schedule = None
    clean_emails = [email.strip() for email in email_to if email.strip()]
    if create_schedule and clean_emails:
        schedule = ReportSchedule(
            workspace_id=workspace_id,
            dashboard_id=dashboard.id,
            created_by=created_by,
            name=f"{dashboard_name} Distribution",
            email_to=clean_emails,
            schedule_type=pack["default_schedule_type"],
            daily_time=pack.get("default_daily_time"),
            weekday=pack.get("default_weekday"),
            enabled=True,
        )
        db.add(schedule)
        db.flush()

    report_pack = generate_dashboard_report_pack(
        db,
        dashboard=dashboard,
        audience=pack["report_audience"],
        goal=report_goal_override or pack["report_goal"],
        report_type=pack["report_type"],
        operating_views=pack["operating_views"],
        exception_report_title=pack["exception_report_title"],
    )
    suggested_alerts = suggest_alert_candidates(db, semantic_model.id, pack["focus_metrics"])

    return {
        "template_id": pack["id"],
        "dashboard": dashboard,
        "widgets_added": len(widget_payloads),
        "notes": notes,
        "report_schedule": schedule,
        "report_pack": report_pack,
        "suggested_alerts": suggested_alerts,
        "generated_at": datetime.now(timezone.utc),
    }
