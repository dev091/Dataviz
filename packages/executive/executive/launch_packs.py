from __future__ import annotations

import re
from typing import Any


STOPWORDS = {
    "dashboard",
    "report",
    "pack",
    "scorecard",
    "summary",
    "business",
    "review",
    "weekly",
    "monthly",
    "quarterly",
    "executive",
    "leadership",
    "kpi",
    "metrics",
    "metric",
    "view",
    "page",
}


LAUNCH_PACKS: dict[str, dict[str, Any]] = {
    "finance_exec": {
        "id": "finance_exec",
        "title": "Finance Executive Pack",
        "department": "Finance",
        "summary": "Board-ready finance reporting with KPI scorecards, variance trends, and weekly executive pack automation.",
        "deliverables": [
            "Executive finance dashboard",
            "Weekly finance report pack",
            "Department operating views",
            "Finance variance exception report",
            "Leadership distribution schedule",
            "Suggested variance alert candidates",
        ],
        "focus_metrics": ["revenue", "profit", "margin", "cost", "arr"],
        "operating_views": [
            "Revenue and Margin Overview",
            "Expense Discipline",
            "Regional Variance Review",
        ],
        "exception_report_title": "Finance Variance Exceptions",
        "report_type": "weekly_business_review",
        "report_audience": "Finance leadership and executive team",
        "report_goal": "Board-ready finance summary with KPI movement, risks, and follow-up actions",
        "default_dashboard_name": "Finance Executive Pack",
        "auto_compose_goal": "Finance executive pack with KPI scorecards, variance trends, operating mix, and leadership detail",
        "default_schedule_type": "weekly",
        "default_weekday": 0,
        "default_daily_time": "08:00",
    },
    "revops_exec": {
        "id": "revops_exec",
        "title": "RevOps Command Pack",
        "department": "RevOps",
        "summary": "Recurring revenue and pipeline reporting with leadership-ready scorecards, funnel monitoring, and pacing visibility.",
        "deliverables": [
            "Executive RevOps dashboard",
            "Weekly pipeline review pack",
            "Department operating views",
            "Revenue exception report",
            "Leadership distribution schedule",
            "Suggested pacing alert candidates",
        ],
        "focus_metrics": ["pipeline", "revenue", "arr", "mrr", "win", "bookings"],
        "operating_views": [
            "Pipeline Coverage",
            "Conversion and Win Rate",
            "Bookings Pacing",
        ],
        "exception_report_title": "Revenue Pipeline Exceptions",
        "report_type": "weekly_business_review",
        "report_audience": "Revenue leadership and executive team",
        "report_goal": "Weekly revenue operating review with KPI movement, funnel risk, and action framing",
        "default_dashboard_name": "RevOps Command Pack",
        "auto_compose_goal": "Revenue leadership pack with KPI scorecards, trend, pipeline mix, and operating detail",
        "default_schedule_type": "weekly",
        "default_weekday": 1,
        "default_daily_time": "08:00",
    },
    "operations_exec": {
        "id": "operations_exec",
        "title": "Operations Performance Pack",
        "department": "Operations",
        "summary": "Operational KPI monitoring with exception visibility, trend breaks, and recurring operating review automation.",
        "deliverables": [
            "Operations leadership dashboard",
            "Weekly operating review pack",
            "Department operating views",
            "Operations exception report",
            "Leadership distribution schedule",
            "Suggested exception alert candidates",
        ],
        "focus_metrics": ["volume", "cost", "cycle", "throughput", "sla", "count"],
        "operating_views": [
            "Throughput and Capacity",
            "SLA Risk",
            "Bottleneck Watchlist",
        ],
        "exception_report_title": "Operations Exception Watchlist",
        "report_type": "weekly_business_review",
        "report_audience": "Operations leadership and executive team",
        "report_goal": "Operating review focused on throughput, bottlenecks, and execution risk",
        "default_dashboard_name": "Operations Performance Pack",
        "auto_compose_goal": "Operations leadership pack with scorecards, trend, mix, and exception detail widgets",
        "default_schedule_type": "weekly",
        "default_weekday": 2,
        "default_daily_time": "08:00",
    },
    "leadership_exec": {
        "id": "leadership_exec",
        "title": "Leadership Scorecard Pack",
        "department": "Leadership",
        "summary": "Cross-functional executive reporting for recurring business reviews, KPI scorecards, and narrative summaries.",
        "deliverables": [
            "Leadership scorecard dashboard",
            "Monthly business review pack",
            "Department operating views",
            "Executive watchlist exception report",
            "Executive distribution schedule",
            "Suggested watchlist alert candidates",
        ],
        "focus_metrics": ["revenue", "profit", "growth", "count", "cost", "users"],
        "operating_views": [
            "Revenue and Growth",
            "Profitability and Efficiency",
            "Executive Watchlist",
        ],
        "exception_report_title": "Leadership Watchlist Exceptions",
        "report_type": "board_summary",
        "report_audience": "Executive leadership and board stakeholders",
        "report_goal": "Monthly leadership review with business change summary, key risks, and recommended actions",
        "default_dashboard_name": "Leadership Scorecard Pack",
        "auto_compose_goal": "Leadership operating pack with KPI scorecards, trend, mix, and business review detail",
        "default_schedule_type": "weekly",
        "default_weekday": 0,
        "default_daily_time": "08:00",
    },
    "marketing_exec": {
        "id": "marketing_exec",
        "title": "Marketing Campaign Pack",
        "department": "Marketing",
        "summary": "Marketing funnel performance tracking with conversion flow, campaign ROI, and lead generation velocity.",
        "deliverables": [
            "Marketing campaign dashboard",
            "Weekly pipeline review pack",
            "Department operating views",
            "Marketing attribution exception report",
            "Leadership distribution schedule",
            "Suggested conversion alert candidates",
        ],
        "focus_metrics": ["leads", "mql", "sql", "cac", "roi", "conversion"],
        "operating_views": [
            "Lead Velocity and Pipeline",
            "Campaign Attribution",
            "Channel Efficiency",
        ],
        "exception_report_title": "Marketing Pipeline Exceptions",
        "report_type": "weekly_business_review",
        "report_audience": "Marketing leadership and executive team",
        "report_goal": "Campaign review tracking conversion flow, lead generation, and funnel drops",
        "default_dashboard_name": "Marketing Campaign Pack",
        "auto_compose_goal": "Marketing campaign performance with funnel drop-off, trend, and ROI detail",
        "default_schedule_type": "weekly",
        "default_weekday": 3,
        "default_daily_time": "08:00",
    },
    "hr_exec": {
        "id": "hr_exec",
        "title": "HR Headcount & Skills Pack",
        "department": "HR",
        "summary": "Human Resources workforce overview tracking headcount, skill acquisition, attrition, and diversity.",
        "deliverables": [
            "HR leadership dashboard",
            "Monthly workforce review pack",
            "Department operating views",
            "Attrition exception report",
            "Leadership distribution schedule",
            "Suggested retention alert candidates",
        ],
        "focus_metrics": ["headcount", "attrition", "retention", "tenure", "skills", "salary"],
        "operating_views": [
            "Workforce Demographics",
            "Retention and Attrition",
            "Skills Coverage Radar",
        ],
        "exception_report_title": "Workforce Retention Exceptions",
        "report_type": "monthly_business_review",
        "report_audience": "HR leadership and executive team",
        "report_goal": "Monthly workforce review assessing retention risks, hiring velocity, and skill gaps",
        "default_dashboard_name": "HR Headcount & Skills Pack",
        "auto_compose_goal": "HR headcount and people skills radar with retention trends and diversity mix",
        "default_schedule_type": "monthly",
        "default_weekday": 0,
        "default_daily_time": "08:00",
    },
}


