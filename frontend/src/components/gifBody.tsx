import type { ReactNode } from 'react'
import { Box } from '@mui/material'

// GIF-first bot personas (e.g. gifgremlin) post a body shaped like
// `caption\ngif_url`, so a GIF shows up as its own line that is just a URL.
// Detect those lines and render them as an inline <img> instead of raw text.
// Matches direct .gif links (Giphy's original URLs end in .gif) as well as
// Giphy media/CDN hosts, whether or not the path ends in .gif.
const GIF_URL_RE = /^https?:\/\/\S+\.gif(\?\S*)?$/i
const GIPHY_HOST_RE = /^https?:\/\/(?:[\w.-]*\.)?giphy\.com\/\S+$/i

export function isGifUrl(text: string): boolean {
  const trimmed = text.trim()
  return GIF_URL_RE.test(trimmed) || GIPHY_HOST_RE.test(trimmed)
}

/**
 * Renders a comment/post body, turning any standalone GIF-URL line into an
 * inline image while preserving the newlines of the surrounding text.
 */
export function renderBodyWithGifs(body: string): ReactNode {
  const nodes: ReactNode[] = []
  let textBuffer: string[] = []

  const flushText = () => {
    if (textBuffer.length === 0) return
    const text = textBuffer.join('\n')
    if (text.trim()) {
      nodes.push(
        <Box key={`t${nodes.length}`} component="span" sx={{ whiteSpace: 'pre-wrap' }}>
          {text}
        </Box>,
      )
    }
    textBuffer = []
  }

  for (const line of body.split('\n')) {
    if (isGifUrl(line)) {
      flushText()
      nodes.push(
        <Box
          key={`g${nodes.length}`}
          component="img"
          src={line.trim()}
          alt="reaction gif"
          loading="lazy"
          sx={{ display: 'block', maxWidth: 240, width: '100%', height: 'auto', borderRadius: 1, mt: 0.5 }}
        />,
      )
    } else {
      textBuffer.push(line)
    }
  }
  flushText()
  return nodes
}
