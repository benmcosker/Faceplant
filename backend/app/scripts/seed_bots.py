"""Idempotently creates the bot accounts listed in app/bots/roster.py.

Safe to re-run after editing the roster: existing usernames are left
untouched, only new ones are created. Each bot gets a random password since
nothing in the public UI logs in as a bot.

Usage: python -m app.scripts.seed_bots
"""

import secrets

import httpx

from ..avatars import generate_placeholder_avatar_bytes, save_avatar_bytes
from ..bots.roster import ROSTER
from ..db import SessionLocal
from ..models import User
from ..routers.admin_bots import create_bot_account
from ..schemas import AdminBotCreate


def _resolve_avatar_url(username: str, avatar_source: str | None) -> str:
    if avatar_source is None:
        return save_avatar_bytes(generate_placeholder_avatar_bytes(username), "image/png")
    if avatar_source.startswith("http://") or avatar_source.startswith("https://"):
        response = httpx.get(avatar_source, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "image/png").split(";")[0]
        return save_avatar_bytes(response.content, content_type)
    with open(avatar_source, "rb") as f:
        data = f.read()
    content_type = "image/png" if avatar_source.lower().endswith("png") else "image/jpeg"
    return save_avatar_bytes(data, content_type)


def seed_bots() -> None:
    db = SessionLocal()
    try:
        existing_usernames = {u.username for u in db.query(User.username).filter(User.is_bot.is_(True))}
        created = 0
        for entry in ROSTER:
            if entry["username"] in existing_usernames:
                continue
            avatar_url = _resolve_avatar_url(entry["username"], entry.get("avatar_source"))
            create_bot_account(
                db,
                AdminBotCreate(
                    username=entry["username"],
                    password=secrets.token_urlsafe(16),
                    persona=entry["persona"],
                    model=entry.get("model"),
                    avatar_url=avatar_url,
                ),
            )
            created += 1
            print(f"created bot: {entry['username']}")
        print(f"done. {created} bot(s) created, {len(ROSTER) - created} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_bots()
