from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, hash_password, verify_password
from app.models.entities import Organization, RoleAssignment, User, Workspace


def _slugify(value: str) -> str:
    return "-".join(value.lower().strip().split())


def create_user_with_org(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    organization_name: str,
    workspace_name: str,
) -> tuple[User, Organization, Workspace]:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise ValueError("Email already registered")

    user = User(email=email, full_name=full_name, password_hash=hash_password(password))
    org_slug = _slugify(organization_name)
    org = Organization(
        name=organization_name,
        slug=f"{org_slug}-{email.split('@')[0]}",
        billing_email=email,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    workspace = Workspace(organization=org, name=workspace_name, key=_slugify(workspace_name)[:40])

    db.add_all([user, org, workspace])
    db.flush()

    db.add(RoleAssignment(user_id=user.id, organization_id=org.id, workspace_id=None, role="Owner"))
    db.add(RoleAssignment(user_id=user.id, organization_id=org.id, workspace_id=workspace.id, role="Owner"))
    db.flush()

    return user, org, workspace


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    access = create_token(
        subject=user.id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_minutes),
    )
    refresh = create_token(
        subject=user.id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_days),
    )
    return access, refresh
