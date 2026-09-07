import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.api.folders import _get_owned_folder_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import File, User
from app.schemas.schemas import (
    DownloadUrlResponse,
    FileOut,
    FileUpdate,
    UploadCompleteRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.audit import log_action
from app.services.quota import has_capacity
from app.services.storage import get_storage_service

settings = get_settings()
router = APIRouter(prefix="/api/files", tags=["files"])


def _get_owned_file_or_404(db: Session, user: User, file_id: uuid.UUID) -> File:
    """Single choke point for file authorization. Every endpoint below
    goes through this rather than trusting a file_id on its own."""
    file = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == user.id, File.deleted_at.is_(None))
        .first()
    )
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file


@router.post("/upload-url", response_model=UploadUrlResponse)
def request_upload_url(payload: UploadUrlRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # 1. authentication already enforced by get_current_user
    # 2. validate basic constraints
    if payload.size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds maximum allowed size")
    if payload.mime_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="File type not allowed")
    if payload.folder_id:
        _get_owned_folder_or_404(db, user, payload.folder_id)

    # 3. validate quota (accounts for other in-flight pending uploads too)
    if not has_capacity(db, user.id, payload.size_bytes):
        raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail="Storage quota exceeded")

    # 4. create a pending file record + opaque storage key, then presign
    file_id = uuid.uuid4()
    storage = get_storage_service()
    storage_key = storage.generate_storage_key(user.id, file_id)

    file = File(
        id=file_id,
        user_id=user.id,
        folder_id=payload.folder_id,
        name=payload.filename,
        original_filename=payload.filename,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        storage_key=storage_key,
        status="pending",
    )
    db.add(file)
    db.commit()

    presigned = storage.generate_upload_url(storage_key, payload.mime_type)

    return UploadUrlResponse(
        file_id=file_id,
        upload_url=presigned.url,
        storage_key=storage_key,
        method=presigned.method,
        expires_in=settings.STORAGE_PRESIGNED_UPLOAD_EXPIRE_SECONDS,
        required_headers=presigned.required_headers,
    )


@router.post("/complete", response_model=FileOut)
def complete_upload(payload: UploadCompleteRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = _get_owned_file_or_404(db, user, payload.file_id)
    if file.status == "completed":
        return file

    storage = get_storage_service()
    if not storage.exists(file.storage_key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload not found in object storage")

    # Re-validate quota at completion time too, in case of concurrent uploads.
    actual_size = storage.get_object_size(file.storage_key) or file.size_bytes
    file.size_bytes = actual_size
    file.checksum = payload.checksum.lower()
    file.status = "completed"
    db.commit()
    db.refresh(file)

    log_action(db, user.id, "UPLOAD", "file", str(file.id), client_ip(request), request.headers.get("user-agent"))
    return file


@router.get("", response_model=list[FileOut])
def list_files(folder_id: uuid.UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(File).filter(File.user_id == user.id, File.deleted_at.is_(None), File.status == "completed")
    query = query.filter(File.folder_id == folder_id) if folder_id else query.filter(File.folder_id.is_(None))
    return query.order_by(File.created_at.desc()).all()


@router.get("/{file_id}", response_model=FileOut)
def get_file(file_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_file_or_404(db, user, file_id)


@router.get("/{file_id}/download-url", response_model=DownloadUrlResponse)
def get_download_url(file_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = _get_owned_file_or_404(db, user, file_id)
    storage = get_storage_service()
    url = storage.generate_download_url(file.storage_key, file.original_filename)

    log_action(db, user.id, "DOWNLOAD", "file", str(file.id), client_ip(request), request.headers.get("user-agent"))
    return DownloadUrlResponse(download_url=url, expires_in=settings.STORAGE_PRESIGNED_DOWNLOAD_EXPIRE_SECONDS)


@router.patch("/{file_id}", response_model=FileOut)
def update_file(file_id: uuid.UUID, payload: FileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = _get_owned_file_or_404(db, user, file_id)

    if payload.folder_id is not None:
        _get_owned_folder_or_404(db, user, payload.folder_id)
        file.folder_id = payload.folder_id

    if payload.name is not None:
        file.name = payload.name

    db.commit()
    db.refresh(file)
    return file


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = _get_owned_file_or_404(db, user, file_id)
    file.deleted_at = datetime.now(timezone.utc)
    db.commit()
    log_action(db, user.id, "DELETE", "file", str(file.id), client_ip(request), request.headers.get("user-agent"))
    return None
