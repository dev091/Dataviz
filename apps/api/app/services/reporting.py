from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_package_paths
from app.models.entities import Dashboard, DashboardWidget
from app.services.ai_orchestrator import ai_orchestrator

bootstrap_package_paths()
from executive.report_packs import build_exception_report_body, chart_rows_from_widget_config  # noqa: E402


def _chart_rows(widget: DashboardWidget) -> list[dict[str, Any]]:
    return chart_rows_from_widget_config(widget.title, widget.config if isinstance(widget.config, dict) else None)


def generate_dashboard_report_pack(
    db: Session,
    *,
    dashboard: Dashboard,
    audience: str,
    goal: str,
    report_type: str = "executive_pack",
    operating_views: list[str] | None = None,
    exception_report_title: str | None = None,
) -> dict[str, Any]:
    widgets = db.scalars(select(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard.id)).all()

    rows: list[dict[str, Any]] = []
    highlights: list[dict[str, Any]] = []
    for widget in widgets:
        summary = ""
        if isinstance(widget.config, dict):
            summary = str(widget.config.get("summary", "")).strip()
        highlights.append(
            {
                "title": widget.title,
                "type": widget.widget_type,
                "summary": summary or f"{widget.title} is available on the dashboard.",
            }
        )
        rows.extend(_chart_rows(widget))

    summary_prompt = f"Create an executive report pack for dashboard '{dashboard.name}' for {audience}. Goal: {goal}."
    executive_summary = ai_orchestrator.summarize(
        question=summary_prompt,
        rows=rows[:30],
        metrics=[item["title"] for item in highlights[:4]],
        dimensions=[item["type"] for item in highlights[:4]],
        insights=highlights[:5],
    )
    next_actions = ai_orchestrator.suggest_followups(
        question=summary_prompt,
        rows=rows[:20],
        metrics=[item["title"] for item in highlights[:4]],
        dimensions=[item["type"] for item in highlights[:4]],
    )

    normalized_operating_views = [view for view in (operating_views or []) if view]
    exception_title = exception_report_title or "Exception Watchlist"
    exception_report = {
        "title": exception_title,
        "body": build_exception_report_body(rows, highlights, exception_title),
    }

    sections = [
        {
            "title": "Executive Summary",
            "body": executive_summary,
        },
        {
            "title": "Key Highlights",
            "body": " ".join(item["summary"] for item in highlights[:4]) or "No widget highlights available yet.",
        },
    ]

    if normalized_operating_views:
        sections.append(
            {
                "title": "Operating Views",
                "body": "This pack includes operating views for " + ", ".join(normalized_operating_views) + ".",
            }
        )

    sections.extend(
        [
            exception_report,
            {
                "title": "Coverage",
                "body": f"This {report_type.replace('_', ' ')} summarizes {len(widgets)} dashboard widgets for {dashboard.name} and is optimized for {audience.lower()}.",
            },
        ]
    )

    return {
        "dashboard_id": dashboard.id,
        "dashboard_name": dashboard.name,
        "generated_at": datetime.now(timezone.utc),
        "audience": audience,
        "goal": goal,
        "report_type": report_type,
        "executive_summary": executive_summary,
        "sections": sections,
        "operating_views": normalized_operating_views,
        "exception_report": exception_report,
        "next_actions": next_actions[:3],
    }
