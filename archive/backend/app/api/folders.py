import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.db.session import get_db
from app.models.models import Folder, User
from app.schemas.schemas import FolderCreate, FolderOut, FolderUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/api/folders", tags=["folders"])


def _get_owned_folder_or_404(db: Session, user: User, folder_id: uuid.UUID) -> Folder:
    """Fetches a folder and enforces that it belongs to the current user.
    This is the single choke point for folder authorization -- callers
    never trust a folder_id without going through here first."""
    folder = (
        db.query(Folder)
        .filter(Folder.id == folder_id, Folder.user_id == user.id, Folder.deleted_at.is_(None))
        .first()
    )
    if not folder:
        # 404, not 403: do not confirm the resource exists for another user.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(request: Request, payload: FolderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.parent_id:
        _get_owned_folder_or_404(db, user, payload.parent_id)  # ensures parent belongs to user

    folder = Folder(user_id=user.id, parent_id=payload.parent_id, name=payload.name)
    db.add(folder)
    db.commit()
    db.refresh(folder)

    log_action(db, user.id, "CREATE_FOLDER", "folder", str(folder.id), client_ip(request), request.headers.get("user-agent"))
    return folder


@router.get("", response_model=list[FolderOut])
def list_folders(parent_id: uuid.UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Folder).filter(Folder.user_id == user.id, Folder.deleted_at.is_(None))
    query = query.filter(Folder.parent_id == parent_id) if parent_id else query.filter(Folder.parent_id.is_(None))
    return query.order_by(Folder.name.asc()).all()


@router.get("/{folder_id}", response_model=FolderOut)
def get_folder(folder_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_folder_or_404(db, user, folder_id)


@router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(folder_id: uuid.UUID, payload: FolderUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    folder = _get_owned_folder_or_404(db, user, folder_id)

    if payload.parent_id is not None:
        if payload.parent_id == folder.id:
            raise HTTPException(status_code=400, detail="A folder cannot be its own parent")
        _get_owned_folder_or_404(db, user, payload.parent_id)
        folder.parent_id = payload.parent_id

    if payload.name is not None:
        folder.name = payload.name

    db.commit()
    db.refresh(folder)
    log_action(db, user.id, "RENAME_FOLDER", "folder", str(folder.id), client_ip(request), request.headers.get("user-agent"))
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    folder = _get_owned_folder_or_404(db, user, folder_id)
    folder.deleted_at = datetime.now(timezone.utc)
    db.commit()
    log_action(db, user.id, "DELETE", "folder", str(folder.id), client_ip(request), request.headers.get("user-agent"))
    return None
