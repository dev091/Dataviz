from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_package_paths
from app.models.entities import CalculatedField, SemanticDimension, SemanticMetric, SemanticModel
from app.services.launch_packs import get_launch_pack, provision_launch_pack
from app.services.semantic import semantic_context

bootstrap_package_paths()
from executive.launch_packs import recommend_pack  # noqa: E402
from executive.migration import (  # noqa: E402
    build_output_suggestions,
    build_trust_checks,
    comparison_status,
    labelize,
    lookup_match,
    match_candidates,
    matched_target_labels,
    tool_label,
)
from semantic.models import QueryFilter, QueryPlan  # noqa: E402
from semantic.sql_builder import build_sql  # noqa: E402


def _match_kpis(db: Session, semantic_model_id: str, source_names: list[str]) -> list[dict[str, Any]]:
    metrics = db.scalars(select(SemanticMetric).where(SemanticMetric.semantic_model_id == semantic_model_id)).all()
    calculated_fields = db.scalars(select(CalculatedField).where(CalculatedField.semantic_model_id == semantic_model_id)).all()

    candidates: list[dict[str, Any]] = [
        {
            "id": metric.id,
            "name": metric.name,
            "label": metric.label,
            "target_type": "metric",
        }
        for metric in metrics
    ]
    candidates.extend(
        {
            "id": field.id,
            "name": field.name,
            "label": labelize(field.name),
            "target_type": "calculated_field",
        }
        for field in calculated_fields
    )

    return match_candidates(
        source_names,
        candidates,
        unmatched_rationale="No governed KPI or calculated field passed the migration confidence threshold.",
    )


def _match_dimensions(dimensions: list[SemanticDimension], source_names: list[str]) -> list[dict[str, Any]]:
    candidates = [
        {
            "id": candidate.id,
            "name": candidate.name,
            "label": candidate.label,
            "target_type": "dimension",
        }
        for candidate in dimensions
    ]
    return match_candidates(
        source_names,
        candidates,
        unmatched_rationale="No governed dimension passed the migration confidence threshold.",
        dimension_mode=True,
    )


def _query_governed_metric_value(
    db: Session,
    *,
    context: dict[str, Any],
    metric_name: str,
    dimension_name: str | None = None,
    dimension_value: Any = None,
) -> float | None:
    if metric_name not in context["metric_sql"]:
        return None

    filters = []
    if dimension_name:
        if dimension_name not in context["dimension_sql"]:
            return None
        filters.append(QueryFilter(field=dimension_name, operator="=", value=dimension_value))

    kwargs: dict[str, Any] = context.get("benchmark_kwargs", {})
    start_date = kwargs.get("start_date")
    end_date = kwargs.get("end_date")
    time_dim = context.get("time_dimension")

    if time_dim and (start_date or end_date):
        if time_dim.name not in context["dimension_sql"]:
            pass  # Fallback gracefully
        elif start_date and end_date:
            filters.append(QueryFilter(field=time_dim.name, operator=">=", value=start_date))
            filters.append(QueryFilter(field=time_dim.name, operator="<=", value=end_date))
        elif start_date:
            filters.append(QueryFilter(field=time_dim.name, operator=">=", value=start_date))
        elif end_date:
            filters.append(QueryFilter(field=time_dim.name, operator="<=", value=end_date))

    plan = QueryPlan(metrics=[metric_name], dimensions=[], filters=filters, limit=1)
    sql = build_sql(
        plan,
        base_table=context["base_table"],
        base_alias=context["base_alias"],
        joins=context["joins"],
        metric_sql=context["metric_sql"],
        dimension_sql=context["dimension_sql"],
    )
    row = db.execute(text(sql)).first()
    if not row:
        return None
    value = row._mapping.get(metric_name)
    if value is None:
        return None
    return float(value)


