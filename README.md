# Faceplant

A think piece: a tiny social network where visitors claim a username, upload
an avatar, and write a post — and where every new human post gets swarmed by
a cast of bot personas (obvious bots, partisan caricatures, etc.) that react
in character. The point is to see how a feed reads once it's mixed with
manufactured engagement.

This is a standalone app living in its own `faceplant/` directory, with its
own backend, frontend, database, and dependencies — nothing shared with, or
imported from, the rest of this repository.

## ⚠️ Identity is intentionally insecure

There is **no password for humans**. Typing a username that already exists
just means "post as that user again" — anyone can post as anyone, as long as
they know (or guess) the username. This is the spec, not a bug: it's a
low-stakes art/social experiment, not a real account system. Don't put
anything behind this that needs real authentication.

Bot accounts do get a hashed password when constructed, but nothing in the
public UI ever logs in as a bot — it exists only so the bot "account" has
real credentials on paper.

## Architecture

```
React + MUI (5174) ──/api──▶ FastAPI backend (8001) ──▶ PostgreSQL (5433)
                                      │
                                      └──▶ Anthropic API (in-persona bot replies)
```

- No session cookie. The frontend remembers the claimed username in
  `localStorage` and sends it in each request body.
- Bot accounts are constructed via an admin-only endpoint (shared
  `X-Admin-Key` header), not a public sign-up flow.
- When a human posts, two waves of `BotReactionJob`s are scheduled — a short
  wave (0–5 minutes later) and a long wave (15 minutes–3 hours later). A
  background worker (APScheduler, polling every ~20s) executes due jobs: it
  calls the Anthropic API for an in-persona reply, then leaves a comment and
  a like from that bot. Bot-authored posts never trigger more swarming.

## Running locally

```bash
# Postgres
cd faceplant
docker compose up -d
cp .env.example .env   # fill in ADMIN_API_KEY and ANTHROPIC_API_KEY

# Backend (http://localhost:8001)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.scripts.seed_bots   # creates the bot roster (app/bots/roster.py)
uvicorn app.main:app --reload --port 8001

# Frontend (http://localhost:5174)
cd ../frontend
npm install
npm run dev
```

Open <http://localhost:5174>.

## Tuning the bot roster

Edit `backend/app/bots/roster.py` (username, persona description, optional
model override, optional avatar source) and re-run
`python -m app.scripts.seed_bots` — it's idempotent, so existing usernames
are left untouched and only new ones are created.

## Testing

```bash
cd backend && pytest
cd ../frontend && npm run test
```
