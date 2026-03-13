from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Any
import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_package_paths
from app.models.entities import Dataset, InsightArtifact, SemanticDimension, SemanticMetric, SemanticModel
from app.services.ai_orchestrator import ai_orchestrator

bootstrap_package_paths()
from analytics.insights import detect_insights  # noqa: E402
from monitoring.policies import (  # noqa: E402
    STALE_DATASET_HOURS,
    audiences as policy_audiences,
    breakdown_dimension as choose_breakdown_dimension,
    escalation_policy as build_escalation_policy,
    investigation_paths as build_investigation_paths,
    normalize_timestamp,
    safe_column_ref,
    suggested_actions as build_suggested_actions,
    time_dimension as choose_time_dimension,
)


def _query_rows(db: Session, dataset: Dataset, metric: SemanticMetric, time_dimension: SemanticDimension | None) -> list[dict[str, Any]]:
    if time_dimension:
        time_column = safe_column_ref(time_dimension.field_ref)
        if not time_column:
            return []
        sql = (
            f"SELECT {time_column} AS {time_dimension.name}, {metric.formula} AS {metric.name} "
            f"FROM {dataset.physical_table} "
            f"GROUP BY {time_column} "
            f"ORDER BY {time_column} DESC LIMIT 24"
        )
        rows = [dict(row._mapping) for row in db.execute(text(sql)).fetchall()]
        rows.reverse()
        return rows

    sql = f"SELECT {metric.formula} AS {metric.name} FROM {dataset.physical_table}"
    return [dict(row._mapping) for row in db.execute(text(sql)).fetchall()]


def _series(rows: list[dict[str, Any]], metric_name: str, time_key: str | None) -> list[tuple[str, float]]:
    series: list[tuple[str, float]] = []
    for index, row in enumerate(rows):
        value = row.get(metric_name)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        label = str(row.get(time_key) if time_key else index + 1)
        series.append((label, numeric))
    return series


def _audiences(metric: SemanticMetric | None, insight_type: str) -> list[str]:
    return policy_audiences(metric.name if metric else None, insight_type)


def _suggested_actions(
    *,
    insight_type: str,
    severity: str,
    metric: SemanticMetric | None,
    dataset: Dataset,
    time_dimension: SemanticDimension | None,
    breakdown_dimension: SemanticDimension | None,
) -> list[str]:
    return build_suggested_actions(
        insight_type=insight_type,
        severity=severity,
        metric_label=metric.label if metric else dataset.name,
        dataset_name=dataset.name,
        time_dimension_label=time_dimension.label or time_dimension.name if time_dimension else None,
        breakdown_dimension_label=breakdown_dimension.label or breakdown_dimension.name if breakdown_dimension else None,
    )


def _escalation_policy(*, audiences: list[str], severity: str, insight_type: str) -> dict[str, str]:
    return build_escalation_policy(audiences_list=audiences, severity=severity, insight_type=insight_type)


def _investigation_paths(
    *,
    metric: SemanticMetric | None,
    time_dimension: SemanticDimension | None,
    breakdown_dimension: SemanticDimension | None,
    dataset: Dataset,
) -> list[str]:
    return build_investigation_paths(
        metric_label=metric.label if metric else "the affected KPI",
        time_dimension_label=time_dimension.label or time_dimension.name if time_dimension else None,
        breakdown_dimension_label=breakdown_dimension.label or breakdown_dimension.name if breakdown_dimension else None,
        dataset_name=dataset.name,
    )


def _recent_duplicate(
    db: Session,
    *,
    workspace_id: str,
    insight_type: str,
    metric_id: str | None,
    signature: str,
    now: datetime,
) -> bool:
    query = select(InsightArtifact).where(
        InsightArtifact.workspace_id == workspace_id,
        InsightArtifact.insight_type == insight_type,
        InsightArtifact.created_at >= now - timedelta(hours=24),
    )
    if metric_id is None:
        query = query.where(InsightArtifact.metric_id.is_(None))
    else:
        query = query.where(InsightArtifact.metric_id == metric_id)

    recent = db.scalars(query.order_by(InsightArtifact.created_at.desc()).limit(5)).all()
    for artifact in recent:
        if str((artifact.data or {}).get("signature")) == signature:
            return True
    return False


