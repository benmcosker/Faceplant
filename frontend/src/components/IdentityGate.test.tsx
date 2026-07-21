import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IdentityGate from './IdentityGate'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return {
    ...actual,
    requestMagicLink: vi.fn(),
    verifyMagicLink: vi.fn(),
    completeSignup: vi.fn(),
    createPost: vi.fn(),
  }
})
import { completeSignup, createPost, requestMagicLink, verifyMagicLink, type User } from '../api'

const NEW_USER: User = {
  id: 2,
  username: 'newperson',
  avatar_url: '/media/avatars/newperson.png',
  is_bot: false,
}

const RETURNING_USER: User = {
  id: 1,
  username: 'returninguser',
  avatar_url: '/media/avatars/x.png',
  is_bot: false,
}

beforeEach(() => {
  window.history.replaceState({}, '', '/')
})

// jsdom doesn't implement createObjectURL; the avatar preview calls it once a
// file is chosen.
URL.createObjectURL = vi.fn(() => 'blob:mock-url')

describe('IdentityGate', () => {
  it('requests a magic link and shows the "check your email" step', async () => {
    vi.mocked(requestMagicLink).mockResolvedValue(undefined)
    const onIdentityResolved = vi.fn()

    render(<IdentityGate onIdentityResolved={onIdentityResolved} />)

    await userEvent.type(screen.getByLabelText('Email'), 'newperson@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send link' }))

    expect(await screen.findByText(/newperson@example.com/)).toBeInTheDocument()
    expect(requestMagicLink).toHaveBeenCalledWith('newperson@example.com')
  })

  it('logs a returning email in directly once the link is verified', async () => {
    window.history.replaceState({}, '', '/?token=abc123')
    vi.mocked(verifyMagicLink).mockResolvedValue({ status: 'logged_in', user: RETURNING_USER })
    const onIdentityResolved = vi.fn()

    render(<IdentityGate onIdentityResolved={onIdentityResolved} />)

    await waitFor(() => {
      expect(onIdentityResolved).toHaveBeenCalledWith(RETURNING_USER)
    })
    expect(verifyMagicLink).toHaveBeenCalledWith('abc123')
  })

  it('collects a username, avatar, and first post for a brand-new email', async () => {
    window.history.replaceState({}, '', '/?token=freshtoken')
    vi.mocked(verifyMagicLink).mockResolvedValue({ status: 'new', email: 'newperson@example.com' })
    vi.mocked(completeSignup).mockResolvedValue(NEW_USER)
    vi.mocked(createPost).mockResolvedValue({
      id: 1,
      body: 'hello there',
      created_at: new Date().toISOString(),
      author: NEW_USER,
      like_count: 0,
      comment_count: 0,
      top_comments: [],
      human_share: 1,
      human_messages: 1,
      bot_messages: 0,
      total_messages: 1,
    })
    const onIdentityResolved = vi.fn()

    render(<IdentityGate onIdentityResolved={onIdentityResolved} />)

    expect(await screen.findByText(/newperson@example.com/)).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Username'), 'newperson')
    const file = new File(['avatar bytes'], 'avatar.png', { type: 'image/png' })
    await userEvent.upload(screen.getByLabelText('Choose avatar'), file)
    await userEvent.type(screen.getByLabelText("What's on your mind?"), 'hello there')
    await userEvent.click(screen.getByRole('button', { name: 'Post' }))

    await waitFor(() => {
      expect(completeSignup).toHaveBeenCalledWith('freshtoken', 'newperson', file)
    })
    expect(createPost).toHaveBeenCalledWith('hello there')
    expect(onIdentityResolved).toHaveBeenCalledWith(NEW_USER)
  })
})
