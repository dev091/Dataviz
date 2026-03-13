from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import AIQuerySession, AuditLog, Dashboard, DataConnection, Dataset, InsightArtifact, Organization, SemanticModel, User, Workspace
from app.services.audit import write_audit_log
from app.services.billing import billing_snapshot


router = APIRouter()


class SubscriptionUpdateRequest(BaseModel):
    plan_tier: str = Field(min_length=2, max_length=32)
    subscription_status: str = Field(min_length=2, max_length=32)
    billing_email: EmailStr
    seat_limit: int = Field(ge=1, le=100000)


def _workspace(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/audit-logs")
def audit_logs(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> list[dict]:
    workspace = _workspace(db, workspace_id)
    rows = db.scalars(
        select(AuditLog)
        .where(
            or_(
                AuditLog.workspace_id == workspace_id,
                (AuditLog.workspace_id.is_(None) & (AuditLog.organization_id == workspace.organization_id)),
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": row.id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "user_id": row.user_id,
            "metadata": row.metadata_json,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/usage")
def usage_metrics(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> dict:
    datasets = db.scalar(select(func.count(Dataset.id)).where(Dataset.workspace_id == workspace_id)) or 0
    semantic_models = db.scalar(select(func.count(SemanticModel.id)).where(SemanticModel.workspace_id == workspace_id)) or 0
    dashboards = db.scalar(select(func.count(Dashboard.id)).where(Dashboard.workspace_id == workspace_id)) or 0
    connections = db.scalar(select(func.count(DataConnection.id)).where(DataConnection.workspace_id == workspace_id)) or 0

    return {
        "datasets": datasets,
        "semantic_models": semantic_models,
        "dashboards": dashboards,
        "connections": connections,
    }


@router.get("/subscription")
def subscription_details(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> dict:
    workspace = _workspace(db, workspace_id)
    organization = db.get(Organization, workspace.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    return billing_snapshot(organization)


@router.put("/subscription")
def update_subscription(
    payload: SubscriptionUpdateRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Owner")),
    db: Session = Depends(get_db),
) -> dict:
    workspace = _workspace(db, workspace_id)
    organization = db.get(Organization, workspace.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    organization.plan_tier = payload.plan_tier
    organization.subscription_status = payload.subscription_status
    organization.billing_email = payload.billing_email
    organization.seat_limit = payload.seat_limit

    write_audit_log(
        db,
        action="organization.subscription.update",
        entity_type="organization",
        entity_id=organization.id,
        user=current_user,
        organization_id=organization.id,
        workspace_id=workspace_id,
        metadata={
            "plan_tier": organization.plan_tier,
            "subscription_status": organization.subscription_status,
            "billing_email": organization.billing_email,
            "seat_limit": organization.seat_limit,
        },
    )
    db.commit()

    return billing_snapshot(organization)


@router.get("/insights")
def recent_insights(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = current_user
    rows = db.scalars(
        select(InsightArtifact)
        .where(InsightArtifact.workspace_id == workspace_id)
        .order_by(InsightArtifact.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": row.id,
            "insight_type": row.insight_type,
            "title": row.title,
            "body": row.body,
            "metric_id": row.metric_id,
            "created_at": row.created_at,
            "data": row.data,
        }
        for row in rows
    ]


@router.get("/ai-trust-history")
def ai_trust_history(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> list[dict]:
    _ = current_user
    items: list[dict] = []

    query_rows = db.execute(
        select(AIQuerySession, SemanticModel)
        .join(SemanticModel, SemanticModel.id == AIQuerySession.semantic_model_id)
        .where(AIQuerySession.workspace_id == workspace_id)
        .order_by(AIQuerySession.created_at.desc())
        .limit(40)
    ).all()
    for session, model in query_rows:
        items.append(
            {
                "id": session.id,
                "artifact_type": "nl_query",
                "title": session.question,
                "summary": session.summary,
                "source_label": model.name,
                "prompt_or_trigger": session.question,
                "trust_signals": ["semantic-grounded", "query-plan", "agent-trace"],
                "created_at": session.created_at,
            }
        )

    audit_rows = db.execute(
        select(AuditLog, Dashboard)
        .join(Dashboard, Dashboard.id == AuditLog.entity_id, isouter=True)
        .where(
            AuditLog.workspace_id == workspace_id,
            AuditLog.action.in_(["dashboard.report_pack.generate", "dashboard.auto_compose"]),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(40)
    ).all()
    for audit, dashboard in audit_rows:
        metadata = audit.metadata_json or {}
        action = str(audit.action)
        artifact_type = "report_pack" if action == "dashboard.report_pack.generate" else "dashboard_auto_compose"
        trust_signals = ["audit-logged", "dashboard-governed"]
        if artifact_type == "report_pack":
            trust_signals.append("ai-summary")
        else:
            trust_signals.append("layout-generated")
        items.append(
            {
                "id": audit.id,
                "artifact_type": artifact_type,
                "title": (dashboard.name if dashboard else "Dashboard") if artifact_type == "dashboard_auto_compose" else f"Report pack for {dashboard.name if dashboard else 'dashboard'}",
                "summary": (
                    f"Audience: {metadata.get('audience', 'Executive leadership')} | Goal: {metadata.get('goal', 'Executive reporting')}"
                    if artifact_type == "report_pack"
                    else f"Auto-composed governed layout for {dashboard.name if dashboard else 'dashboard'}"
                ),
                "source_label": dashboard.name if dashboard else None,
                "prompt_or_trigger": str(metadata.get("goal") or metadata.get("audience") or action),
                "trust_signals": trust_signals,
                "created_at": audit.created_at,
            }
        )

    insight_rows = db.scalars(
        select(InsightArtifact)
        .where(InsightArtifact.workspace_id == workspace_id)
        .order_by(InsightArtifact.created_at.desc())
        .limit(40)
    ).all()
    for artifact in insight_rows:
        artifact_data = artifact.data or {}
        trust_signals = ["monitoring-artifact"]
        if isinstance(artifact_data.get("audiences"), list) and artifact_data.get("audiences"):
            trust_signals.append("audience-routed")
        if isinstance(artifact_data.get("suggested_actions"), list) and artifact_data.get("suggested_actions"):
            trust_signals.append("action-guided")
        if isinstance(artifact_data.get("investigation_paths"), list) and artifact_data.get("investigation_paths"):
            trust_signals.append("investigation-ready")
        items.append(
            {
                "id": artifact.id,
                "artifact_type": "proactive_insight",
                "title": artifact.title,
                "summary": artifact.body,
                "source_label": str(artifact_data.get("metric") or artifact_data.get("dataset_name") or artifact.insight_type),
                "prompt_or_trigger": "System-generated proactive monitoring artifact",
                "trust_signals": trust_signals,
                "created_at": artifact.created_at,
            }
        )

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:60]
