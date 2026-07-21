import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PostCard from './PostCard'
import { ToastProvider } from './ToastProvider'
import type { Comment, Post } from '../api'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return {
    ...actual,
    fetchComments: vi.fn(() => Promise.resolve([])),
    fetchThreadStats: vi.fn(() => Promise.resolve(null)),
    toggleLike: vi.fn(),
  }
})
import { fetchComments, fetchThreadStats } from '../api'

const bot = (username: string): Comment['author'] => ({
  id: 99,
  username,
  avatar_url: '/x.png',
  is_bot: true,
})

const reply = (id: number, username: string, body: string): Comment => ({
  id,
  body,
  created_at: '2026-07-08T00:00:00Z',
  author: bot(username),
})

function makePost(overrides: Partial<Post>): Post {
  return {
    id: 1,
    body: 'will cat people ever get along with dog people?',
    created_at: '2026-07-08T00:00:00Z',
    author: { id: 1, username: 'human', avatar_url: '/a.png', is_bot: false },
    like_count: 5,
    comment_count: 0,
    top_comments: [],
    human_share: 1,
    human_messages: 1,
    bot_messages: 0,
    total_messages: 1,
    ...overrides,
  }
}

function renderCard(post: Post) {
  return render(
    <ToastProvider>
      <PostCard post={post} />
    </ToastProvider>,
  )
}

describe('PostCard reply peek', () => {
  it('shows the top replies inline without a click', () => {
    renderCard(
      makePost({
        comment_count: 5,
        top_comments: [
          reply(1, 'wakeupsheeple', 'do your own research'),
          reply(2, 'notimpressedned', 'not groundbreaking'),
        ],
      }),
    )

    expect(screen.getByText('wakeupsheeple')).toBeInTheDocument()
    expect(screen.getByText('do your own research')).toBeInTheDocument()
    // 5 total − 2 peeked = 3 more.
    expect(screen.getByRole('button', { name: 'Show 3 more replies' })).toBeInTheDocument()
  })

  it('expands to the full thread when "show more" is clicked', async () => {
    renderCard(
      makePost({
        comment_count: 5,
        top_comments: [reply(1, 'wakeupsheeple', 'do your own research')],
      }),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Show 4 more replies' }))
    expect(fetchComments).toHaveBeenCalledWith(1)
  })

  it('shows no peek and no "show more" when there are no replies', () => {
    renderCard(makePost({ comment_count: 0, top_comments: [] }))

    expect(screen.queryByText(/Show .* repl/)).not.toBeInTheDocument()
  })

  it('omits "show more" when the peek already covers every reply', () => {
    renderCard(
      makePost({
        comment_count: 1,
        top_comments: [reply(1, 'onlyreply', 'first!')],
      }),
    )

    expect(screen.getByText('onlyreply')).toBeInTheDocument()
    expect(screen.queryByText(/Show .* repl/)).not.toBeInTheDocument()
  })
})

describe('PostCard % human counter', () => {
  it('shows the % human from the post', () => {
    renderCard(makePost({ human_share: 0.2, human_messages: 1, bot_messages: 4, total_messages: 5 }))
    expect(screen.getByText('20% human')).toBeInTheDocument()
  })

  it('shows "dead internet" when no humans remain', () => {
    renderCard(makePost({ human_share: 0, human_messages: 0, bot_messages: 6, total_messages: 6 }))
    expect(screen.getByText('dead internet')).toBeInTheDocument()
  })

  it('polls thread-stats and drops the % as the swarm piles on', async () => {
    vi.mocked(fetchThreadStats).mockResolvedValue({
      human_share: 0.1,
      human_messages: 1,
      bot_messages: 9,
      total_messages: 10,
    })
    renderCard(
      makePost({
        comment_count: 3,
        top_comments: [reply(1, 'wakeupsheeple', 'x')],
        human_share: 0.4,
        human_messages: 1,
        bot_messages: 2,
        total_messages: 3,
      }),
    )

    expect(screen.getByText('40% human')).toBeInTheDocument()
    // Opening the thread starts the poll, which reports a fresher, lower share.
    await userEvent.click(screen.getByRole('button', { name: 'Show 2 more replies' }))
    expect(await screen.findByText('10% human')).toBeInTheDocument()
    expect(fetchThreadStats).toHaveBeenCalledWith(1)
  })
})