def _automated_trust_comparison(
    db: Session,
    *,
    semantic_model: SemanticModel,
    kpi_matches: list[dict[str, Any]],
    dimension_matches: list[dict[str, Any]],
    benchmark_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if not benchmark_rows:
        return {
            "rows": rows,
            "summary": {
                "compared_rows": 0,
                "pass_count": 0,
                "review_count": 0,
                "fail_count": 0,
                "pending_count": 0,
            },
        }

    context = semantic_context(db, semantic_model.id)
    for benchmark in benchmark_rows:
        source_name = str(benchmark.get("kpi_name") or "").strip()
        label = str(benchmark.get("label") or source_name or "Benchmark")
        expected_value = float(benchmark.get("expected_value", 0))
        dimension_source_name = str(benchmark.get("dimension_name") or "").strip() or None
        dimension_value = benchmark.get("dimension_value")
        start_date = benchmark.get("start_date")
        end_date = benchmark.get("end_date")

        # Inject dates so `_query_governed_metric_value` has them via context hack
        context["benchmark_kwargs"] = {
            "start_date": start_date,
            "end_date": end_date,
            "benchmark_index": id(benchmark),
        }

        metric_match = lookup_match(kpi_matches, source_name)
        if not metric_match or metric_match.get("status") == "unmatched":
            rows.append(
                {
                    "label": label,
                    "source_name": source_name,
                    "target_name": None,
                    "target_label": None,
                    "dimension_name": dimension_source_name,
                    "dimension_value": dimension_value,
                    "start_date": start_date,
                    "end_date": end_date,
                    "expected_value": expected_value,
                    "governed_value": None,
                    "variance": None,
                    "variance_pct": None,
                    "status": "pending",
                    "rationale": "No governed KPI match is available for automated trust comparison.",
                }
            )
            continue

        if metric_match.get("target_type") != "metric":
            rows.append(
                {
                    "label": label,
                    "source_name": source_name,
                    "target_name": metric_match.get("target_name"),
                    "target_label": metric_match.get("target_label"),
                    "dimension_name": dimension_source_name,
                    "dimension_value": dimension_value,
                    "start_date": start_date,
                    "end_date": end_date,
                    "expected_value": expected_value,
                    "governed_value": None,
                    "variance": None,
                    "variance_pct": None,
                    "status": "pending",
                    "rationale": "The best match is a calculated field. Promote it to a governed KPI before relying on automated trust comparison.",
                }
            )
            continue

        target_dimension_name = None
        target_dimension_label = None
        if dimension_source_name:
            dimension_match = lookup_match(dimension_matches, dimension_source_name)
            if not dimension_match or dimension_match.get("status") == "unmatched":
                rows.append(
                    {
                        "label": label,
                        "source_name": source_name,
                        "target_name": metric_match.get("target_name"),
                        "target_label": metric_match.get("target_label"),
                        "dimension_name": dimension_source_name,
                        "dimension_value": dimension_value,
                        "start_date": start_date,
                        "end_date": end_date,
                        "expected_value": expected_value,
                        "governed_value": None,
                        "variance": None,
                        "variance_pct": None,
                        "status": "pending",
                        "rationale": "No governed dimension match is available for the benchmark slice.",
                    }
                )
                continue
            if dimension_value is None:
                rows.append(
                    {
                        "label": label,
                        "source_name": source_name,
                        "target_name": metric_match.get("target_name"),
                        "target_label": metric_match.get("target_label"),
                        "dimension_name": dimension_source_name,
                        "dimension_value": dimension_value,
                        "start_date": start_date,
                        "end_date": end_date,
                        "expected_value": expected_value,
                        "governed_value": None,
                        "variance": None,
                        "variance_pct": None,
                        "status": "pending",
                        "rationale": "A benchmark slice needs a concrete dimension_value for automated comparison.",
                    }
                )
                continue
            target_dimension_name = str(dimension_match.get("target_name") or "") or None
            target_dimension_label = str(dimension_match.get("target_label") or "") or None

        governed_value = _query_governed_metric_value(
            db,
            context=context,
            metric_name=str(metric_match["target_name"]),
            dimension_name=target_dimension_name,
            dimension_value=dimension_value,
        )
        if governed_value is None:
            rows.append(
                {
                    "label": label,
                    "source_name": source_name,
                    "target_name": metric_match.get("target_name"),
                    "target_label": metric_match.get("target_label"),
                    "dimension_name": target_dimension_label or dimension_source_name,
                    "dimension_value": dimension_value,
                    "start_date": start_date,
                    "end_date": end_date,
                    "expected_value": expected_value,
                    "governed_value": None,
                    "variance": None,
                    "variance_pct": None,
                    "status": "pending",
                    "rationale": "The governed model did not return a comparable value for this benchmark slice.",
                }
            )
            continue

        variance = governed_value - expected_value
        variance_pct = 0.0 if expected_value == 0 and governed_value == 0 else None
        if expected_value != 0:
            variance_pct = abs(variance) / abs(expected_value)

        status = comparison_status(variance_pct)
        if status == "pass":
            rationale = "Governed value is within the strict migration variance threshold."
        elif status == "review":
            rationale = "Governed value is close, but manual review is recommended before certifying cutover."
        else:
            rationale = "Governed value is materially different from the incumbent benchmark and should block certification until resolved."

        rows.append(
            {
                "label": label,
                "source_name": source_name,
                "target_name": metric_match.get("target_name"),
                "target_label": metric_match.get("target_label"),
                "dimension_name": target_dimension_label or dimension_source_name,
                "dimension_value": dimension_value,
                "start_date": start_date,
                "end_date": end_date,
                "expected_value": expected_value,
                "governed_value": round(governed_value, 4),
                "variance": round(float(variance), 4),
                "variance_pct": round(float(variance_pct), 4) if variance_pct is not None else None,
                "status": status,
                "rationale": rationale,
            }
        )

    summary = {
        "compared_rows": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "review_count": sum(1 for row in rows if row["status"] == "review"),
        "fail_count": sum(1 for row in rows if row["status"] == "fail"),
        "pending_count": sum(1 for row in rows if row["status"] == "pending"),
    }
    return {"rows": rows, "summary": summary}


def analyze_migration_bundle(
    db: Session,
    *,
    semantic_model: SemanticModel,
    source_tool: str,
    dashboard_names: list[str],
    report_names: list[str],
    kpi_names: list[str],
    dimension_names: list[str],
    benchmark_rows: list[dict[str, Any]],
    notes: str | None,
) -> dict[str, Any]:
    context = semantic_context(db, semantic_model.id)
    dimensions = [dimension for dimension in context["dimensions"] if dimension.visibility == "public"]
    recommended_pack = recommend_pack(dashboard_names + report_names, kpi_names, dimension_names, notes)
    kpi_matches = _match_kpis(db, semantic_model.id, kpi_names)
    dimension_matches = _match_dimensions(dimensions, dimension_names)
    automated_trust_comparison = _automated_trust_comparison(
        db,
        semantic_model=semantic_model,
        kpi_matches=kpi_matches,
        dimension_matches=dimension_matches,
        benchmark_rows=benchmark_rows,
    )

    dashboard_matches = build_output_suggestions(
        dashboard_names,
        source_tool=source_tool,
        kpi_matches=kpi_matches,
    )
    report_matches = build_output_suggestions(
        report_names,
        source_tool=source_tool,
        kpi_matches=kpi_matches,
    )

    primary_asset_title = (
        (dashboard_names[0] if dashboard_names else None)
        or (report_names[0] if report_names else None)
        or f"{recommended_pack['title']} Migration"
    )
    matched_targets = matched_target_labels(kpi_matches)[:3]
    bootstrap_goal = (
        f"Rebuild the {tool_label(source_tool)} asset '{primary_asset_title}' as a governed executive reporting flow focused on {', '.join(matched_targets) if matched_targets else 'trusted KPI monitoring'} using the {recommended_pack['title']}."
    )

    unmatched_assets = sum(1 for match in kpi_matches + dimension_matches if match["status"] == "unmatched")
    coverage = {
        "matched_kpis": sum(1 for match in kpi_matches if match["status"] in {"matched", "promote"}),
        "total_kpis": len(kpi_matches),
        "matched_dimensions": sum(1 for match in dimension_matches if match["status"] == "matched"),
        "total_dimensions": len(dimension_matches),
        "unmatched_assets": unmatched_assets,
    }

    return {
        "source_tool": source_tool,
        "semantic_model_id": semantic_model.id,
        "recommended_launch_pack_id": recommended_pack["id"],
        "recommended_launch_pack_title": recommended_pack["title"],
        "primary_asset_title": primary_asset_title,
        "dashboard_matches": dashboard_matches,
        "report_matches": report_matches,
        "kpi_matches": kpi_matches,
        "dimension_matches": dimension_matches,
        "trust_validation_checks": build_trust_checks(
            kpi_matches=kpi_matches,
            dimension_matches=dimension_matches,
            dashboard_names=dashboard_names,
            report_names=report_names,
            automated_trust_comparison=automated_trust_comparison,
        ),
        "automated_trust_comparison": automated_trust_comparison,
        "bootstrap_goal": bootstrap_goal,
        "coverage": coverage,
    }


def bootstrap_migration_pack(
    db: Session,
    *,
    workspace_id: str,
    semantic_model: SemanticModel,
    source_tool: str,
    dashboard_names: list[str],
    report_names: list[str],
    kpi_names: list[str],
    dimension_names: list[str],
    benchmark_rows: list[dict[str, Any]],
    notes: str | None,
    created_by: str,
    email_to: list[str],
    create_schedule: bool,
    dashboard_name_override: str | None = None,
) -> dict[str, Any]:
    analysis = analyze_migration_bundle(
        db,
        semantic_model=semantic_model,
        source_tool=source_tool,
        dashboard_names=dashboard_names,
        report_names=report_names,
        kpi_names=kpi_names,
        dimension_names=dimension_names,
        benchmark_rows=benchmark_rows,
        notes=notes,
    )

    recommended_pack = get_launch_pack(str(analysis["recommended_launch_pack_id"])) or get_launch_pack("leadership_exec")
    provisioned = provision_launch_pack(
        db,
        workspace_id=workspace_id,
        semantic_model=semantic_model,
        pack=recommended_pack,
        created_by=created_by,
        email_to=email_to,
        create_schedule=create_schedule,
        dashboard_name_override=dashboard_name_override or f"{analysis['primary_asset_title']} Migration Pack",
        description_override=f"Migration bootstrap from {tool_label(source_tool)} for {analysis['primary_asset_title']}",
        report_goal_override=str(analysis["bootstrap_goal"]),
    )

    dashboard = provisioned["dashboard"]
    current_layout = dict(dashboard.layout or {})
    current_layout["migration"] = {
        "source_tool": source_tool,
        "dashboard_names": dashboard_names,
        "report_names": report_names,
        "kpi_names": kpi_names,
        "dimension_names": dimension_names,
        "recommended_launch_pack_id": analysis["recommended_launch_pack_id"],
        "automated_trust_comparison": analysis["automated_trust_comparison"]["summary"],
    }
    dashboard.layout = current_layout
    db.flush()

    return {
        "analysis": analysis,
        "provisioned": provisioned,
    }
