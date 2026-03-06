from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, get_db
from app.core.security import decode_token
from app.models.entities import Organization, RoleAssignment, User, Workspace
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, SignupRequest, TokenResponse, WorkspaceAccess
from app.services.audit import write_audit_log
from app.services.auth import authenticate_user, create_user_with_org, issue_tokens


router = APIRouter()


def _workspace_access(db: Session, user_id: str) -> list[WorkspaceAccess]:
    stmt = (
        select(RoleAssignment, Workspace, Organization)
        .join(Workspace, Workspace.id == RoleAssignment.workspace_id)
        .join(Organization, Organization.id == Workspace.organization_id)
        .where(RoleAssignment.user_id == user_id, RoleAssignment.workspace_id.is_not(None))
    )
    rows = db.execute(stmt).all()
    return [
        WorkspaceAccess(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            organization_id=org.id,
            organization_name=org.name,
            role=assignment.role,
        )
        for assignment, workspace, org in rows
    ]


@router.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user, org, workspace = create_user_with_org(
            db,
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            organization_name=payload.organization_name,
            workspace_name=payload.workspace_name,
        )
        access, refresh = issue_tokens(user)
        write_audit_log(
            db,
            action="auth.signup",
            entity_type="user",
            entity_id=user.id,
            user=user,
            organization_id=org.id,
            workspace_id=workspace.id,
            metadata={"email": user.email},
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        email=user.email,
        workspaces=_workspace_access(db, user.id),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access, refresh = issue_tokens(user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        email=user.email,
        workspaces=_workspace_access(db, user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token_payload = decode_token(payload.refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.get(User, token_payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access, refresh_token = issue_tokens(user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        workspaces=_workspace_access(db, user.id),
    )


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        workspaces=_workspace_access(db, current_user.id),
    )
