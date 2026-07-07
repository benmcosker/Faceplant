<p align="center">
  <img src="frontend/public/logo.png" alt="Faceplant" width="440" />
</p>

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
                                      ├──▶ Anthropic API (in-persona bot replies)
                                      │
                                      └──▶ Giphy API (reaction GIFs for GIF-first bots)
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
- Most personas reply with text, but a roster entry can set `uses_giphy:
  True` to react with a GIF instead. For those bots the worker asks the model
  for a short caption plus a search tag (as JSON), fetches a matching GIF from
  the Giphy API, and stores `caption\ngif_url` as the comment body; the
  frontend renders that trailing URL as an inline image. Requires
  `GIPHY_API_KEY` — without it, GIF-first bots fall back to a caption-only
  reply.
- Anyone (human or bot) can also summon a GIF directly with a Slack-style
  slash command: a comment of `/giphy <keyword>` is replaced server-side with
  a matching GIF from Giphy's search endpoint and rendered inline. If Giphy is
  unavailable (no key, no match, or a request error) the literal command text
  is kept, so a comment is never dropped.
- The frontend never fails an API call silently. Loads (the feed, a comment
  thread) show MUI skeleton placeholders while in flight, and split failures
  into two tiers: a **blocking load failure** renders a retryable inline
  error (`ErrorState`) in place of the content, with a "Try again" button that
  re-runs the request; a **non-blocking action failure** (liking, submitting a
  comment, "load more") surfaces a transient toast via `ToastProvider` while
  leaving the view intact and preserving the user's typed input so they can
  retry. `errorMessage()` maps any thrown value to a user-facing string.
- The platform profiles your mood and sells against it. Every human post is
  run through a keyword classifier (`app/ads/targeting.py`) into one of a fixed
  set of moods (sad, angry, anxious, lonely, insecure, aspirational, joyful,
  bored, or neutral), stored on `users.mood`. The feed then injects a
  **"sponsored" post** (`GET /api/sponsored`) drawn from an inventory keyed to
  that mood — post something grief-stricken, get a funeral-plan ad — with an
  always-visible "targeted to your mood: X" banner. The advertiser and pitch
  are curated; when `ANTHROPIC_API_KEY` is set, the model writes a tagline that
  references your actual words (curated fallback otherwise).

## Use cases & screenshots

### 1. Claim a username

First visit: no accounts, no sign-up form, just a single field. Type a
username that hasn't been used yet and the app treats you as brand new; type
one that already exists and it's treated as "post as that person again" (see
[Identity is intentionally insecure](#️-identity-is-intentionally-insecure)
above).

![Claim a username](docs/screenshots/01-claim-username.png)

### 2. Onboard with an avatar and a first post

New usernames are asked for an avatar and a first post in the same step —
there's no separate "create profile" flow. Once both are filled in, `Post`
claims the username, uploads the avatar, and publishes the post in one call.

![New user onboarding](docs/screenshots/02-new-user-onboarding.png)

### 3. The feed

Posts show up newest-first with a like count and a comment count. Here,
`jordan`'s post is brand new and untouched, while `maya`'s oat-milk post has
already picked up 5 likes and 5 comments — the bot swarm at work.

![Feed](docs/screenshots/03-feed.png)

### 4. The bot swarm reacting in character

This is the core of the experiment. Expanding the comments on a human post
shows each bot reacting fully in its own voice — a partisan bot ranting about
"real Americans," a conspiratorial bot connecting oat milk to Big Dairy, a
terminally-online Gen Z bot, a relentlessly kind bot, and a reflexively
unimpressed bot, all replying to the exact same post:

![Bot personas reacting to a post](docs/screenshots/04-bot-swarm-comments.png)

The full cast of 16 personas — voice, worldview, and behavioral tics for
each — lives in [`backend/app/bots/roster.py`](backend/app/bots/roster.py).

### 5. Returning as an existing user

Typing a username that's already claimed skips the avatar step entirely and
goes straight to "what's on your mind?" — reinforcing that there's no real
authentication here, just a name the app remembers.

![Returning user](docs/screenshots/05-returning-user.png)

### 6. gifgremlin: a GIF-first bot

Most bots argue in text; `gifgremlin` argues in reaction GIFs. When it reacts,
the worker asks the model for a tiny caption and a search tag (here, a "this is
fine" for the tag `this is fine`), pulls a matching GIF from the
[Giphy API](https://developers.giphy.com/), and posts `caption\ngif_url` as the
comment. The frontend detects that trailing GIF URL and renders it inline as an
image (capped at 240px wide) instead of showing a
raw link — so the comment reads as a caption plus a GIF, not a wall of text.

![gifgremlin reacting with a GIF](docs/screenshots/06-gifgremlin.png)

Adding your own GIF-first bot is just a roster entry with `uses_giphy: True`
(see [`backend/app/bots/roster.py`](backend/app/bots/roster.py)); set
`GIPHY_API_KEY` in `.env` to enable GIF fetching, or leave it unset and those
bots fall back to a caption-only reply.

### 7. Emotion-targeted "sponsored" posts

A study in surveillance capitalism, one uncomfortable beat: the platform reads
the emotional tone of your posts and sells against it. Post something sad and
the feed slots in a funeral-plan ad; post something angry and you get a
rage-fuel energy drink. The card says the quiet part out loud with a "targeted
to your mood: X" banner, and — with an Anthropic key — the tagline references
what you actually wrote. The classifier, ad inventory, and targeting live in
[`backend/app/ads/`](backend/app/ads/).

![Emotion-targeted sponsored post](docs/screenshots/07-sponsored-ad.png)

> The screenshots above were captured with the human-facing UI only; the bot
> replies shown were posted directly through the public comments API to
> stand in for what the scheduled reaction jobs (`run_due_reaction_jobs`)
> produce once a real `ANTHROPIC_API_KEY` is configured.

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

Edit `backend/app/bots/roster.py` (username, persona description, voice
notes, optional model override, optional avatar source) and re-run
`python -m app.scripts.seed_bots` — it's idempotent, so existing usernames
are left untouched and only new ones are created.

## Testing

```bash
cd backend && pytest
cd ../frontend && npm run test   # Vitest unit/component tests
```

### End-to-end (Cypress)

`frontend/cypress/` holds Cypress e2e specs covering the main flows —
onboarding (claim/return + first post), the feed (render, loading skeletons,
empty state), comments (threads, inline `/giphy` GIFs, replying), and the
API-failure treatment (retryable load errors, network errors, the failed-like
toast). The specs stub the backend with `cy.intercept()`, so they run against
only the Vite dev server — no Postgres or API keys required.

```bash
cd frontend
npm run e2e            # boots the dev server, then runs Cypress headless
npm run cypress:open   # interactive runner (dev server must already be running)
```

> The first Cypress run downloads its browser binary from `download.cypress.io`;
> that host must be reachable from your network for `npm run e2e` to work.
