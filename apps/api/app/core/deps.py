from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.base import SessionLocal
from app.models.entities import RoleAssignment, User, Workspace


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


ROLE_ORDER = {
    "Viewer": 1,
    "Analyst": 2,
    "Admin": 3,
    "Owner": 4,
}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_error
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_error
    return user


def get_workspace_id(x_workspace_id: str = Header(default="", alias="X-Workspace-Id")) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")
    return x_workspace_id


def require_role(min_role: str):
    def _dependency(
        workspace_id: str = Depends(get_workspace_id),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        workspace = db.get(Workspace, workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        stmt = select(RoleAssignment).where(
            RoleAssignment.user_id == current_user.id,
            RoleAssignment.workspace_id == workspace_id,
        )
        assignment = db.scalar(stmt)
        if not assignment:
            org_stmt = select(RoleAssignment).where(
                RoleAssignment.user_id == current_user.id,
                RoleAssignment.organization_id == workspace.organization_id,
                RoleAssignment.workspace_id.is_(None),
            )
            assignment = db.scalar(org_stmt)

        if not assignment:
            raise HTTPException(status_code=403, detail="No workspace access")

        user_rank = ROLE_ORDER.get(assignment.role, 0)
        needed_rank = ROLE_ORDER.get(min_role, 99)
        if user_rank < needed_rank:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return current_user

    return _dependency
