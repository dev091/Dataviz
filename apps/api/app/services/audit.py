from sqlalchemy.orm import Session

from app.models.entities import AuditLog, User


def write_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    user: User | None,
    organization_id: str | None,
    workspace_id: str | None,
    metadata: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user.id if user else None,
        organization_id=organization_id,
        workspace_id=workspace_id,
        metadata_json=metadata or {},
    )
    db.add(log)
    db.flush()
    return log
