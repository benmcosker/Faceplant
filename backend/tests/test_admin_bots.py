def test_create_bot_missing_admin_key_rejected(client):
    response = client.post(
        "/api/admin/bots",
        json={
            "username": "testbot",
            "password": "password123",
            "persona": "an obvious bot",
            "avatar_url": "/media/avatars/placeholder.png",
        },
    )
    assert response.status_code == 422


def test_create_bot_wrong_admin_key_rejected(client):
    response = client.post(
        "/api/admin/bots",
        json={
            "username": "testbot",
            "password": "password123",
            "persona": "an obvious bot",
            "avatar_url": "/media/avatars/placeholder.png",
        },
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_create_and_list_bots(client, admin_headers):
    response = client.post(
        "/api/admin/bots",
        json={
            "username": "  TestBot  ",
            "password": "password123",
            "persona": "an obvious bot",
            "model": "claude-haiku-4-5",
            "avatar_url": "/media/avatars/placeholder.png",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "testbot"
    assert body["is_bot"] is True

    listing = client.get("/api/admin/bots", headers=admin_headers)
    assert listing.status_code == 200
    usernames = [b["username"] for b in listing.json()]
    assert "testbot" in usernames

    no_key_listing = client.get("/api/admin/bots")
    assert no_key_listing.status_code == 422


def test_create_bot_duplicate_username_conflicts(client, admin_headers):
    payload = {
        "username": "dupebot",
        "password": "password123",
        "persona": "an obvious bot",
        "avatar_url": "/media/avatars/placeholder.png",
    }
    first = client.post("/api/admin/bots", json=payload, headers=admin_headers)
    assert first.status_code == 200

    second = client.post("/api/admin/bots", json=payload, headers=admin_headers)
    assert second.status_code == 409
