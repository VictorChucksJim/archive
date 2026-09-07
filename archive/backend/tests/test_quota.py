from app.models.models import User
from tests.conftest import register_user


def test_upload_within_quota_succeeds(client):
    register_user(client, email="quota1@example.com")
    resp = client.post(
        "/api/files/upload-url",
        json={"filename": "small.txt", "mime_type": "text/plain", "size_bytes": 1024},
    )
    assert resp.status_code == 200


def test_upload_exceeding_quota_rejected(client, db_session):
    register_user(client, email="quota2@example.com")

    me = client.get("/api/auth/me").json()
    user = db_session.query(User).filter(User.id == me["id"]).first()
    user.quota_bytes = 500  # shrink quota for this test
    db_session.commit()

    resp = client.post(
        "/api/files/upload-url",
        json={"filename": "too-big.txt", "mime_type": "text/plain", "size_bytes": 1000},
    )
    assert resp.status_code == 507


def test_default_quota_is_one_terabyte(client, db_session):
    register_user(client, email="quota3@example.com")
    me = client.get("/api/auth/me").json()
    user = db_session.query(User).filter(User.id == me["id"]).first()
    assert user.quota_bytes == 1_099_511_627_776