def list_launch_packs() -> list[dict[str, Any]]:
    return list(LAUNCH_PACKS.values())


def get_launch_pack(template_id: str) -> dict[str, Any] | None:
    return LAUNCH_PACKS.get(template_id)


def matches_focus_metric(metric_name: str, focus_metrics: list[str]) -> bool:
    lowered = metric_name.lower()
    return any(hint in lowered for hint in focus_metrics)


def _tokenize(*values: str | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        for token in re.findall(r"[a-z0-9]+", value.lower()):
            if len(token) <= 1 or token in STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _pack_tokens(pack: dict[str, Any]) -> set[str]:
    return _tokenize(pack["id"], pack["title"], pack["department"], pack["summary"], " ".join(pack["focus_metrics"]))


def recommend_pack(asset_names: list[str], kpi_names: list[str], dimension_names: list[str], notes: str | None) -> dict[str, Any]:
    signal = _tokenize(" ".join(asset_names), " ".join(kpi_names), " ".join(dimension_names), notes)
    best_pack = None
    best_score = -1.0
    for pack in list_launch_packs():
        pack_signal = _pack_tokens(pack)
        score = len(signal & pack_signal)
        if any(metric in signal for metric in pack["focus_metrics"]):
            score += 2
        if pack["department"].lower() in signal:
            score += 2
        if score > best_score:
            best_pack = pack
            best_score = score
    return best_pack or get_launch_pack("leadership_exec") or list_launch_packs()[0]
