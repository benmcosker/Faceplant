# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Faceplant is a think-piece: a tiny social network where a human claims a username and posts, and a cast of 16 bot personas swarms every human post with in-character reactions. The point is to show how a feed reads once it's mixed with manufactured engagement — and (via "The Meter") what that manufactured engagement costs in real Claude API spend. It's a standalone app: its own backend, frontend, database, and dependencies.

## Architecture

Three processes: **React + MUI frontend (Vite, :5174)** → `/api` proxy → **FastAPI backend (:8001)** → **PostgreSQL**. The backend also calls the **Anthropic API** (in-persona bot replies + emotion-targeted ad taglines) and the **Giphy API** (reaction GIFs for GIF-first bots).

Key cross-cutting flows that require reading several files to understand:

- **Identity is intentionally insecure.** No auth, no session cookie. The frontend remembers the claimed username in `localStorage` and sends it in each request body (`frontend/src/api.ts`). Typing an existing username just means "post as that user again." This is the spec, not a bug.

- **The bot swarm is asynchronous.** When a human posts (`routers/posts.py`), `bots/reactions.py::enqueue_reactions_for_post` schedules two waves of `BotReactionJob` rows (a short wave 0–5 min out, a long wave 15 min–3 hrs out). An APScheduler job started in `main.py`'s `lifespan` polls every ~20s and runs `run_due_reaction_jobs`, which calls Anthropic for an in-character reply, then writes a comment + a like from that bot. **Bot-authored posts never trigger more swarming.** Reactions only appear after bots exist *and* a human posts — seeding after a post won't retroactively swarm it.

- **The persona roster is data.** `bots/roster.py` (16 entries: username, persona, voice notes, optional model override, `uses_giphy`) is the source of truth. `python -m app.scripts.seed_bots` creates the bot users idempotently. GIF-first bots (`uses_giphy: True`) ask the model for a caption + search tag, then `giphy.py` fetches a GIF; the comment body is stored as `caption\ngif_url` and the frontend renders the trailing URL inline (`components/gifBody.tsx`).

- **Emotion targeting.** Every human post is run through `ads/targeting.py::classify_mood` into a fixed mood, stored on `users.mood`. `GET /api/sponsored` returns an ad from `ads/inventory.py` keyed to that mood; with an Anthropic key the tagline references the user's words (curated fallback otherwise).

- **"The Meter" (cost metering).** Every Anthropic call is priced and recorded as a `TokenUsage` row (`usage.py`, pricing table there), attributed to the human whose post/feed triggered it. `routers/costs.py` aggregates it in a single pass (totals, by-source, per-human, a $/min rate, and a 15×60s sparkline). The app-bar `components/CostMeter.tsx` polls `/api/costs`.

- **Reply peek.** `_to_post_out` in `routers/posts.py` inlines the first `PEEK_COMMENTS` replies (`top_comments`) so the feed shows the swarm without a click; `components/PostCard.tsx` renders them and expands to the full thread on demand. `components/CommentItem.tsx` is shared by the peek and the full thread.

- **No migration tool.** `Base.metadata.create_all` runs on startup and only creates missing *tables*. Columns added after a table's initial release are backfilled by `db.py::ensure_columns` — **to add a new column, append it to `_ADDED_COLUMNS`** (types must be valid on both SQLite and PostgreSQL) rather than reaching for Alembic.

- **Frontend error tiers.** `api.ts` never fails silently. Blocking load failures render a retryable `ErrorState`; non-blocking action failures (like, comment, load-more) surface a toast via `ToastProvider` and preserve typed input. Non-fatal fetches (`fetchCosts`, `fetchSponsored`) return `null` instead of throwing.

## Commands

Backend (from `backend/`, venv activated):
```bash
python3 -m venv .venv && source .venv/bin/activate   # use python3 — many systems have no bare `python`
pip install -r requirements.txt
python -m app.scripts.seed_bots                      # idempotent; run before expecting reactions
uvicorn app.main:app --reload --port 8001
pytest                                               # full suite (SQLite, no DB/keys needed)
pytest tests/test_posts.py::test_post_count          # a single test
```

Frontend (from `frontend/`):
```bash
npm run dev                                          # Vite dev server :5174, proxies /api -> :8001
npm run test                                         # Vitest (single: npx vitest run src/components/PostCard.test.tsx)
npm run lint                                         # oxlint
npm run build                                        # tsc -b && vite build — this is the typecheck; run it after TS changes
npm run e2e                                          # Cypress (downloads its browser on first run; needs network)
```

Database — two options; the backend picks the URL from `DATABASE_URL`:
```bash
docker compose up -d                                 # Postgres on :5433 (matches the default DATABASE_URL)
# — or native Postgres on :5432, then set in the repo-root .env:
#   DATABASE_URL=postgresql+psycopg://faceplant:faceplant@localhost:5432/faceplant
```

## Config

`config.py` reads the **repo-root `.env`** (`parents[2]` of `config.py`), copied from `.env.example`. Real OS environment variables override `.env` (this is how the pytest `conftest.py` points tests at throwaway SQLite). Bot reactions require `ANTHROPIC_API_KEY`; GIF-first bots additionally need `GIPHY_API_KEY` (without it they fall back to caption-only). `ADMIN_API_KEY` gates the admin-only bot-construction endpoints (`X-Admin-Key` header).

## Gotchas

- **MUI v9:** don't pass `display` as a direct `Typography` prop — it fails `tsc`. Use `sx={{ display: '…' }}`.
- `npm run lint` (oxlint) does not typecheck; only `npm run build` (`tsc -b`) does.
- Cypress can't run in a sandbox without the browser download; unit/component coverage is Vitest.

## Conventions

- **Branch names use the `code/` prefix** (e.g. `code/reply-peek`), never `claude/` — rename any default `claude/…` suggestion.
- **Commits are authored as `Ben McOsker <benmcosker@gmail.com>`.** Do **not** add `Co-Authored-By: Claude` or `Claude-Session:` trailers, and do not reference model identifiers in commit messages, PR titles/bodies, or code comments.
- **Do not open a pull request unless explicitly asked.**
