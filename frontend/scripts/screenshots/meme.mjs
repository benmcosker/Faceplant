import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))

// The gifgremlin shots (04/06/08) render a real reaction GIF. That image is a
// copyrighted meme, so it is intentionally NOT committed. Drop a PNG at
// assets/this_is_fine.png (gitignored) to use the real thing; otherwise a
// self-contained SVG placeholder is served so the shots still render coherently.
const ASSET = join(HERE, 'assets', 'this_is_fine.png')

const PLACEHOLDER_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="150" viewBox="0 0 240 150">
  <defs><radialGradient id="g" cx="30%" cy="80%" r="90%">
    <stop offset="0%" stop-color="#ff8a3d"/><stop offset="55%" stop-color="#c0341f"/><stop offset="100%" stop-color="#2b0f0a"/>
  </radialGradient></defs>
  <rect width="240" height="150" rx="8" fill="#2b2018"/>
  <rect width="240" height="150" rx="8" fill="url(#g)" opacity="0.9"/>
  <text x="120" y="70" font-family="Helvetica,Arial" font-size="22" font-weight="800" fill="#fff5e8" text-anchor="middle">this is fine</text>
  <text x="120" y="104" font-family="Helvetica,Arial" font-size="30" text-anchor="middle">🔥🐶🔥</text>
</svg>`

/**
 * Resolve the reaction-GIF image to serve for intercepted gif/giphy requests.
 * Returns a { body, contentType } ready to hand to Playwright's route.fulfill.
 */
export function reactionGif() {
  if (existsSync(ASSET)) {
    return { body: readFileSync(ASSET), contentType: 'image/png' }
  }
  return { body: PLACEHOLDER_SVG, contentType: 'image/svg+xml' }
}

export const usingRealMeme = () => existsSync(ASSET)
