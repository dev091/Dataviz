from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import AIActionHistory, Dataset, DatasetField, SemanticMetric, SemanticModel, User
from app.schemas.data_prep import (
    DataPrepActionRequest,
    DataPrepActionResponse,
    DataPrepFeedbackRequest,
    DataPrepFeedbackResponse,
    DataPrepPlanResponse,
)
from app.schemas.semantic import (
    CreateSemanticModelRequest,
    DraftSemanticModelRequest,
    DraftSemanticModelResponse,
    SemanticModelDetailResponse,
    SemanticModelResponse,
    SemanticTrustPanelResponse,
    ValidateSemanticModelResponse,
)
from app.services.audit import write_audit_log
from app.services.data_prep import apply_data_prep_action, build_data_prep_plan, feedback_counts_for_step
from app.services.semantic import (
    create_semantic_model,
    infer_semantic_model_draft,
    semantic_detail_payload,
    semantic_trust_panel,
    validate_semantic_payload,
)


router = APIRouter()


def _model_or_404(db: Session, workspace_id: str, semantic_model_id: str) -> SemanticModel:
    model = db.get(SemanticModel, semantic_model_id)
    if not model or model.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Semantic model not found")
    return model


def _dataset_or_404(db: Session, workspace_id: str, dataset_id: str) -> Dataset:
    dataset = db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.workspace_id == workspace_id))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get("/datasets")
