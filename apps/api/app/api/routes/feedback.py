"""Feedback API routes — usefulness instrumentation for AI-generated artifacts."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import ArtifactFeedback, User
from app.services.audit import write_audit_log

router = APIRouter()

ALLOWED_ARTIFACT_TYPES = {
    "alert", "insight", "nl_query", "report_pack",
    "dashboard_compose", "semantic_draft", "data_prep",
}
ALLOWED_RATINGS = {"useful", "not_useful", "dismissed", "snoozed"}


class FeedbackRequest(BaseModel):
    artifact_type: str = Field(min_length=2, max_length=64)
    artifact_id: str = Field(min_length=1, max_length=36)
    rating: str = Field(min_length=2, max_length=16)
    comment: str | None = Field(default=None, max_length=1000)


@router.post("")
def submit_feedback(
    payload: FeedbackRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> dict:
    if payload.artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported artifact_type '{payload.artifact_type}'")
    if payload.rating not in ALLOWED_RATINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported rating '{payload.rating}'")

    feedback = ArtifactFeedback(
        workspace_id=workspace_id,
        user_id=current_user.id,
        artifact_type=payload.artifact_type,
        artifact_id=payload.artifact_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)

    write_audit_log(
        db,
        action="artifact.feedback.submit",
        entity_type="artifact_feedback",
        entity_id=feedback.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "artifact_type": payload.artifact_type,
            "artifact_id": payload.artifact_id,
            "rating": payload.rating,
        },
    )
    db.commit()

    return {
        "id": feedback.id,
        "artifact_type": feedback.artifact_type,
        "artifact_id": feedback.artifact_id,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "created_at": feedback.created_at,
    }


@router.get("/stats")
def feedback_stats(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> dict:
    _ = current_user
    rows = db.execute(
        select(
            ArtifactFeedback.artifact_type,
            ArtifactFeedback.rating,
            func.count(ArtifactFeedback.id),
        )
        .where(ArtifactFeedback.workspace_id == workspace_id)
        .group_by(ArtifactFeedback.artifact_type, ArtifactFeedback.rating)
    ).all()

    stats: dict[str, dict[str, int]] = {}
    for artifact_type, rating, count in rows:
        category = stats.setdefault(artifact_type, {})
        category[rating] = count

    summary: dict[str, dict] = {}
    for artifact_type, counts in stats.items():
        total = sum(counts.values())
        useful = counts.get("useful", 0)
        not_useful = counts.get("not_useful", 0)
        dismissed = counts.get("dismissed", 0)

        summary[artifact_type] = {
            "total_feedback": total,
            "useful": useful,
            "not_useful": not_useful,
            "dismissed": dismissed,
            "snoozed": counts.get("snoozed", 0),
            "usefulness_rate": round(useful / total, 4) if total > 0 else None,
            "false_positive_rate": round(not_useful / total, 4) if total > 0 else None,
            "dismiss_rate": round(dismissed / total, 4) if total > 0 else None,
        }

    return {
        "workspace_id": workspace_id,
        "by_artifact_type": summary,
        "total_feedback": sum(s["total_feedback"] for s in summary.values()),
    }
