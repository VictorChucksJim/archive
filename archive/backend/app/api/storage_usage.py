from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import StorageUsageOut
from app.services.quota import get_quota_bytes, get_used_bytes

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.get("/usage", response_model=StorageUsageOut)
def storage_usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    used = get_used_bytes(db, user.id)
    quota = get_quota_bytes(db, user.id)
    return StorageUsageOut(used_bytes=used, quota_bytes=quota, remaining_bytes=max(quota - used, 0))
