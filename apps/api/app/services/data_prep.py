from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_package_paths
from app.models.entities import AIActionHistory, AuditLog, Dataset, DatasetField, TransformationLineage

bootstrap_package_paths()
from dataprep.planner import (  # noqa: E402
    build_transformation_lineage,
    generate_calculated_field_suggestions,
    generate_cleaning_steps,
    generate_join_suggestions,
    generate_union_suggestions,
)


def _feedback_summary(db: Session, dataset_id: str) -> dict[str, dict[str, int]]:
    rows = db.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "dataset",
            AuditLog.entity_id == dataset_id,
            AuditLog.action == "data_prep.feedback",
        )
    ).all()
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        metadata = row.metadata_json or {}
        step_id = str(metadata.get("step_id") or "")
        decision = str(metadata.get("decision") or "")
        if not step_id or decision not in {"approve", "reject"}:
            continue
        current = summary.setdefault(step_id, {"approved": 0, "rejected": 0})
        current["approved" if decision == "approve" else "rejected"] += 1
    return summary


def _load_dataset_frame(db: Session, dataset: Dataset, limit: int = 500) -> pd.DataFrame:
    bind = db.get_bind()
    query = text(f'SELECT * FROM "{dataset.physical_table}" LIMIT :limit')
    with bind.connect() as connection:
        return pd.read_sql_query(query, connection, params={"limit": limit})


def _sample_lookup(dataset: Dataset) -> dict[str, dict[str, Any]]:
    quality = dataset.quality_profile or {}
    return {
        str(item.get("name")): item
        for item in quality.get("field_profiles", [])
        if isinstance(item, dict) and item.get("name")
    }


def _cleaning_steps(dataset: Dataset, frame: pd.DataFrame, feedback_map: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    return generate_cleaning_steps(
        quality_profile=dict(dataset.quality_profile or {}),
        frame=frame,
        feedback_map=feedback_map,
    )


def _join_suggestions(db: Session, dataset: Dataset) -> list[dict[str, Any]]:
    current_samples = _sample_lookup(dataset)
    current_fields = {field.name: field.data_type for field in db.scalars(select(DatasetField).where(DatasetField.dataset_id == dataset.id)).all()}
    other_datasets = db.scalars(
        select(Dataset).where(Dataset.workspace_id == dataset.workspace_id, Dataset.id != dataset.id).order_by(Dataset.created_at.desc())
    ).all()
    candidate_payloads: list[dict[str, Any]] = []
    for candidate in other_datasets:
        candidate_fields = {
            field.name: field.data_type
            for field in db.scalars(select(DatasetField).where(DatasetField.dataset_id == candidate.id)).all()
        }
        candidate_payloads.append(
            {
                "id": candidate.id,
                "name": candidate.name,
                "fields": candidate_fields,
                "samples": _sample_lookup(candidate),
            }
        )
    return generate_join_suggestions(
        dataset_name=dataset.name,
        current_fields=current_fields,
        current_samples=current_samples,
        other_datasets=candidate_payloads,
    )


def _union_suggestions(db: Session, dataset: Dataset) -> list[dict[str, Any]]:
    current_fields = {
        field.name: field.data_type for field in db.scalars(select(DatasetField).where(DatasetField.dataset_id == dataset.id)).all()
    }
    other_datasets = db.scalars(
        select(Dataset).where(Dataset.workspace_id == dataset.workspace_id, Dataset.id != dataset.id).order_by(Dataset.created_at.desc())
    ).all()
    candidate_payloads: list[dict[str, Any]] = []
    for candidate in other_datasets:
        candidate_fields = {
            field.name: field.data_type for field in db.scalars(select(DatasetField).where(DatasetField.dataset_id == candidate.id)).all()
        }
        candidate_payloads.append({"id": candidate.id, "name": candidate.name, "fields": candidate_fields})
    return generate_union_suggestions(
        dataset_name=dataset.name,
        current_fields=set(current_fields.keys()),
        other_datasets=candidate_payloads,
    )


def _calculated_field_suggestions(db: Session, dataset: Dataset) -> list[dict[str, Any]]:
    fields = [field.name for field in db.scalars(select(DatasetField).where(DatasetField.dataset_id == dataset.id)).all()]
    return generate_calculated_field_suggestions(fields)


def _autopilot_state(dataset: Dataset) -> dict[str, Any]:
    quality = dataset.quality_profile or {}
    autopilot = quality.get("autopilot") if isinstance(quality.get("autopilot"), dict) else {}
    return dict(autopilot)


def _transformation_lineage(dataset: Dataset) -> list[dict[str, Any]]:
    return build_transformation_lineage(dict(dataset.quality_profile or {}))


def build_data_prep_plan(db: Session, dataset: Dataset) -> dict[str, Any]:
    feedback_map = _feedback_summary(db, dataset.id)
    frame = _load_dataset_frame(db, dataset)
    cleaning_steps = _cleaning_steps(dataset, frame, feedback_map)
    autopilot = _autopilot_state(dataset)
    applied_steps = autopilot.get("applied_steps") if isinstance(autopilot.get("applied_steps"), dict) else {}
    for step in cleaning_steps:
        applied_state = applied_steps.get(step["step_id"]) if isinstance(applied_steps.get(step["step_id"]), dict) else {}
        step["applied"] = bool(applied_state.get("applied"))
        step["applied_at"] = applied_state.get("applied_at")

    notes: list[str] = []
    if not cleaning_steps:
        notes.append("No urgent cleaning interventions were detected from the sampled data and quality profile.")
    join_suggestions = _join_suggestions(db, dataset)
    if not join_suggestions:
        notes.append("No high-confidence join suggestion passed the current threshold.")
    union_suggestions = _union_suggestions(db, dataset)
    if not union_suggestions:
        notes.append("No union-compatible sibling dataset passed the current threshold.")
    calculated_field_suggestions = _calculated_field_suggestions(db, dataset)
    if not calculated_field_suggestions:
        notes.append("No high-confidence calculated field suggestion was inferred from current field names.")
    if any(step.get("applied") for step in cleaning_steps):
        notes.append("Applied autopilot steps are recorded in governed prep lineage; raw synced tables remain unchanged until promoted downstream.")

    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "dataset_quality_status": dataset.quality_status,
        "generated_at": datetime.now(timezone.utc),
        "cleaning_steps": cleaning_steps,
        "join_suggestions": join_suggestions,
        "union_suggestions": union_suggestions,
        "calculated_field_suggestions": calculated_field_suggestions,
        "transformation_lineage": _transformation_lineage(dataset),
        "notes": notes,
    }


