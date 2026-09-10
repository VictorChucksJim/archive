import hashlib

from tests.conftest import fake_storage, register_user


def _upload_test_file(client, content=b"hello archive", filename="notes.txt", mime="text/plain", folder_id=None):
    payload = {"filename": filename, "mime_type": mime, "size_bytes": len(content)}
    if folder_id:
        payload["folder_id"] = folder_id

    upload_url_resp = client.post("/api/files/upload-url", json=payload)
    assert upload_url_resp.status_code == 200, upload_url_resp.text
    data = upload_url_resp.json()

    # Simulate the browser's direct PUT to object storage.
    fake_storage.upload(data["storage_key"], content, mime)

    checksum = hashlib.sha256(content).hexdigest()
    complete_resp = client.post("/api/files/complete", json={"file_id": data["file_id"], "checksum": checksum})
    assert complete_resp.status_code == 200, complete_resp.text
    return complete_resp.json()


def test_full_file_lifecycle(client):
    register_user(client, email="files1@example.com")

    file_out = _upload_test_file(client)
    assert file_out["status"] == "completed"
    assert file_out["size_bytes"] == len(b"hello archive")
    assert len(file_out["checksum"]) == 64

    listing = client.get("/api/files")
    assert any(f["id"] == file_out["id"] for f in listing.json())

    download = client.get(f"/api/files/{file_out['id']}/download-url")
    assert download.status_code == 200
    assert "download_url" in download.json()

    rename = client.patch(f"/api/files/{file_out['id']}", json={"name": "renamed.txt"})
    assert rename.status_code == 200
    assert rename.json()["name"] == "renamed.txt"

    delete = client.delete(f"/api/files/{file_out['id']}")
    assert delete.status_code == 204

    listing_after_delete = client.get("/api/files")
    assert all(f["id"] != file_out["id"] for f in listing_after_delete.json())

    trash = client.get("/api/trash")
    assert any(item["id"] == file_out["id"] for item in trash.json())

    restore = client.post(f"/api/trash/{file_out['id']}/restore")
    assert restore.status_code == 200

    listing_after_restore = client.get("/api/files")
    assert any(f["id"] == file_out["id"] for f in listing_after_restore.json())

    delete_again = client.delete(f"/api/files/{file_out['id']}")
    assert delete_again.status_code == 204

    permanent_delete = client.delete(f"/api/trash/{file_out['id']}")
    assert permanent_delete.status_code == 204

    trash_after = client.get("/api/trash")
    assert all(item["id"] != file_out["id"] for item in trash_after.json())


def test_upload_rejects_disallowed_mime_type(client):
    register_user(client, email="files2@example.com")
    resp = client.post(
        "/api/files/upload-url",
        json={"filename": "virus.exe", "mime_type": "application/x-msdownload", "size_bytes": 100},
    )
    assert resp.status_code == 415


def test_upload_rejects_oversized_file(client):
    register_user(client, email="files3@example.com")
    resp = client.post(
        "/api/files/upload-url",
        json={"filename": "huge.mp4", "mime_type": "video/mp4", "size_bytes": 10 * 1024 * 1024 * 1024 * 1024},
    )
    assert resp.status_code == 413


def test_search_finds_uploaded_file(client):
    register_user(client, email="files4@example.com")
    _upload_test_file(client, filename="quarterly-report.txt")

    resp = client.get("/api/search", params={"q": "quarterly"})
    assert resp.status_code == 200
    assert len(resp.json()["files"]) == 1
    assert resp.json()["files"][0]["name"] == "quarterly-report.txt"


def test_storage_usage_reflects_uploads(client):
    register_user(client, email="files5@example.com")
    content = b"x" * 1000
    _upload_test_file(client, content=content)

    usage = client.get("/api/storage/usage")
    assert usage.status_code == 200
    body = usage.json()
    assert body["used_bytes"] == 1000
    assert body["remaining_bytes"] == body["quota_bytes"] - 1000
