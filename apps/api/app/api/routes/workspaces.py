from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, get_db
from app.models.entities import Organization, RoleAssignment, User, Workspace
from app.schemas.orgs import CreateWorkspaceRequest, WorkspaceResponse
from app.services.audit import write_audit_log


router = APIRouter()


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WorkspaceResponse]:
    stmt = (
        select(Workspace)
        .join(RoleAssignment, RoleAssignment.workspace_id == Workspace.id)
        .where(RoleAssignment.user_id == current_user.id)
    )
    rows = db.scalars(stmt).all()
    return [
        WorkspaceResponse(id=workspace.id, organization_id=workspace.organization_id, name=workspace.name, key=workspace.key)
        for workspace in rows
    ]


@router.post("", response_model=WorkspaceResponse)
def create_workspace(
    payload: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    assignment = db.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == current_user.id,
            RoleAssignment.organization_id == payload.organization_id,
            RoleAssignment.workspace_id.is_(None),
        )
    )
    if not assignment or assignment.role not in {"Owner", "Admin"}:
        raise HTTPException(status_code=403, detail="Only owner or admin can create workspaces")

    org = db.get(Organization, payload.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    workspace = Workspace(organization_id=org.id, name=payload.name, key=payload.key)
    db.add(workspace)
    db.flush()

    db.add(RoleAssignment(user_id=current_user.id, organization_id=org.id, workspace_id=workspace.id, role="Owner"))
    write_audit_log(
        db,
        action="workspace.create",
        entity_type="workspace",
        entity_id=workspace.id,
        user=current_user,
        organization_id=org.id,
        workspace_id=workspace.id,
        metadata={"name": workspace.name},
    )
    db.commit()

    return WorkspaceResponse(id=workspace.id, organization_id=workspace.organization_id, name=workspace.name, key=workspace.key)
