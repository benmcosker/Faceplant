import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PostComposer from './PostComposer'
import { ToastProvider } from './ToastProvider'
import type { Post } from '../api'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return { ...actual, createPost: vi.fn() }
})
import { createPost } from '../api'

const POSTED: Post = {
  id: 5,
  body: 'fresh take',
  created_at: new Date().toISOString(),
  author: { id: 1, username: 'me', avatar_url: '/a.png', is_bot: false },
  like_count: 0,
  comment_count: 0,
  top_comments: [],
  human_share: 1,
  human_messages: 1,
  bot_messages: 0,
  total_messages: 1,
}

describe('PostComposer', () => {
  it('posts the typed body and clears the field', async () => {
    vi.mocked(createPost).mockResolvedValue(POSTED)
    const onPosted = vi.fn()

    render(
      <ToastProvider>
        <PostComposer onPosted={onPosted} />
      </ToastProvider>,
    )

    const field = screen.getByPlaceholderText("What's on your mind?")
    await userEvent.type(field, 'fresh take')
    await userEvent.click(screen.getByRole('button', { name: 'Post' }))

    await waitFor(() => {
      expect(createPost).toHaveBeenCalledWith('fresh take')
    })
    expect(onPosted).toHaveBeenCalledWith(POSTED)
    expect(field).toHaveValue('')
  })
})
