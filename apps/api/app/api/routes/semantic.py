from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import Dataset, DatasetField, SemanticMetric, SemanticModel, User
from app.schemas.semantic import CreateSemanticModelRequest, SemanticModelResponse, ValidateSemanticModelResponse
from app.services.audit import write_audit_log
from app.services.semantic import create_semantic_model, validate_semantic_payload


router = APIRouter()


@router.get("/datasets")
def datasets(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[dict]:
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


@router.get("/models", response_model=list[SemanticModelResponse])
def list_models(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[SemanticModelResponse]:
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


@router.get("/models/{semantic_model_id}/metrics")
def list_metrics(
    semantic_model_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[dict]:
    model = db.get(SemanticModel, semantic_model_id)
    if not model or model.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Semantic model not found")

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
    model = db.get(SemanticModel, semantic_model_id)
    if not model or model.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Semantic model not found")

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


@router.post("/models/validate", response_model=ValidateSemanticModelResponse)
def validate_model(
    payload: CreateSemanticModelRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> ValidateSemanticModelResponse:
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == payload.base_dataset_id, Dataset.workspace_id == workspace_id)
    )
    errors = validate_semantic_payload(
        base_dataset=dataset,
        joins=payload.joins,
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
    dataset = db.scalar(
        select(Dataset).where(Dataset.id == payload.base_dataset_id, Dataset.workspace_id == workspace_id)
    )
    errors = validate_semantic_payload(
        base_dataset=dataset,
        joins=payload.joins,
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
        joins=payload.joins,
        metrics=[metric.model_dump() for metric in payload.metrics],
        dimensions=[dimension.model_dump() for dimension in payload.dimensions],
        calculated_fields=[calc.model_dump() for calc in payload.calculated_fields],
    )

    write_audit_log(
        db,
        action="semantic_model.create",
        entity_type="semantic_model",
        entity_id=model.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"model_key": model.model_key, "version": model.version},
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

