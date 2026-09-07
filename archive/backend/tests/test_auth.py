from app.core.security import hash_password, verify_password
from tests.conftest import register_user


def test_password_hashing_roundtrip():
    hashed = hash_password("a-strong-password-123")
    assert hashed != "a-strong-password-123"
    assert verify_password("a-strong-password-123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_register_creates_session_cookie(client):
    resp = register_user(client, email="alice@example.com")
    assert "archive_session" in resp.cookies
    assert resp.json()["email"] == "alice@example.com"
    assert "password" not in resp.json()


def test_register_duplicate_email_rejected(client):
    register_user(client, email="dupe@example.com")
    resp = client.post(
        "/api/auth/register",
        json={"email": "dupe@example.com", "password": "another-strong-pass", "display_name": "Someone"},
    )
    assert resp.status_code == 409


def test_login_success_and_failure(client):
    register_user(client, email="bob@example.com", password="correct-horse-battery-staple")
    client.cookies.clear()

    good = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "correct-horse-battery-staple"})
    assert good.status_code == 200

    client.cookies.clear()
    bad = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong-password"})
    assert bad.status_code == 401


def test_me_requires_authentication(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client):
    register_user(client, email="carol@example.com")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "carol@example.com"


def test_logout_clears_session(client):
    register_user(client, email="dave@example.com")
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
