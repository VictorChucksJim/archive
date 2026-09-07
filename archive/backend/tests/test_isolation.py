"""
Security tests proving strict per-user data isolation.

These are the tests referenced by the spec's "Definition of Done":
User A must never be able to read, modify, or delete User B's files,
folders, or download URLs -- regardless of what IDs are supplied.
"""
import hashlib

from tests.conftest import fake_storage, register_user


def _new_authenticated_client(client, email):
    """Each TestClient instance keeps its own cookie jar, so logging in
    as a second user requires a fresh client bound to the same app."""
    from fastapi.testclient import TestClient
    from app.main import app

    other = TestClient(app)
    other.cookies.clear()
    resp = other.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple", "display_name": "User"},
    )
    assert resp.status_code == 201
    return other


def test_user_cannot_access_another_users_folder(client, db_session):
    register_user(client, email="owner1@example.com")
    folder = client.post("/api/folders", json={"name": "Secret Plans"}).json()

    attacker = _new_authenticated_client(client, "attacker1@example.com")
    # override dependency for the second client too, since it shares the app
    resp = attacker.get(f"/api/folders/{folder['id']}")
    assert resp.status_code == 404

    rename_attempt = attacker.patch(f"/api/folders/{folder['id']}", json={"name": "Hacked"})
    assert rename_attempt.status_code == 404

    delete_attempt = attacker.delete(f"/api/folders/{folder['id']}")
    assert delete_attempt.status_code == 404


def test_user_cannot_access_another_users_file(client, db_session):
    register_user(client, email="owner2@example.com")
    content = b"private financial data"
    upload = client.post(
        "/api/files/upload-url",
        json={"filename": "salary.pdf", "mime_type": "application/pdf", "size_bytes": len(content)},
    ).json()
    fake_storage.upload(upload["storage_key"], content, "application/pdf")
    file_out = client.post(
        "/api/files/complete",
        json={"file_id": upload["file_id"], "checksum": hashlib.sha256(content).hexdigest()},
    ).json()

    attacker = _new_authenticated_client(client, "attacker2@example.com")

    get_attempt = attacker.get(f"/api/files/{file_out['id']}")
    assert get_attempt.status_code == 404

    rename_attempt = attacker.patch(f"/api/files/{file_out['id']}", json={"name": "stolen.pdf"})
    assert rename_attempt.status_code == 404

    delete_attempt = attacker.delete(f"/api/files/{file_out['id']}")
    assert delete_attempt.status_code == 404


def test_user_cannot_obtain_another_users_download_url(client, db_session):
    register_user(client, email="owner3@example.com")
    content = b"confidential"
    upload = client.post(
        "/api/files/upload-url",
        json={"filename": "contract.pdf", "mime_type": "application/pdf", "size_bytes": len(content)},
    ).json()
    fake_storage.upload(upload["storage_key"], content, "application/pdf")
    file_out = client.post(
        "/api/files/complete",
        json={"file_id": upload["file_id"], "checksum": hashlib.sha256(content).hexdigest()},
    ).json()

    attacker = _new_authenticated_client(client, "attacker3@example.com")
    resp = attacker.get(f"/api/files/{file_out['id']}/download-url")
    assert resp.status_code == 404


def test_user_cannot_place_file_in_another_users_folder(client, db_session):
    register_user(client, email="owner4@example.com")
    folder = client.post("/api/folders", json={"name": "Owner Folder"}).json()

    attacker = _new_authenticated_client(client, "attacker4@example.com")
    resp = attacker.post(
        "/api/files/upload-url",
        json={"filename": "sneaky.txt", "mime_type": "text/plain", "size_bytes": 10, "folder_id": folder["id"]},
    )
    assert resp.status_code == 404


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/folders").status_code == 401
    assert client.get("/api/files").status_code == 401
    assert client.get("/api/trash").status_code == 401
    assert client.get("/api/search", params={"q": "x"}).status_code == 401
    assert client.get("/api/storage/usage").status_code == 401
    assert client.post("/api/folders", json={"name": "x"}).status_code == 401


def test_invalid_session_cookie_is_rejected(client):
    client.cookies.set("archive_session", "not-a-real-token")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_quota_cannot_be_bypassed_by_forged_user_id(client, db_session):
    """The upload-url endpoint must derive the owning user strictly from
    the session, never from any client-supplied field -- there is no
    user_id field in the request schema at all, so this test asserts the
    file ends up owned by the authenticated user regardless of any extra
    fields an attacker might smuggle into the JSON body."""
    register_user(client, email="owner5@example.com")

    resp = client.post(
        "/api/files/upload-url",
        json={
            "filename": "test.txt",
            "mime_type": "text/plain",
            "size_bytes": 10,
            "user_id": "11111111-1111-1111-1111-111111111111",  # ignored: not part of the schema
        },
    )
    assert resp.status_code == 200
    me = client.get("/api/auth/me").json()

    from app.models.models import File
    file_row = db_session.query(File).filter(File.id == resp.json()["file_id"]).first()
    assert str(file_row.user_id) == me["id"]
