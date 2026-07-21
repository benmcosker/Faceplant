import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Feed from './Feed'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return {
    ...actual,
    fetchPosts: vi.fn(),
    fetchSponsored: vi.fn(() => Promise.resolve(null)),
    createPost: vi.fn(),
  }
})
import { type Ad, ApiError, createPost, fetchPosts, fetchSponsored, type Post } from '../api'

const POST: Post = {
  id: 1,
  body: 'hello world',
  created_at: new Date().toISOString(),
  author: { id: 2, username: 'someone', avatar_url: '/media/avatars/x.png', is_bot: false },
  like_count: 3,
  comment_count: 1,
  top_comments: [],
  human_share: 0.5,
  human_messages: 1,
  bot_messages: 1,
  total_messages: 2,
}

const AD: Ad = {
  advertiser: 'Evergreen Farewell Plans',
  tagline: 'We saw you say goodbye today.',
  body: 'Lock in today’s prices before you need them.',
  cta: 'Get your quote',
  mood: 'sad',
  url: 'https://en.wikipedia.org/wiki/Funeral',
}

describe('Feed', () => {
  it('renders posts returned by the API', async () => {
    vi.mocked(fetchPosts).mockResolvedValue([POST])

    render(<Feed />)

    expect(await screen.findByText('hello world')).toBeInTheDocument()
    expect(screen.getByText('someone')).toBeInTheDocument()
  })

  it('injects a mood-targeted sponsored card into the feed', async () => {
    vi.mocked(fetchPosts).mockResolvedValue([POST])
    vi.mocked(fetchSponsored).mockResolvedValue(AD)

    render(<Feed />)

    expect(await screen.findByText('Evergreen Farewell Plans')).toBeInTheDocument()
    expect(screen.getByText(/targeted to your mood: sad/i)).toBeInTheDocument()
    expect(screen.getByText('We saw you say goodbye today.')).toBeInTheDocument()
  })

  it('shows skeleton placeholders while the feed is loading', async () => {
    let resolvePosts: (posts: Post[]) => void = () => {}
    vi.mocked(fetchPosts).mockReturnValue(
      new Promise<Post[]>((resolve) => {
        resolvePosts = resolve
      }),
    )

    render(<Feed />)

    // While the request is pending, the loading skeletons are shown.
    expect(screen.getByRole('status', { name: 'Loading posts' })).toBeInTheDocument()

    // Once it resolves, the skeletons give way to the real content.
    resolvePosts([POST])
    expect(await screen.findByText('hello world')).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Loading posts' })).toBeNull()
  })

  it('shows an empty-state message when there are no posts', async () => {
    vi.mocked(fetchPosts).mockResolvedValue([])

    render(<Feed />)

    expect(await screen.findByText('No posts yet. Be the first.')).toBeInTheDocument()
  })

  it('shows an error message when the feed fails to load', async () => {
    vi.mocked(fetchPosts).mockRejectedValue(new ApiError('nope', 502, 'upstream_error'))

    render(<Feed />)

    expect(await screen.findByText('nope')).toBeInTheDocument()
  })

  it('recovers from a load failure when "Try again" is clicked', async () => {
    vi.mocked(fetchPosts)
      .mockRejectedValueOnce(new ApiError('nope', 502, 'upstream_error'))
      .mockResolvedValueOnce([POST])

    render(<Feed />)

    const retry = await screen.findByRole('button', { name: /try again/i })
    await userEvent.click(retry)

    expect(await screen.findByText('hello world')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /try again/i })).toBeNull()
  })

  it('prepends a post made via the composer to the top of the feed', async () => {
    vi.mocked(fetchPosts).mockResolvedValue([POST])
    const newPost: Post = { ...POST, id: 99, body: 'brand new take' }
    vi.mocked(createPost).mockResolvedValue(newPost)

    render(<Feed />)
    expect(await screen.findByText('hello world')).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText("What's on your mind?"), 'brand new take')
    await userEvent.click(screen.getByRole('button', { name: 'Post' }))

    const posts = await screen.findAllByText(/hello world|brand new take/)
    expect(posts.map((el) => el.textContent)).toEqual(['brand new take', 'hello world'])
  })
})
