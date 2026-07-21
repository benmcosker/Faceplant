import io
import os
import tempfile

# Point the app at a throwaway SQLite DB before it's imported, so tests never
# touch the dev database. (Env vars take precedence over .env in pydantic-settings.)
_tmp = tempfile.mkdtemp(prefix="faceplant-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["SESSION_SECRET_KEY"] = "test-session-secret"

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture(autouse=True)
def _reset_db():
    from app.db import Base, engine

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def make_avatar_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def avatar_file():
    return ("avatar.png", make_avatar_bytes(), "image/png")


@pytest.fixture
def admin_headers():
    return {"X-Admin-Key": "test-admin-key"}


@pytest.fixture
def login(client, avatar_file, monkeypatch):
    """Drives the real magic-link flow (request-link -> verify -> signup),
    capturing the emailed link the way `send_magic_link_email` would deliver
    it, instead of a test-only backdoor. Returns a callable
    `login(email, username=None) -> UserOut dict` that leaves `client`
    holding a session cookie for that user — logging in as someone else later
    in the same test swaps which session is active, same as a real browser.
    """
    sent_links: dict[str, str] = {}

    def _capture(to_email: str, link: str) -> None:
        sent_links[to_email] = link

    monkeypatch.setattr("app.routers.auth.send_magic_link_email", _capture)

    def _login(email: str, username: str | None = None) -> dict:
        username = username or email.split("@")[0]
        response = client.post("/api/auth/request-link", json={"email": email})
        assert response.status_code == 202, response.text
        token = sent_links[email].rsplit("token=", 1)[1]

        verified = client.post("/api/auth/verify", json={"token": token})
        assert verified.status_code == 200, verified.text
        body = verified.json()
        if body["status"] == "logged_in":
            return body["user"]

        signed_up = client.post(
            "/api/auth/signup",
            data={"token": token, "username": username},
            files={"avatar": avatar_file},
        )
        assert signed_up.status_code == 200, signed_up.text
        return signed_up.json()

    return _login
