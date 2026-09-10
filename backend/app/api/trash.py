import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.db.session import get_db
from app.models.models import File, Folder, User
from app.schemas.schemas import TrashItemOut
from app.services.audit import log_action
from app.services.storage import get_storage_service

router = APIRouter(prefix="/api/trash", tags=["trash"])


@router.get("", response_model=list[TrashItemOut])
def list_trash(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    files = db.query(File).filter(File.user_id == user.id, File.deleted_at.isnot(None)).all()
    folders = db.query(Folder).filter(Folder.user_id == user.id, Folder.deleted_at.isnot(None)).all()

    items = [TrashItemOut(id=f.id, type="file", name=f.name, deleted_at=f.deleted_at) for f in files]
    items += [TrashItemOut(id=f.id, type="folder", name=f.name, deleted_at=f.deleted_at) for f in folders]
    return sorted(items, key=lambda i: i.deleted_at, reverse=True)


def _find_trashed_owned(db: Session, user: User, item_id: uuid.UUID):
    file = db.query(File).filter(File.id == item_id, File.user_id == user.id, File.deleted_at.isnot(None)).first()
    if file:
        return "file", file
    folder = db.query(Folder).filter(Folder.id == item_id, Folder.user_id == user.id, Folder.deleted_at.isnot(None)).first()
    if folder:
        return "folder", folder
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trash item not found")


@router.post("/{item_id}/restore", status_code=status.HTTP_200_OK)
def restore_item(item_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    kind, item = _find_trashed_owned(db, user, item_id)
    item.deleted_at = None
    db.commit()
    log_action(db, user.id, "RESTORE", kind, str(item_id), client_ip(request), request.headers.get("user-agent"))
    return {"id": str(item_id), "type": kind, "restored": True}


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete(item_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    kind, item = _find_trashed_owned(db, user, item_id)

    if kind == "file":
        storage = get_storage_service()
        try:
            storage.delete(item.storage_key)
        except Exception:
            # Object may already be gone; do not block metadata cleanup.
            pass

    db.delete(item)
    db.commit()
    log_action(db, user.id, "PERMANENT_DELETE", kind, str(item_id), client_ip(request), request.headers.get("user-agent"))
    return None
