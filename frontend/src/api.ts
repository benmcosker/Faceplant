// Typed client for the backend. No session cookie — identity is just a
// username the visitor types, remembered in localStorage and sent in each
// request body. The Vite dev proxy forwards /api -> :8001.

const IDENTITY_KEY = 'faceplant:username'

export function getIdentity(): string | null {
  return localStorage.getItem(IDENTITY_KEY)
}

export function setIdentity(username: string): void {
  localStorage.setItem(IDENTITY_KEY, username)
}

export function clearIdentity(): void {
  localStorage.removeItem(IDENTITY_KEY)
}

export interface User {
  id: number
  username: string
  avatar_url: string
  is_bot: boolean
}

export interface Comment {
  id: number
  body: string
  created_at: string
  author: User
}

export interface Post {
  id: number
  body: string
  created_at: string
  author: User
  like_count: number
  comment_count: number
  /** The first few replies, for an inline "peek" of the swarm in the feed. */
  top_comments: Comment[]
  /** How human this thread is, by message count — the "% human" counter. */
  human_share: number
  human_messages: number
  bot_messages: number
  total_messages: number
}

export interface ThreadStats {
  human_share: number
  human_messages: number
  bot_messages: number
  total_messages: number
}

export interface Ad {
  advertiser: string
  tagline: string
  body: string
  cta: string
  /** The mood the platform profiled the viewer into, shown on the targeting banner. */
  mood: string
  /** Where the CTA links out (a real brand / affiliate URL). */
  url: string
}

export interface SourceCost {
  cost_usd: number
  calls: number
}

export interface UserCost {
  username: string
  cost_usd: number
  calls: number
}

export interface SpendEvent {
  source: string
  actor: string | null
  human_username: string | null
  cost_usd: number
  created_at: string
}

export interface CostSummary {
  total_cost_usd: number
  total_calls: number
  input_tokens: number
  output_tokens: number
  by_source: Record<string, SourceCost>
  per_human_user: UserCost[]
  human_user_count: number
  cost_per_human_user_avg: number
  cost_per_post_usd: number
  rate_per_min_usd: number
  recent: SpendEvent[]
  spend_per_min: number[]
  /** Spend with no human at either end (bot posts + bots reacting to bots). */
  no_human_cost_usd: number
  no_human_calls: number
}

export class ApiError extends Error {
  status: number
  code: string

  constructor(message: string, status: number, code: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/** Maps any thrown value to a user-facing message for error UI. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  return 'Something went wrong. Please try again.'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError("Can't reach the server.", 0, 'network_error')
  }
  if (!res.ok) {
    let message = `Request failed (${res.status}).`
    let code = 'http_error'
    try {
      const body = await res.json()
      if (body?.error) message = body.error
      if (body?.code) code = body.code
    } catch {
      /* non-JSON body */
    }
    throw new ApiError(message, res.status, code)
  }
  return (await res.json()) as T
}

/** Looks up a username. Returns null on 404 (username not yet claimed). */
export async function fetchUser(username: string): Promise<User | null> {
  try {
    return await request<User>(`/api/users/${encodeURIComponent(username)}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

/** Claims a new username (avatar required) or fetches an existing one (avatar ignored). */
export async function claimUser(username: string, avatar?: File): Promise<User> {
  const form = new FormData()
  form.set('username', username)
  if (avatar) form.set('avatar', avatar)
  return request<User>('/api/users', { method: 'POST', body: form })
}

export async function fetchPosts(cursor?: number): Promise<Post[]> {
  const params = new URLSearchParams()
  if (cursor !== undefined) params.set('cursor', String(cursor))
  const query = params.toString()
  return request<Post[]>(`/api/posts${query ? `?${query}` : ''}`)
}

export async function createPost(username: string, body: string): Promise<Post> {
  return request<Post>('/api/posts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, body }),
  })
}

export async function fetchComments(postId: number): Promise<Comment[]> {
  return request<Comment[]>(`/api/posts/${postId}/comments`)
}

/**
 * Live "% human" for one thread. Non-fatal — a failed poll just leaves the
 * counter stale, so this returns null rather than throwing.
 */
export async function fetchThreadStats(postId: number): Promise<ThreadStats | null> {
  try {
    return await request<ThreadStats>(`/api/posts/${postId}/thread-stats`)
  } catch {
    return null
  }
}

export async function addComment(postId: number, username: string, body: string): Promise<Comment> {
  return request<Comment>(`/api/posts/${postId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, body }),
  })
}

/**
 * The "sponsored" post targeted at this viewer's profiled mood. Non-fatal: a
 * failed ad fetch just means no ad card, never a broken feed — so this swallows
 * errors and returns null rather than throwing.
 */
export async function fetchSponsored(username: string): Promise<Ad | null> {
  try {
    const ad = await request<Ad>(`/api/sponsored?username=${encodeURIComponent(username)}`)
    return ad && ad.advertiser ? ad : null
  } catch {
    return null
  }
}

/**
 * "The Meter": the running estimated Claude spend behind the feed. Non-fatal —
 * a failed poll just leaves the meter stale, never disrupts the app.
 */
export async function fetchCosts(): Promise<CostSummary | null> {
  try {
    return await request<CostSummary>('/api/costs')
  } catch {
    return null
  }
}

export async function toggleLike(postId: number, username: string): Promise<{ liked: boolean; count: number }> {
  return request<{ liked: boolean; count: number }>(`/api/posts/${postId}/like`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username }),
  })
}