def apply_data_prep_action(db: Session, dataset: Dataset, *, step_id: str, action: str) -> dict[str, Any]:
    plan = build_data_prep_plan(db, dataset)
    step = next((item for item in plan["cleaning_steps"] if item["step_id"] == step_id), None)
    if not step:
        raise ValueError("Prep step not found for dataset")

    quality = dict(dataset.quality_profile or {})
    autopilot = _autopilot_state(dataset)
    applied_steps = dict(autopilot.get("applied_steps") or {})
    history = list(autopilot.get("history") or [])
    recorded_at = datetime.now(timezone.utc).isoformat()

    if action == "apply":
        applied_steps[step_id] = {
            "applied": True,
            "applied_at": recorded_at,
            "title": step["title"],
            "step_type": step["step_type"],
            "target_fields": step["target_fields"],
        }
        status = "applied"
        note = f"Prep step '{step['title']}' applied to governed prep history. Raw synced data remains unchanged."
        description = f"Applied prep step '{step['title']}' through the AI Data Prep Autopilot."
    else:
        applied_steps.pop(step_id, None)
        status = "rolled_back"
        note = f"Prep step '{step['title']}' rolled back from governed prep history."
        description = f"Rolled back prep step '{step['title']}' from the AI Data Prep Autopilot."

    history.insert(
        0,
        {
            "source": "ai_data_prep_autopilot",
            "description": description,
            "affected_fields": step["target_fields"],
            "status": status,
            "recorded_at": recorded_at,
            "step_id": step_id,
        },
    )

    autopilot["applied_steps"] = applied_steps
    autopilot["history"] = history[:25]
    quality["autopilot"] = autopilot
    dataset.quality_profile = quality
    db.add(dataset)

    # Record transformation lineage
    current_step_count = db.scalar(
        select(func.count(TransformationLineage.id)).where(
            TransformationLineage.dataset_id == dataset.id,
            TransformationLineage.workspace_id == dataset.workspace_id,
        )
    ) or 0
    tl = TransformationLineage(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.id,
        step_order=current_step_count + 1,
        step_id=step_id,
        step_type=step.get("step_type", "clean"),
        input_fields=step.get("target_fields", []),
        output_fields=step.get("target_fields", []),
        description=description,
        status=status,
        applied_at=datetime.now(timezone.utc) if action == "apply" else None,
        rolled_back_at=datetime.now(timezone.utc) if action != "apply" else None,
    )
    db.add(tl)

    # Record AI action history
    db.add(AIActionHistory(
        workspace_id=dataset.workspace_id,
        action_type="data_prep_action",
        input_summary=f"{action.title()} prep step '{step['title']}' on dataset {dataset.name}",
        output_summary=note,
        artifact_ref=dataset.id,
        artifact_type="dataset",
        status="completed",
    ))

    return {
        "dataset_id": dataset.id,
        "step_id": step_id,
        "action": action,
        "status": status,
        "note": note,
    }


def feedback_counts_for_step(db: Session, dataset_id: str, step_id: str) -> dict[str, int]:
    summary = _feedback_summary(db, dataset_id)
    return summary.get(step_id, {"approved": 0, "rejected": 0})
