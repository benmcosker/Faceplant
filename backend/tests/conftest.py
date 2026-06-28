import io
import os
import tempfile

# Point the app at a throwaway SQLite DB before it's imported, so tests never
# touch the dev database. (Env vars take precedence over .env in pydantic-settings.)
_tmp = tempfile.mkdtemp(prefix="faceplant-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

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
