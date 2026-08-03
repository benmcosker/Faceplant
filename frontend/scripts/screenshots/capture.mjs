import { chromium } from 'playwright'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'
import { ad, costs, posts, swarmComments, user } from './fixtures.mjs'
import { reactionGif, usingRealMeme } from './meme.mjs'

// Regenerates every screenshot referenced by the README, against a production
// `vite preview` build, with the backend fully mocked via route interception.
// Run it with `npm run screenshots` (which builds, serves, then invokes this).
//
// Portable browser resolution: by default Playwright finds the Chromium it
// installed via `npx playwright install chromium`. Set PLAYWRIGHT_CHROMIUM_PATH
// to point at a specific binary (used in CI/sandbox environments that
// pre-install the browser).

const HERE = dirname(fileURLToPath(import.meta.url))
const SHOTS = resolve(HERE, '../../../docs/screenshots')
const BASE = process.env.SCREENSHOT_BASE_URL ?? 'http://localhost:4173'
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined

const gif = reactionGif()

async function waitForServer() {
  for (let i = 0; i < 60; i++) {
    try {
      if ((await fetch(BASE)).ok) return
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`preview server never came up at ${BASE}`)
}

function apiRoutes(ctx, { authed }) {
  return ctx.route('**/*', async (route) => {
    const url = route.request().url()
    const json = (b) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) })
    // The reaction GIF: network is blocked during capture, so serve the meme
    // asset (or placeholder) for any .gif / giphy request.
    if (url.endsWith('.gif') || url.includes('giphy.com')) {
      return route.fulfill({ status: 200, contentType: gif.contentType, body: gif.body })
    }
    if (!url.includes('/api/')) return route.continue()
    if (url.includes('/api/auth/me')) {
      return authed ? json(user) : route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"no"}' })
    }
    if (url.includes('/api/auth/verify')) return json({ status: 'new', email: 'newperson@example.com' })
    if (url.match(/\/api\/posts(\?|$)/)) return json(posts)
    if (url.includes('/api/costs')) return json(costs)
    if (url.includes('/api/sponsored')) return json(ad)
    if (url.match(/\/api\/posts\/\d+\/comments/)) return json(swarmComments)
    if (url.includes('/thread-stats')) {
      const id = Number((url.match(/\/api\/posts\/(\d+)\//) || [])[1] || 1)
      const p = posts.find((x) => x.id === id) || posts[0]
      return json({ human_share: p.human_share, human_messages: p.human_messages, bot_messages: p.bot_messages, total_messages: p.total_messages, like_count: p.like_count })
    }
    if (url.includes('/likes')) return json([])
    return json({ ok: true })
  })
}

async function shoot(browser, { file, authed = true, path: gotoPath = '/', width = 900, height = 1200, fullPage = false, colorMode, wait, prep, clip }) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2 })
  await apiRoutes(ctx, { authed })
  const page = await ctx.newPage()
  if (colorMode) await page.addInitScript((m) => localStorage.setItem('faceplant-color-mode', m), colorMode)
  await page.goto(`${BASE}${gotoPath}`, { waitUntil: 'networkidle' })
  if (wait) await page.waitForSelector(wait, { timeout: 9000 })
  if (prep) await prep(page)
  await page.waitForTimeout(600)
  if (clip) {
    await (await clip(page)).screenshot({ path: join(SHOTS, file) })
  } else {
    await page.screenshot({ path: join(SHOTS, file), fullPage })
  }
  await ctx.close()
  console.log('  wrote', file)
}

// The full shot list. Each entry maps 1:1 to an image referenced by README.md.
const SHOT_LIST = [
  // 01 — magic-link email step (logged out)
  { file: '01-claim-username.png', authed: false, width: 860, height: 720, wait: 'text=Engagement is free' },
  // 02 — new-user signup (username + avatar + first post)
  { file: '02-new-user-onboarding.png', authed: false, path: '/?token=demo', width: 860, height: 900, wait: 'text=checks out' },
  // 03 — the feed
  { file: '03-feed.png', width: 900, height: 1300, fullPage: true, wait: 'text=oat milk' },
  // 04 — the bot swarm (expanded thread). The maya post's comment count (5) is
  // unique among the action buttons, so target it by accessible name — MUI
  // strips icon data-testids in production builds.
  {
    file: '04-bot-swarm-comments.png', width: 900, height: 1400, fullPage: true, wait: 'text=oat milk',
    prep: async (page) => {
      await page.getByRole('button', { name: '5', exact: true }).first().click()
      await page.waitForSelector('text=BREAKING', { timeout: 9000 })
    },
  },
  // 05 — returning user's feed
  { file: '05-returning-user.png', width: 900, height: 1300, fullPage: true, wait: 'text=oat milk' },
  // 06 — gifgremlin (GIF-first bot)
  { file: '06-gifgremlin.png', width: 900, height: 1300, fullPage: true, wait: 'img[alt="reaction gif"]' },
  // 07 — emotion-targeted sponsored post (tight crop of just the ad card)
  {
    file: '07-sponsored-ad.png', width: 720, height: 1200, wait: 'text=targeted to your mood',
    clip: (page) => page.locator('.MuiCard-root', { hasText: 'targeted to your mood' }).first(),
  },
  // 08 — The Meter (popover open)
  {
    file: '08-cost-meter.png', width: 900, height: 1250, wait: 'text=oat milk',
    prep: async (page) => {
      await page.getByRole('button', { name: 'AI cost meter' }).click()
      await page.waitForSelector('text=Spent on nobody', { timeout: 9000 })
    },
  },
  // 09 — the "% human" counter
  { file: '09-human-counter.png', width: 900, height: 1300, fullPage: true, wait: 'text=dead internet' },
  // 12 — light / dark theme comparison (matched viewport, top of feed)
  { file: '12-theme-light.png', width: 900, height: 1100, colorMode: 'light', wait: 'text=oat milk' },
  { file: '12-theme-dark.png', width: 900, height: 1100, colorMode: 'dark', wait: 'text=oat milk' },
]

async function main() {
  await waitForServer()
  console.log(`Capturing ${SHOT_LIST.length} screenshots → ${SHOTS}`)
  console.log(usingRealMeme() ? '  reaction gif: real meme asset' : '  reaction gif: placeholder (drop assets/this_is_fine.png for the real one)')
  const browser = await chromium.launch({ executablePath })
  let failed = 0
  for (const opts of SHOT_LIST) {
    try {
      await shoot(browser, opts)
    } catch (e) {
      failed++
      console.error('  FAILED', opts.file, '-', e.message.split('\n')[0])
    }
  }
  await browser.close()
  console.log('done')
  if (failed) process.exitCode = 1
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
