from __future__ import annotations

from typing import Any


def _status_from_bool(value: bool) -> str:
    return "done" if value else "pending"


def build_launch_pack_playbook(
    *,
    pack: dict[str, Any],
    trust_panel: dict[str, Any],
    dashboard_present: bool,
    widget_count: int,
    schedule_count: int,
    enabled_schedule_count: int,
    focus_alert_count: int,
    report_pack_runs: int,
    delivery_events: int,
    nl_query_count: int,
    onboarding_events: int,
) -> dict[str, Any]:
    governance = trust_panel.get("governance", {})
    open_gaps = list(trust_panel.get("open_gaps", []))
    line = trust_panel.get("lineage_summary", {})

    validation_checks = [
        {
            "id": "semantic_owner",
            "title": "Assign semantic owner",
            "status": _status_from_bool(bool(governance.get("owner_name"))),
            "detail": governance.get("owner_name") or "Assign an accountable semantic owner before stakeholder rollout.",
            "owner_role": "Analytics lead",
            "requires_human_review": True,
        },
        {
            "id": "semantic_certification",
            "title": "Certify KPI layer",
            "status": "done" if governance.get("certification_status") == "certified" else "at_risk",
            "detail": f"Current certification status: {governance.get('certification_status', 'unknown')}.",
            "owner_role": "Business owner",
            "requires_human_review": True,
        },
        {
            "id": "nl_trust",
            "title": "Trust model for natural-language analytics",
            "status": _status_from_bool(bool(governance.get("trusted_for_nl", True))),
            "detail": "Natural-language answers are grounded only in trusted semantic models.",
            "owner_role": "Semantic modeling agent",
            "requires_human_review": False,
        },
        {
            "id": "lineage_depth",
            "title": "Review lineage and reusable dimensions",
            "status": "done" if not open_gaps else "at_risk",
            "detail": open_gaps[0] if open_gaps else f"{line.get('datasets_in_scope', []) and len(line.get('datasets_in_scope', [])) or 1} datasets are in governed scope.",
            "owner_role": "Data lead",
            "requires_human_review": True,
        },
        {
            "id": "launch_dashboard",
            "title": "Provision launch dashboard",
            "status": _status_from_bool(dashboard_present and widget_count > 0),
            "detail": f"{widget_count} widgets are currently provisioned for the launch dashboard.",
            "owner_role": "Executive reporting agent",
            "requires_human_review": False,
        },
        {
            "id": "launch_schedule",
            "title": "Enable recurring delivery",
            "status": _status_from_bool(enabled_schedule_count > 0),
            "detail": f"{enabled_schedule_count}/{schedule_count} schedules are enabled for this launch pack.",
            "owner_role": "Customer success",
            "requires_human_review": True,
        },
        {
            "id": "alert_watchlist",
            "title": "Cover focus metrics with alerts",
            "status": "done" if focus_alert_count >= 2 else "pending",
            "detail": f"{focus_alert_count} focus-metric alerts exist; target is at least 2.",
            "owner_role": "KPI monitoring agent",
            "requires_human_review": False,
        },
    ]

    milestones = [
        {
            "title": "Connect source and draft semantic layer",
            "status": "done",
            "detail": f"Governed model includes {line.get('metrics_governed', 0)} metrics and {line.get('dimensions_governed', 0)} dimensions.",
            "owner_role": "Semantic modeling agent",
        },
        {
            "title": "Provision first executive pack",
            "status": _status_from_bool(dashboard_present),
            "detail": f"Target deliverables: {', '.join(pack.get('deliverables', [])[:3])}.",
            "owner_role": "Executive reporting agent",
        },
        {
            "title": "Validate KPI trust with stakeholders",
            "status": "done" if governance.get("certification_status") == "certified" else "at_risk",
            "detail": "Run KPI variance review before retiring incumbent workflows.",
            "owner_role": "Business owner",
        },
        {
            "title": "Operationalize recurring delivery",
            "status": _status_from_bool(enabled_schedule_count > 0),
            "detail": f"Recurring delivery events recorded: {delivery_events}.",
            "owner_role": "Customer success",
        },
        {
            "title": "Drive executive adoption",
            "status": "done" if report_pack_runs > 0 and nl_query_count > 0 else "pending",
            "detail": f"Report generations: {report_pack_runs}; governed NL sessions: {nl_query_count}.",
            "owner_role": "Champion",
        },
    ]

    adoption_signals = [
        {
            "signal": "dashboard_widgets",
            "label": "Dashboard widgets provisioned",
            "value": widget_count,
            "target": 4,
            "status": "done" if widget_count >= 4 else "pending",
            "detail": "Executive packs should launch with at least 4 useful widgets.",
        },
        {
            "signal": "enabled_schedules",
            "label": "Enabled recurring schedules",
            "value": enabled_schedule_count,
            "target": 1,
            "status": "done" if enabled_schedule_count >= 1 else "pending",
            "detail": "Recurring delivery is required to remove manual reporting work.",
        },
        {
            "signal": "focus_metric_alerts",
            "label": "Focus-metric alert coverage",
            "value": focus_alert_count,
            "target": 2,
            "status": "done" if focus_alert_count >= 2 else "pending",
            "detail": "At least two focus metrics should be monitored automatically.",
        },
        {
            "signal": "report_pack_generations",
            "label": "Report pack generations",
            "value": report_pack_runs,
            "target": 1,
            "status": "done" if report_pack_runs >= 1 else "pending",
            "detail": "A generated report pack indicates the launch wedge is being exercised.",
        },
        {
            "signal": "governed_nl_queries",
            "label": "Governed NL analytics sessions",
            "value": nl_query_count,
            "target": 3,
            "status": "done" if nl_query_count >= 3 else "pending",
            "detail": "Usage should expand beyond static dashboards into governed self-serve analysis.",
        },
        {
            "signal": "onboarding_events",
            "label": "Onboarding automation events",
            "value": onboarding_events,
            "target": 2,
            "status": "done" if onboarding_events >= 2 else "pending",
            "detail": "Provisioning and migration events are tracked to keep onboarding repeatable.",
        },
    ]

    status_weights = {"done": 1.0, "at_risk": 0.5, "pending": 0.0}
    readiness_score = round(
        (sum(status_weights[item["status"]] for item in validation_checks) / max(len(validation_checks), 1)) * 100,
        1,
    )
    trust_gap_count = len(open_gaps)
    readiness_summary = (
        f"{pack['title']} is {readiness_score:.1f}% onboarding-ready. "
        f"Open trust gaps: {trust_gap_count}. Enabled schedules: {enabled_schedule_count}. "
        f"Focus-metric alerts: {focus_alert_count}."
    )

    return {
        "template_id": pack["id"],
        "readiness_score": readiness_score,
        "readiness_summary": readiness_summary,
        "trust_gap_count": trust_gap_count,
        "recommended_stakeholders": [
            "Executive sponsor",
            "Analytics lead",
            "Business owner",
            "Operations or finance champion",
        ],
        "validation_checks": validation_checks,
        "milestones": milestones,
        "adoption_signals": adoption_signals,
    }