def _store_artifact(
    db: Session,
    *,
    model: SemanticModel,
    metric: SemanticMetric | None,
    insight_type: str,
    title: str,
    body: str,
    severity: str,
    audiences: list[str],
    investigation_paths: list[str],
    suggested_actions: list[str],
    escalation_policy: dict[str, str] | None,
    extra_data: dict[str, Any],
    now: datetime,
) -> int:
    signature = str(extra_data.get("signature"))
    if _recent_duplicate(
        db,
        workspace_id=model.workspace_id,
        insight_type=insight_type,
        metric_id=metric.id if metric else None,
        signature=signature,
        now=now,
    ):
        return 0

    db.add(
        InsightArtifact(
            workspace_id=model.workspace_id,
            dashboard_id=None,
            metric_id=metric.id if metric else None,
            insight_type=insight_type,
            title=title,
            body=body,
            data={
                "severity": severity,
                "audiences": audiences,
                "investigation_paths": investigation_paths,
                "suggested_actions": suggested_actions,
                "escalation_policy": escalation_policy,
                **extra_data,
            },
        )
    )
    return 1


def run_proactive_insight_agents(db: Session) -> int:
    created = 0
    now = datetime.now(timezone.utc)

    models = db.scalars(select(SemanticModel).where(SemanticModel.is_active.is_(True))).all()
    for model in models:
        dataset = db.get(Dataset, model.base_dataset_id)
        if not dataset:
            continue

        metrics = db.scalars(
            select(SemanticMetric).where(SemanticMetric.semantic_model_id == model.id, SemanticMetric.visibility == "public")
        ).all()
        dimensions = db.scalars(
            select(SemanticDimension).where(
                SemanticDimension.semantic_model_id == model.id,
                SemanticDimension.visibility == "public",
            )
        ).all()

        time_dimension = choose_time_dimension(dimensions)
        breakdown_dimension = choose_breakdown_dimension(dimensions, time_dimension)

        dataset_updated_at = normalize_timestamp(dataset.updated_at)
        dataset_age_hours = (now - dataset_updated_at).total_seconds() / 3600 if dataset_updated_at else None
        if dataset_age_hours is None or dataset_age_hours >= STALE_DATASET_HOURS or dataset.quality_status in {"warning", "critical", "unknown"}:
            freshness_state = "warning" if dataset_age_hours is not None and dataset_age_hours < 72 else "critical"
            freshness_title = f"Freshness watch: {dataset.name}"
            freshness_body = (
                f"Dataset {dataset.name} has not been refreshed within the expected window"
                if dataset_age_hours is None or dataset_age_hours >= STALE_DATASET_HOURS
                else f"Dataset {dataset.name} quality is flagged as {dataset.quality_status}."
            )
            freshness_audiences = _audiences(None, "freshness")
            created += _store_artifact(
                db,
                model=model,
                metric=None,
                insight_type="freshness",
                title=freshness_title,
                body=freshness_body,
                severity=freshness_state,
                audiences=freshness_audiences,
                investigation_paths=_investigation_paths(metric=None, time_dimension=time_dimension, breakdown_dimension=breakdown_dimension, dataset=dataset),
                suggested_actions=_suggested_actions(
                    insight_type="freshness",
                    severity=freshness_state,
                    metric=None,
                    dataset=dataset,
                    time_dimension=time_dimension,
                    breakdown_dimension=breakdown_dimension,
                ),
                escalation_policy=_escalation_policy(audiences=freshness_audiences, severity=freshness_state, insight_type="freshness"),
                extra_data={
                    "dataset_id": dataset.id,
                    "dataset_name": dataset.name,
                    "dataset_age_hours": round(dataset_age_hours, 1) if dataset_age_hours is not None else None,
                    "quality_status": dataset.quality_status,
                    "signature": f"freshness:{dataset.id}:{dataset.quality_status}:{int(dataset_age_hours or 0)}",
                },
                now=now,
            )

        for metric in metrics:
            try:
                rows = _query_rows(db, dataset, metric, time_dimension)
            except Exception:
                continue

            series = _series(rows, metric.name, time_dimension.name if time_dimension else None)
            if len(series) < 2:
                continue

            values = [value for _, value in series]
            labels = [label for label, _ in series]
            investigation_paths = _investigation_paths(
                metric=metric,
                time_dimension=time_dimension,
                breakdown_dimension=breakdown_dimension,
                dataset=dataset,
            )

            if len(values) >= 4:
                baseline_values = values[-4:-1]
                baseline = mean(baseline_values) if baseline_values else 0.0
                current = values[-1]
                if baseline:
                    pacing_delta = (current - baseline) / abs(baseline)
                    if abs(pacing_delta) >= 0.15:
                        direction = "ahead" if pacing_delta > 0 else "behind"
                        pacing_severity = "warning" if pacing_delta < 0 else "success"
                        pacing_audiences = _audiences(metric, "pacing")
                        created += _store_artifact(
                            db,
                            model=model,
                            metric=metric,
                            insight_type="pacing",
                            title=f"Pacing signal: {metric.label}",
                            body=f"{metric.label} is {direction} the recent run rate by {abs(pacing_delta) * 100:.1f}% in the latest period.",
                            severity=pacing_severity,
                            audiences=pacing_audiences,
                            investigation_paths=investigation_paths,
                            suggested_actions=_suggested_actions(
                                insight_type="pacing",
                                severity=pacing_severity,
                                metric=metric,
                                dataset=dataset,
                                time_dimension=time_dimension,
                                breakdown_dimension=breakdown_dimension,
                            ),
                            escalation_policy=_escalation_policy(audiences=pacing_audiences, severity=pacing_severity, insight_type="pacing"),
                            extra_data={
                                "metric": metric.name,
                                "latest_label": labels[-1],
                                "latest_value": current,
                                "baseline_value": round(baseline, 2),
                                "delta_percent": round(pacing_delta * 100, 2),
                                "signature": f"pacing:{metric.id}:{labels[-1]}:{round(pacing_delta, 4)}",
                            },
                            now=now,
                        )

            if len(values) >= 6:
                recent_mean = mean(values[-3:])
                prior_mean = mean(values[-6:-3])
                if prior_mean:
                    trend_delta = (recent_mean - prior_mean) / abs(prior_mean)
                    if abs(trend_delta) >= 0.18:
                        direction = "up" if trend_delta > 0 else "down"
                        trend_severity = "warning" if trend_delta < 0 else "success"
                        trend_audiences = _audiences(metric, "trend_break")
                        created += _store_artifact(
                            db,
                            model=model,
                            metric=metric,
                            insight_type="trend_break",
                            title=f"Trend break: {metric.label}",
                            body=f"{metric.label} shifted {direction} by {abs(trend_delta) * 100:.1f}% versus the prior rolling window.",
                            severity=trend_severity,
                            audiences=trend_audiences,
                            investigation_paths=investigation_paths,
                            suggested_actions=_suggested_actions(
                                insight_type="trend_break",
                                severity=trend_severity,
                                metric=metric,
                                dataset=dataset,
                                time_dimension=time_dimension,
                                breakdown_dimension=breakdown_dimension,
                            ),
                            escalation_policy=_escalation_policy(audiences=trend_audiences, severity=trend_severity, insight_type="trend_break"),
                            extra_data={
                                "metric": metric.name,
                                "recent_average": round(recent_mean, 2),
                                "prior_average": round(prior_mean, 2),
                                "delta_percent": round(trend_delta * 100, 2),
                                "signature": f"trend_break:{metric.id}:{labels[-1]}:{round(trend_delta, 4)}",
                            },
                            now=now,
                        )

                deviation = pstdev(values[:-1]) if len(values[:-1]) > 1 else 0.0
                baseline = mean(values[:-1]) if values[:-1] else 0.0
                if deviation > 0:
                    z_score = abs((values[-1] - baseline) / deviation)
                    if z_score >= 2:
                        anomaly_audiences = _audiences(metric, "anomaly")
                        created += _store_artifact(
                            db,
                            model=model,
                            metric=metric,
                            insight_type="anomaly",
                            title=f"Anomaly watch: {metric.label}",
                            body=f"The latest {metric.label} reading is materially outside the recent baseline (z-score {z_score:.2f}).",
                            severity="warning",
                            audiences=anomaly_audiences,
                            investigation_paths=investigation_paths,
                            suggested_actions=_suggested_actions(
                                insight_type="anomaly",
                                severity="warning",
                                metric=metric,
                                dataset=dataset,
                                time_dimension=time_dimension,
                                breakdown_dimension=breakdown_dimension,
                            ),
                            escalation_policy=_escalation_policy(audiences=anomaly_audiences, severity="warning", insight_type="anomaly"),
                            extra_data={
                                "metric": metric.name,
                                "latest_label": labels[-1],
                                "latest_value": values[-1],
                                "baseline_value": round(baseline, 2),
                                "z_score": round(z_score, 2),
                                "signature": f"anomaly:{metric.id}:{labels[-1]}:{round(z_score, 2)}",
                            },
                            now=now,
                        )

            derived_insights = detect_insights(rows, [metric.name], [time_dimension.name] if time_dimension else [])
            if any(item.get("type") == "rank" for item in derived_insights):
                rank = next(item for item in derived_insights if item.get("type") == "rank")
                investigation_audiences = _audiences(metric, "investigation_path")
                created += _store_artifact(
                    db,
                    model=model,
                    metric=metric,
                    insight_type="investigation_path",
                    title=f"Suggested drill path: {metric.label}",
                    body=str(rank.get("body") or "Top contributors are available for review."),
                    severity="default",
                    audiences=investigation_audiences,
                    investigation_paths=investigation_paths,
                    suggested_actions=_suggested_actions(
                        insight_type="investigation_path",
                        severity="default",
                        metric=metric,
                        dataset=dataset,
                        time_dimension=time_dimension,
                        breakdown_dimension=breakdown_dimension,
                    ),
                    escalation_policy=_escalation_policy(audiences=investigation_audiences, severity="default", insight_type="investigation_path"),
                    extra_data={
                        "metric": metric.name,
                        "leaders": (rank.get("data") or {}).get("leaders", []),
                        "signature": f"investigation_path:{metric.id}:{','.join(map(str, (rank.get('data') or {}).get('leaders', [])))}",
                    },
                    now=now,
                )

    db.flush()
    return created


