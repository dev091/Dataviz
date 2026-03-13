"""Lineage API routes — metric provenance and transformation history."""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import (
    CalculatedField,
    Dataset,
    DatasetField,
    MetricLineage,
    SemanticMetric,
    SemanticModel,
    TransformationLineage,
    User,
)

router = APIRouter()

AGG_FIELD_RE = re.compile(
    r"^(?:SUM|AVG|COUNT|MIN|MAX)\(\s*(?:([A-Za-z_][A-Za-z0-9_]*)\.)?([A-Za-z_][A-Za-z0-9_]*|\*)\s*\)$",
    re.IGNORECASE,
)
SIMPLE_FIELD_RE = re.compile(
    r"^(?:([A-Za-z_][A-Za-z0-9_]*)\.)?([A-Za-z_][A-Za-z0-9_]*)$",
)


def _extract_source_fields(formula: str) -> list[str]:
    """Parse a metric formula to extract referenced field names."""
    match = AGG_FIELD_RE.fullmatch(formula.strip())
    if match:
        field = match.group(2)
        return [] if field == "*" else [field]
    match = SIMPLE_FIELD_RE.fullmatch(formula.strip())
    if match:
        return [match.group(2)]
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
    keywords = {"SUM", "AVG", "COUNT", "MIN", "MAX", "sum", "avg", "count", "min", "max"}
    return [tok for tok in tokens if tok not in keywords]


def record_metric_lineage(
    db: Session,
    *,
    workspace_id: str,
    semantic_model: SemanticModel,
    metrics: list[SemanticMetric],
    calculated_fields: list[CalculatedField],
) -> list[MetricLineage]:
    """Auto-populate MetricLineage entries from metric formulas and field references."""
    calc_field_names = {cf.name.lower() for cf in calculated_fields}
    entries: list[MetricLineage] = []

    for metric in metrics:
        source_fields = _extract_source_fields(metric.formula)
        for field_name in source_fields:
            if field_name.lower() in calc_field_names:
                source_type = "calculated_field"
            else:
                source_type = "raw_field"

            entry = MetricLineage(
                workspace_id=workspace_id,
                semantic_model_id=semantic_model.id,
                semantic_metric_id=metric.id,
                source_dataset_id=semantic_model.base_dataset_id,
                source_field=field_name,
                source_type=source_type,
                transformation_summary=f"{metric.aggregation.upper()}({field_name}) → {metric.name}",
                confidence=1.0,
            )
            db.add(entry)
            entries.append(entry)

        if not source_fields:
            entry = MetricLineage(
                workspace_id=workspace_id,
                semantic_model_id=semantic_model.id,
                semantic_metric_id=metric.id,
                source_dataset_id=semantic_model.base_dataset_id,
                source_field="*",
                source_type="aggregation",
                transformation_summary=f"{metric.formula} → {metric.name}",
                confidence=0.8,
            )
            db.add(entry)
            entries.append(entry)

    db.flush()
    return entries


@router.get("/metric/{metric_id}")
def get_metric_lineage(
    metric_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> dict:
    _ = current_user
    metric = db.get(SemanticMetric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")

    rows = db.scalars(
        select(MetricLineage)
        .where(
            MetricLineage.semantic_metric_id == metric_id,
            MetricLineage.workspace_id == workspace_id,
        )
        .order_by(MetricLineage.created_at.asc())
    ).all()

    model = db.get(SemanticModel, metric.semantic_model_id)
    dataset = db.get(Dataset, model.base_dataset_id) if model else None

    return {
        "metric_id": metric_id,
        "metric_name": metric.name,
        "metric_formula": metric.formula,
        "semantic_model": model.name if model else None,
        "base_dataset": dataset.name if dataset else None,
        "lineage_entries": [
            {
                "id": row.id,
                "source_dataset_id": row.source_dataset_id,
                "source_field": row.source_field,
                "source_type": row.source_type,
                "transformation_summary": row.transformation_summary,
                "confidence": row.confidence,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@router.get("/dataset/{dataset_id}")
def get_dataset_transformation_lineage(
    dataset_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> dict:
    _ = current_user
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    rows = db.scalars(
        select(TransformationLineage)
        .where(
            TransformationLineage.dataset_id == dataset_id,
            TransformationLineage.workspace_id == workspace_id,
        )
        .order_by(TransformationLineage.step_order.asc())
    ).all()

    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.name,
        "transformation_steps": [
            {
                "id": row.id,
                "step_order": row.step_order,
                "step_id": row.step_id,
                "step_type": row.step_type,
                "input_fields": row.input_fields,
                "output_fields": row.output_fields,
                "description": row.description,
                "status": row.status,
                "applied_at": row.applied_at,
                "rolled_back_at": row.rolled_back_at,
            }
            for row in rows
        ],
    }


@router.get("/model/{model_id}")
def get_model_lineage(
    model_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> dict:
    _ = current_user
    model = db.get(SemanticModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Semantic model not found")

    dataset = db.get(Dataset, model.base_dataset_id)

    metric_lineage_rows = db.scalars(
        select(MetricLineage)
        .where(MetricLineage.semantic_model_id == model_id, MetricLineage.workspace_id == workspace_id)
        .order_by(MetricLineage.created_at.asc())
    ).all()

    transformation_rows = db.scalars(
        select(TransformationLineage)
        .where(TransformationLineage.dataset_id == model.base_dataset_id, TransformationLineage.workspace_id == workspace_id)
        .order_by(TransformationLineage.step_order.asc())
    ).all() if dataset else []

    metrics = db.scalars(
        select(SemanticMetric).where(SemanticMetric.semantic_model_id == model_id)
    ).all()
    metric_name_by_id = {m.id: m.name for m in metrics}

    fields = db.scalars(
        select(DatasetField).where(DatasetField.dataset_id == model.base_dataset_id)
    ).all() if dataset else []

    return {
        "model_id": model_id,
        "model_name": model.name,
        "base_dataset": {
            "id": dataset.id if dataset else None,
            "name": dataset.name if dataset else None,
            "connection_id": dataset.connection_id if dataset else None,
            "source_table": dataset.source_table if dataset else None,
            "field_count": len(fields),
        },
        "metric_lineage": [
            {
                "metric_name": metric_name_by_id.get(row.semantic_metric_id, row.semantic_metric_id),
                "source_field": row.source_field,
                "source_type": row.source_type,
                "transformation_summary": row.transformation_summary,
                "confidence": row.confidence,
            }
            for row in metric_lineage_rows
        ],
        "transformation_lineage": [
            {
                "step_order": row.step_order,
                "step_type": row.step_type,
                "description": row.description,
                "status": row.status,
                "input_fields": row.input_fields,
                "output_fields": row.output_fields,
            }
            for row in transformation_rows
        ],
        "lineage_summary": {
            "metrics_with_lineage": len(set(row.semantic_metric_id for row in metric_lineage_rows)),
            "total_metrics": len(metrics),
            "transformation_steps": len(transformation_rows),
            "active_transformations": sum(1 for row in transformation_rows if row.status == "applied"),
        },
    }
