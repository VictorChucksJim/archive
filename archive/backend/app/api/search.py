from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import File, Folder, User
from app.schemas.schemas import SearchResult

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResult)
def search(q: str = Query(min_length=1, max_length=255), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Basic PostgreSQL ILIKE search over filenames and folder names,
    scoped strictly to the current user. No AI/vector/semantic search --
    that is explicitly a future feature, not part of the MVP."""
    pattern = f"%{q}%"

    files = (
        db.query(File)
        .filter(File.user_id == user.id, File.deleted_at.is_(None), File.status == "completed", File.name.ilike(pattern))
        .order_by(File.created_at.desc())
        .limit(100)
        .all()
    )
    folders = (
        db.query(Folder)
        .filter(Folder.user_id == user.id, Folder.deleted_at.is_(None), Folder.name.ilike(pattern))
        .order_by(Folder.name.asc())
        .limit(100)
        .all()
    )
    return SearchResult(files=files, folders=folders)
