def test_get_unknown_username_404(client):
    response = client.get("/api/users/nobody")
    assert response.status_code == 404


def test_claim_new_username_requires_avatar(client):
    response = client.post("/api/users", data={"username": "newperson"})
    assert response.status_code == 400


def test_claim_new_username_rejects_bad_content_type(client):
    response = client.post(
        "/api/users",
        data={"username": "newperson"},
        files={"avatar": ("avatar.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


def test_claim_new_username_rejects_oversized_file(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_avatar_mb", 0.0001)
    big_payload = b"\x89PNG\r\n" + b"0" * 1024
    response = client.post(
        "/api/users",
        data={"username": "newperson"},
        files={"avatar": ("avatar.png", big_payload, "image/png")},
    )
    assert response.status_code == 400


def test_claim_new_username_creates_user(client, avatar_file):
    response = client.post(
        "/api/users",
        data={"username": "  NewPerson  "},
        files={"avatar": avatar_file},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "newperson"
    assert body["is_bot"] is False
    assert body["avatar_url"].startswith("/media/avatars/")

    fetched = client.get("/api/users/newperson")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_claiming_existing_username_returns_same_user_no_avatar_needed(client, avatar_file):
    first = client.post(
        "/api/users", data={"username": "repeatuser"}, files={"avatar": avatar_file}
    )
    assert first.status_code == 200
    first_id = first.json()["id"]

    second = client.post("/api/users", data={"username": "repeatuser"})
    assert second.status_code == 200
    assert second.json()["id"] == first_id
