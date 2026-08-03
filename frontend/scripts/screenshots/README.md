# Screenshot utility

Regenerates every image referenced by the top-level `README.md`, so the docs
can be refreshed in one command whenever the UI changes instead of being
reconstructed by hand.

It runs the **production build** under `vite preview` with the backend fully
mocked (Playwright route interception), so it needs no API key, no database,
and no network — the feed, bot swarm, sponsored ad, cost meter, and light/dark
themes are all driven from local fixtures.

## Run it

```bash
cd frontend
npx playwright install chromium   # one-time, downloads the browser
npm run screenshots
```

`npm run screenshots` builds the app, serves it, runs the capture, and writes
the PNGs into `../docs/screenshots/`. Review the diff and commit the images.

## The reaction GIF (04 / 06 / 08)

The gifgremlin shots render a real "this is fine" reaction GIF. That image is
copyrighted, so it is **not committed** — `assets/` is gitignored. Without it,
the capture serves a self-contained SVG placeholder and the shots still render
coherently. To reproduce the exact committed images, drop the real meme at:

```
scripts/screenshots/assets/this_is_fine.png
```

## Files

- `fixtures.mjs` — the demo data (personas, posts, swarm comments, costs, ad).
  Edit here to change what the docs feed shows.
- `meme.mjs` — resolves the reaction-GIF image (real asset or placeholder).
- `capture.mjs` — the runner: the mock API routes and the shot list, one entry
  per README image.

## Environment overrides

- `PLAYWRIGHT_CHROMIUM_PATH` — launch a specific Chromium binary instead of the
  one Playwright installed (used in CI / sandboxes that pre-install the browser).
- `SCREENSHOT_BASE_URL` — capture against a different origin (default
  `http://localhost:4173`).
