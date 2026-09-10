import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---------- Auth ----------

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    display_name: str = Field(min_length=1, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    created_at: datetime
    last_login_at: Optional[datetime] = None


# ---------- Folders ----------

class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: Optional[uuid.UUID] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    parent_id: Optional[uuid.UUID] = None


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    name: str
    created_at: datetime
    updated_at: datetime


# ---------- Files ----------

class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    mime_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    folder_id: Optional[uuid.UUID] = None


class UploadUrlResponse(BaseModel):
    file_id: uuid.UUID
    upload_url: str
    storage_key: str
    method: str = "PUT"
    expires_in: int
    required_headers: dict = {}


class UploadCompleteRequest(BaseModel):
    file_id: uuid.UUID
    checksum: str = Field(min_length=64, max_length=64)  # sha256 hex


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folder_id: Optional[uuid.UUID]
    name: str
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class FileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    folder_id: Optional[uuid.UUID] = None


class DownloadUrlResponse(BaseModel):
    download_url: str
    expires_in: int


# ---------- Trash ----------

class TrashItemOut(BaseModel):
    id: uuid.UUID
    type: str  # "file" | "folder"
    name: str
    deleted_at: datetime


# ---------- Storage ----------

class StorageUsageOut(BaseModel):
    used_bytes: int
    quota_bytes: int
    remaining_bytes: int


# ---------- Search ----------

class SearchResult(BaseModel):
    files: List[FileOut]
    folders: List[FolderOut]