def build_proactive_digest(db: Session, *, workspace_id: str, audience: str | None = None) -> dict[str, Any]:
    rows = db.scalars(
        select(InsightArtifact)
        .where(InsightArtifact.workspace_id == workspace_id)
        .order_by(InsightArtifact.created_at.desc())
        .limit(20)
    ).all()

    selected: list[InsightArtifact] = []
    for artifact in rows:
        artifact_audiences = list((artifact.data or {}).get("audiences", [])) if isinstance((artifact.data or {}).get("audiences", []), list) else []
        if audience and audience not in artifact_audiences:
            continue
        selected.append(artifact)

    requested_audience = audience or "Executive leadership"
    if not selected:
        return {
            "audience": requested_audience,
            "generated_at": datetime.now(timezone.utc),
            "summary": "No recent proactive signals require escalation for the selected audience.",
            "recommended_recipients": [requested_audience],
            "top_insights": [],
            "suggested_actions": ["Keep the existing KPI review cadence and monitor the next scheduled digest."],
            "escalation_policies": [],
        }

    digest_rows = [
        {
            "insight_type": artifact.insight_type,
            "title": artifact.title,
            "severity": (artifact.data or {}).get("severity", "default"),
            "metric": (artifact.data or {}).get("metric"),
            "created_at": artifact.created_at.isoformat(),
        }
        for artifact in selected[:8]
    ]
    digest_insights = [
        {
            "type": artifact.insight_type,
            "title": artifact.title,
            "body": artifact.body,
            "data": artifact.data or {},
        }
        for artifact in selected[:6]
    ]

    summary = ai_orchestrator.summarize(
        question=f"Create a concise proactive KPI digest for {requested_audience} with recommended next actions and escalation context.",
        rows=digest_rows,
        metrics=[row.get("metric") for row in digest_rows if row.get("metric")],
        dimensions=["severity", "insight_type"],
        insights=digest_insights,
    )

    recommended_recipients: list[str] = []
    if audience:
        recommended_recipients.append(audience)
    suggested_actions: list[str] = []
    escalation_policies: list[dict[str, str]] = []
    for artifact in selected:
        artifact_data = artifact.data or {}
        for recipient in list(artifact_data.get("audiences", [])) if isinstance(artifact_data.get("audiences", []), list) else []:
            if recipient not in recommended_recipients:
                recommended_recipients.append(recipient)
        for action in list(artifact_data.get("suggested_actions", [])) if isinstance(artifact_data.get("suggested_actions", []), list) else []:
            if action not in suggested_actions:
                suggested_actions.append(action)
        policy = artifact_data.get("escalation_policy")
        if isinstance(policy, dict):
            policy_key = f"{policy.get('level')}:{policy.get('owner')}:{policy.get('route')}:{policy.get('sla')}"
            if all(
                f"{existing.get('level')}:{existing.get('owner')}:{existing.get('route')}:{existing.get('sla')}" != policy_key
                for existing in escalation_policies
            ):
                escalation_policies.append(
                    {
                        "level": str(policy.get("level") or "informational"),
                        "owner": str(policy.get("owner") or requested_audience),
                        "route": str(policy.get("route") or f"Include in the next digest for {requested_audience}."),
                        "sla": str(policy.get("sla") or "Next scheduled digest"),
                        "routing_depth": str(policy.get("routing_depth")) if policy.get("routing_depth") else None,
                        "tier_l1": str(policy.get("tier_l1")) if policy.get("tier_l1") else None,
                        "tier_l2": str(policy.get("tier_l2")) if policy.get("tier_l2") else None,
                        "tier_l3": str(policy.get("tier_l3")) if policy.get("tier_l3") else None,
                    }
                )

    return {
        "audience": requested_audience,
        "generated_at": datetime.now(timezone.utc),
        "summary": summary,
        "recommended_recipients": recommended_recipients[:5],
        "top_insights": [
            {
                "title": artifact.title,
                "insight_type": artifact.insight_type,
                "severity": (artifact.data or {}).get("severity", "default"),
            }
            for artifact in selected[:5]
        ],
        "suggested_actions": suggested_actions[:5],
        "escalation_policies": escalation_policies[:3],
    }