def datasets(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = current_user
    rows = db.scalars(select(Dataset).where(Dataset.workspace_id == workspace_id).order_by(Dataset.created_at.desc())).all()
    payload: list[dict] = []
    for row in rows:
        fields = db.scalars(select(DatasetField).where(DatasetField.dataset_id == row.id).order_by(DatasetField.name.asc())).all()
        payload.append(
            {
                "id": row.id,
                "name": row.name,
                "source_table": row.source_table,
                "physical_table": row.physical_table,
                "row_count": row.row_count,
                "quality_status": row.quality_status,
                "quality_profile": row.quality_profile,
                "fields": [
                    {
                        "id": field.id,
                        "name": field.name,
                        "data_type": field.data_type,
                        "is_dimension": field.is_dimension,
                        "is_metric": field.is_metric,
                    }
                    for field in fields
                ],
            }
        )
    return payload


@router.get("/datasets/{dataset_id}/prep-plan", response_model=DataPrepPlanResponse)
def get_data_prep_plan(
    dataset_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> DataPrepPlanResponse:
    _ = current_user
    dataset = _dataset_or_404(db, workspace_id, dataset_id)
    plan = build_data_prep_plan(db, dataset)
    
    action_history = AIActionHistory(
        workspace_id=workspace_id,
        actor_id=current_user.id,
        action_type="data_prep_suggestion",
        input_summary=f"Generate data prep plan for dataset {dataset.name}",
        output_summary=f"Generated {len(plan['cleaning_steps'])} prep steps",
        artifact_ref=dataset.id,
        artifact_type="dataset",
        confidence_score=0.85,
        status="completed",
        metadata_json={
            "dataset_id": dataset.id,
            "step_count": len(plan["cleaning_steps"]),
        }
    )
    db.add(action_history)
    db.commit()

    return DataPrepPlanResponse(**plan)


@router.post("/datasets/{dataset_id}/prep-feedback", response_model=DataPrepFeedbackResponse)
def submit_data_prep_feedback(
    dataset_id: str,
    payload: DataPrepFeedbackRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> DataPrepFeedbackResponse:
    dataset = _dataset_or_404(db, workspace_id, dataset_id)
    write_audit_log(
        db,
        action="data_prep.feedback",
        entity_type="dataset",
        entity_id=dataset.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "step_id": payload.step_id,
            "decision": payload.decision,
            "comment": payload.comment,
        },
    )
    db.commit()
    counts = feedback_counts_for_step(db, dataset.id, payload.step_id)
    return DataPrepFeedbackResponse(
        dataset_id=dataset.id,
        step_id=payload.step_id,
        decision=payload.decision,
        approved=int(counts.get("approved", 0)),
        rejected=int(counts.get("rejected", 0)),
        note="Feedback captured and will influence future prep recommendations.",
    )


@router.post("/datasets/{dataset_id}/prep-actions", response_model=DataPrepActionResponse)
def execute_data_prep_action_route(
    dataset_id: str,
    payload: DataPrepActionRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> DataPrepActionResponse:
    dataset = _dataset_or_404(db, workspace_id, dataset_id)
    try:
        result = apply_data_prep_action(db, dataset, step_id=payload.step_id, action=payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    write_audit_log(
        db,
        action=f"data_prep.{payload.action}",
        entity_type="dataset",
        entity_id=dataset.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"step_id": payload.step_id, "status": result["status"]},
    )
    db.commit()
    return DataPrepActionResponse(**result)


@router.get("/models", response_model=list[SemanticModelResponse])
def list_models(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[SemanticModelResponse]:
    _ = current_user
    rows = db.scalars(
        select(SemanticModel).where(SemanticModel.workspace_id == workspace_id).order_by(SemanticModel.created_at.desc())
    ).all()
    return [
        SemanticModelResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            model_key=row.model_key,
            version=row.version,
            is_active=row.is_active,
            base_dataset_id=row.base_dataset_id,
            description=row.description,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/models/draft", response_model=DraftSemanticModelResponse)
def draft_model(
    payload: DraftSemanticModelRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> DraftSemanticModelResponse:
    _ = current_user
    dataset = _dataset_or_404(db, workspace_id, payload.dataset_id)
    fields = db.scalars(select(DatasetField).where(DatasetField.dataset_id == dataset.id).order_by(DatasetField.name.asc())).all()
    draft = infer_semantic_model_draft(
        dataset=dataset,
        fields=fields,
        name=payload.name,
        model_key=payload.model_key,
        description=payload.description,
    )

    action_history = AIActionHistory(
        workspace_id=workspace_id,
        actor_id=current_user.id,
        action_type="semantic_draft",
        input_summary=f"Draft semantic model from dataset {dataset.name}",
        output_summary=f"Generated draft with {len(draft['metrics'])} metrics, {len(draft['dimensions'])} dimensions",
        artifact_ref=dataset.id,
        artifact_type="dataset",
        confidence_score=0.9,
        status="completed",
        metadata_json={
            "dataset_id": dataset.id,
            "metric_count": len(draft["metrics"]),
            "dimension_count": len(draft["dimensions"]),
        }
    )
    db.add(action_history)
    db.commit()

    return DraftSemanticModelResponse(**draft)


@router.get("/models/{semantic_model_id}", response_model=SemanticModelDetailResponse)
def get_model(
    semantic_model_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> SemanticModelDetailResponse:
    _ = current_user
    model = _model_or_404(db, workspace_id, semantic_model_id)
    return SemanticModelDetailResponse(**semantic_detail_payload(db, model))


@router.get("/models/{semantic_model_id}/metrics")
def list_metrics(
    semantic_model_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = current_user
    _model_or_404(db, workspace_id, semantic_model_id)

    rows = db.scalars(
        select(SemanticMetric).where(SemanticMetric.semantic_model_id == semantic_model_id).order_by(SemanticMetric.name.asc())
    ).all()

    return [
        {
            "id": row.id,
            "name": row.name,
            "label": row.label,
            "formula": row.formula,
        }
        for row in rows
    ]


@router.get("/models/{semantic_model_id}/versions", response_model=list[SemanticModelResponse])
def list_versions(
    semantic_model_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[SemanticModelResponse]:
    _ = current_user
    model = _model_or_404(db, workspace_id, semantic_model_id)

    rows = db.scalars(
        select(SemanticModel)
        .where(SemanticModel.workspace_id == workspace_id, SemanticModel.model_key == model.model_key)
        .order_by(SemanticModel.version.desc())
    ).all()

    return [
        SemanticModelResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            model_key=row.model_key,
            version=row.version,
            is_active=row.is_active,
            base_dataset_id=row.base_dataset_id,
            description=row.description,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/models/{semantic_model_id}/trust-panel", response_model=SemanticTrustPanelResponse)
def get_trust_panel(
    semantic_model_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> SemanticTrustPanelResponse:
    _ = current_user
    model = _model_or_404(db, workspace_id, semantic_model_id)
    return SemanticTrustPanelResponse(**semantic_trust_panel(db, model))


@router.post("/models/validate", response_model=ValidateSemanticModelResponse)
def validate_model(
    payload: CreateSemanticModelRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> ValidateSemanticModelResponse:
    _ = current_user
    dataset = db.scalar(select(Dataset).where(Dataset.id == payload.base_dataset_id, Dataset.workspace_id == workspace_id))
    errors = validate_semantic_payload(
        base_dataset=dataset,
        joins=[join.model_dump() for join in payload.joins],
        metrics=[metric.model_dump() for metric in payload.metrics],
        dimensions=[dimension.model_dump() for dimension in payload.dimensions],
        calculated_fields=[calc.model_dump() for calc in payload.calculated_fields],
    )
    return ValidateSemanticModelResponse(valid=not errors, errors=errors)


@router.post("/models", response_model=SemanticModelResponse)
def create_model(
    payload: CreateSemanticModelRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> SemanticModelResponse:
    dataset = db.scalar(select(Dataset).where(Dataset.id == payload.base_dataset_id, Dataset.workspace_id == workspace_id))
    errors = validate_semantic_payload(
        base_dataset=dataset,
        joins=[join.model_dump() for join in payload.joins],
        metrics=[metric.model_dump() for metric in payload.metrics],
        dimensions=[dimension.model_dump() for dimension in payload.dimensions],
        calculated_fields=[calc.model_dump() for calc in payload.calculated_fields],
    )
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    model = create_semantic_model(
        db,
        workspace_id=workspace_id,
        created_by=current_user.id,
        name=payload.name,
        model_key=payload.model_key,
        description=payload.description,
        base_dataset_id=payload.base_dataset_id,
        joins=[join.model_dump() for join in payload.joins],
        metrics=[metric.model_dump() for metric in payload.metrics],
        dimensions=[dimension.model_dump() for dimension in payload.dimensions],
        calculated_fields=[calc.model_dump() for calc in payload.calculated_fields],
        governance=payload.governance.model_dump(),
    )

    write_audit_log(
        db,
        action="semantic_model.create",
        entity_type="semantic_model",
        entity_id=model.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"model_key": model.model_key, "version": model.version, "certification_status": payload.governance.certification_status},
    )
    db.commit()

    return SemanticModelResponse(
        id=model.id,
        workspace_id=model.workspace_id,
        name=model.name,
        model_key=model.model_key,
        version=model.version,
        is_active=model.is_active,
        base_dataset_id=model.base_dataset_id,
        description=model.description,
        created_at=model.created_at,
    )

