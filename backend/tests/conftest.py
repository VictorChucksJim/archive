"""
Shared test fixtures.

Tests run against a real PostgreSQL instance (see docker-compose.yml /
CI config) because the schema uses PostgreSQL-specific UUID columns.
Set TEST_DATABASE_URL to point at a disposable database; it defaults to
a local Postgres on the standard docker-compose port with a distinct
"archive_test" database name so tests never touch development data.

Object storage calls are faked via a lightweight in-memory double so
the test suite does not require a running MinIO/S3 endpoint, and so
uploaded bytes never need to leave the test process.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg2://archive:archive@localhost:5432/archive_test"),
)
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.db.session import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.api.deps import get_db  # noqa: E402
from app.services import storage as storage_module  # noqa: E402


TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class FakeStorageService:
    """In-memory double for StorageService used across the whole test
    suite so tests do not depend on a running object-storage endpoint."""

    def __init__(self):
        self._objects: dict[str, bytes] = {}

    @staticmethod
    def generate_storage_key(user_id, file_id) -> str:
        hex_id = file_id.hex
        return f"objects/{hex_id[0:2]}/{hex_id[2:4]}/{hex_id}.bin"

    def generate_upload_url(self, storage_key, mime_type, expires_in=None):
        from app.services.storage import PresignedUpload
        # The "URL" here is a marker consumed by the test's fake HTTP PUT.
        return PresignedUpload(url=f"fake://upload/{storage_key}", method="PUT", required_headers={"Content-Type": mime_type})

    def generate_download_url(self, storage_key, download_filename, expires_in=None):
        return f"fake://download/{storage_key}?name={download_filename}"

    def exists(self, storage_key: str) -> bool:
        return storage_key in self._objects

    def get_object_size(self, storage_key: str):
        obj = self._objects.get(storage_key)
        return len(obj) if obj is not None else None

    def upload(self, storage_key: str, data: bytes, mime_type: str) -> None:
        self._objects[storage_key] = data

    def delete(self, storage_key: str) -> None:
        self._objects.pop(storage_key, None)

    def copy(self, source_key: str, dest_key: str) -> None:
        self._objects[dest_key] = self._objects[source_key]

    def move(self, source_key: str, dest_key: str) -> None:
        self.copy(source_key, dest_key)
        self.delete(source_key)


fake_storage = FakeStorageService()


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _patch_storage(monkeypatch):
    monkeypatch.setattr(storage_module, "get_storage_service", lambda: fake_storage)
    # Also patch the already-imported references in the api modules.
    from app.api import files as files_api
    from app.api import trash as trash_api
    monkeypatch.setattr(files_api, "get_storage_service", lambda: fake_storage)
    monkeypatch.setattr(trash_api, "get_storage_service", lambda: fake_storage)
    yield


@pytest.fixture()
def db_session():
    """A plain session against the test database. Because request
    handlers call db.commit() themselves (as they do in production),
    we clean up by truncating tables after each test rather than
    relying on a rolled-back outer transaction."""
    session = TestingSessionLocal()
    yield session
    session.close()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register_user(client, email=None, password="correct-horse-battery-staple", name="Test User"):
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": password, "display_name": name})
    assert resp.status_code == 201, resp.text
    return resp
