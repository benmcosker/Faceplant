from datetime import timedelta

from app import models
from app.auth import hash_token, utcnow
from app.db import SessionLocal
from app.email import send_magic_link_email


def test_send_magic_link_email_logs_link_without_api_key(caplog):
    with caplog.at_level("INFO"):
        send_magic_link_email("someone@example.com", "http://localhost:5174/?token=abc123")
    assert "someone@example.com" in caplog.text
    assert "abc123" in caplog.text


def _capture_links(monkeypatch):
    sent: dict[str, str] = {}
    monkeypatch.setattr("app.routers.auth.send_magic_link_email", lambda email, link: sent.update({email: link}))
    return sent


def _token_from(sent: dict[str, str], email: str) -> str:
    return sent[email].rsplit("token=", 1)[1]


def test_request_link_always_202(client, monkeypatch):
    _capture_links(monkeypatch)
    known = client.post("/api/auth/request-link", json={"email": "known@example.com"})
    unknown = client.post("/api/auth/request-link", json={"email": "brand-new@example.com"})
    assert known.status_code == 202
    assert unknown.status_code == 202


def test_verify_unknown_email_reports_new(client, monkeypatch):
    sent = _capture_links(monkeypatch)
    client.post("/api/auth/request-link", json={"email": "fresh@example.com"})
    token = _token_from(sent, "fresh@example.com")

    result = client.post("/api/auth/verify", json={"token": token})
    assert result.status_code == 200
    assert result.json() == {"status": "new", "user": None, "email": "fresh@example.com"}


def test_verify_bad_token_400(client):
    response = client.post("/api/auth/verify", json={"token": "not-a-real-token"})
    assert response.status_code == 400


def test_verify_expired_token_400(client):
    db = SessionLocal()
    try:
        db.add(
            models.MagicLinkToken(
                email="stale@example.com",
                token_hash=hash_token("expired-token"),
                expires_at=utcnow() - timedelta(minutes=1),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post("/api/auth/verify", json={"token": "expired-token"})
    assert response.status_code == 400


def test_full_signup_flow_sets_session(client, avatar_file, monkeypatch):
    sent = _capture_links(monkeypatch)
    client.post("/api/auth/request-link", json={"email": "newperson@example.com"})
    token = _token_from(sent, "newperson@example.com")

    signed_up = client.post(
        "/api/auth/signup",
        data={"token": token, "username": "  NewPerson  "},
        files={"avatar": avatar_file},
    )
    assert signed_up.status_code == 200
    body = signed_up.json()
    assert body["username"] == "newperson"
    assert body["is_bot"] is False

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


def test_signup_token_is_single_use(client, avatar_file, monkeypatch):
    sent = _capture_links(monkeypatch)
    client.post("/api/auth/request-link", json={"email": "onceonly@example.com"})
    token = _token_from(sent, "onceonly@example.com")

    first = client.post(
        "/api/auth/signup",
        data={"token": token, "username": "onceonly"},
        files={"avatar": avatar_file},
    )
    assert first.status_code == 200

    replay = client.post(
        "/api/auth/signup",
        data={"token": token, "username": "someoneelse"},
        files={"avatar": avatar_file},
    )
    assert replay.status_code == 400


def test_signup_rejects_taken_username(client, avatar_file, login, monkeypatch):
    login("first@example.com", "taken")

    sent = _capture_links(monkeypatch)
    client.post("/api/auth/request-link", json={"email": "second@example.com"})
    token = _token_from(sent, "second@example.com")

    response = client.post(
        "/api/auth/signup",
        data={"token": token, "username": "taken"},
        files={"avatar": avatar_file},
    )
    assert response.status_code == 409


def test_verify_for_returning_user_logs_in_directly(client, login, monkeypatch):
    login("returning@example.com", "returner")
    client.cookies.clear()

    sent = _capture_links(monkeypatch)
    client.post("/api/auth/request-link", json={"email": "returning@example.com"})
    token = _token_from(sent, "returning@example.com")

    verified = client.post("/api/auth/verify", json={"token": token})
    assert verified.status_code == 200
    body = verified.json()
    assert body["status"] == "logged_in"
    assert body["user"]["username"] == "returner"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "returner"


def test_me_requires_session(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_logout_clears_session(client, login):
    login("byebye@example.com", "byebye")
    assert client.get("/api/auth/me").status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    assert client.get("/api/auth/me").status_code == 401
