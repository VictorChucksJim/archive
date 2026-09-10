import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import AuditLog


def log_action(
    db: Session,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Best-effort structured audit log. Never include secrets, tokens,
    passwords, or file contents in audit entries."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=ip_address,
        user_agent=(user_agent[:1000] if user_agent else None),
    )
    db.add(entry)
    db.commit()
