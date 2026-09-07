"""
StorageService: the single abstraction through which the rest of the
application talks to object storage.

No other module should import boto3 or reference a storage provider
directly. Switching between AWS S3, Backblaze B2, Cloudflare R2, Wasabi
or MinIO is a matter of changing the STORAGE_* environment variables --
all of them speak the S3 API, which is what this class wraps.

Design notes (see docs/ARCHITECTURE.md for the full rationale):
- Uploads and downloads use presigned URLs so file bytes flow directly
  between the browser and the object store; FastAPI never buffers file
  content in memory or on local disk.
- Storage keys are opaque UUID-based paths, never user-supplied
  filenames, so there is no directory traversal / collision / PII-in-path
  risk.
"""
import uuid
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()


@dataclass
class PresignedUpload:
    url: str
    method: str
    required_headers: dict


class StorageService:
    """Thin wrapper around an S3-compatible client.

    Methods intentionally mirror the spec: upload, delete, exists,
    generate_upload_url, generate_download_url, copy, move.
    """

    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT,
            region_name=settings.STORAGE_REGION,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if settings.STORAGE_USE_PATH_STYLE else "auto"},
            ),
        )
        self._bucket = settings.STORAGE_BUCKET

        # A second client, identical except for its endpoint, used only to
        # sign URLs meant for the browser. See STORAGE_PUBLIC_ENDPOINT in
        # app/core/config.py for why this can differ from the endpoint the
        # backend itself uses to reach the object store.
        public_endpoint = settings.STORAGE_PUBLIC_ENDPOINT or settings.STORAGE_ENDPOINT
        if public_endpoint == settings.STORAGE_ENDPOINT:
            self._signing_client = self._client
        else:
            self._signing_client = boto3.client(
                "s3",
                endpoint_url=public_endpoint,
                region_name=settings.STORAGE_REGION,
                aws_access_key_id=settings.STORAGE_ACCESS_KEY,
                aws_secret_access_key=settings.STORAGE_SECRET_KEY,
                config=BotoConfig(
                    signature_version="s3v4",
                    s3={"addressing_style": "path" if settings.STORAGE_USE_PATH_STYLE else "auto"},
                ),
            )

    @staticmethod
    def generate_storage_key(user_id: uuid.UUID, file_id: uuid.UUID) -> str:
        """Opaque, non-guessable storage key. Never derived from the
        user-supplied filename."""
        hex_id = file_id.hex
        return f"objects/{hex_id[0:2]}/{hex_id[2:4]}/{hex_id}.bin"

    def generate_upload_url(self, storage_key: str, mime_type: str, expires_in: Optional[int] = None) -> PresignedUpload:
        expires_in = expires_in or settings.STORAGE_PRESIGNED_UPLOAD_EXPIRE_SECONDS
        url = self._signing_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self._bucket,
                "Key": storage_key,
                "ContentType": mime_type,
            },
            ExpiresIn=expires_in,
        )
        return PresignedUpload(url=url, method="PUT", required_headers={"Content-Type": mime_type})

    def generate_download_url(self, storage_key: str, download_filename: str, expires_in: Optional[int] = None) -> str:
        expires_in = expires_in or settings.STORAGE_PRESIGNED_DOWNLOAD_EXPIRE_SECONDS
        return self._signing_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self._bucket,
                "Key": storage_key,
                "ResponseContentDisposition": f'attachment; filename="{download_filename}"',
            },
            ExpiresIn=expires_in,
        )

    def exists(self, storage_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=storage_key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise

    def get_object_size(self, storage_key: str) -> Optional[int]:
        try:
            resp = self._client.head_object(Bucket=self._bucket, Key=storage_key)
            return resp.get("ContentLength")
        except ClientError:
            return None

    def upload(self, storage_key: str, data: bytes, mime_type: str) -> None:
        """Direct server-side upload. Used only for small/system writes
        (e.g. tests, seed data) -- normal user uploads go browser-to-storage
        via generate_upload_url."""
        self._client.put_object(Bucket=self._bucket, Key=storage_key, Body=data, ContentType=mime_type)

    def delete(self, storage_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=storage_key)

    def copy(self, source_key: str, dest_key: str) -> None:
        self._client.copy_object(
            Bucket=self._bucket,
            Key=dest_key,
            CopySource={"Bucket": self._bucket, "Key": source_key},
        )

    def move(self, source_key: str, dest_key: str) -> None:
        self.copy(source_key, dest_key)
        self.delete(source_key)


_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
