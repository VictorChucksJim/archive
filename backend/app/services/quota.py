"""
Storage quota calculation.

Quota is expressed per-user (User.quota_bytes) so that different
plans/quotas can be introduced later without a schema change. Usage is
computed from the files table rather than cached, which is simpler and
correct for MVP scale; this can be optimized with a running counter
later if needed.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import File, User


def get_used_bytes(db: Session, user_id: uuid.UUID) -> int:
    """Sum of completed, non-deleted files. Pending (not-yet-confirmed)
    uploads are excluded until the browser confirms completion, but see
    reserve_pending_bytes for how in-flight uploads are still accounted
    for against quota to prevent a burst of concurrent uploads from
    exceeding it."""
    stmt = select(func.coalesce(func.sum(File.size_bytes), 0)).where(
        File.user_id == user_id,
        File.deleted_at.is_(None),
        File.status == "completed",
    )
    return db.execute(stmt).scalar_one()


def get_pending_bytes(db: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(File.size_bytes), 0)).where(
        File.user_id == user_id,
        File.deleted_at.is_(None),
        File.status == "pending",
    )
    return db.execute(stmt).scalar_one()


def get_quota_bytes(db: Session, user_id: uuid.UUID) -> int:
    user = db.get(User, user_id)
    return user.quota_bytes if user else 0


def has_capacity(db: Session, user_id: uuid.UUID, additional_bytes: int) -> bool:
    used = get_used_bytes(db, user_id) + get_pending_bytes(db, user_id)
    quota = get_quota_bytes(db, user_id)
    return (used + additional_bytes) <= quota
