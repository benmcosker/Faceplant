import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IdentityGate from './IdentityGate'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return {
    ...actual,
    fetchUser: vi.fn(),
    claimUser: vi.fn(),
    createPost: vi.fn(),
    setIdentity: vi.fn(),
  }
})
import { claimUser, createPost, fetchUser, setIdentity, type User } from '../api'

const EXISTING_USER: User = {
  id: 1,
  username: 'returninguser',
  avatar_url: '/media/avatars/x.png',
  is_bot: false,
}

describe('IdentityGate', () => {
  it('shows the avatar + first-post step for a brand-new username', async () => {
    vi.mocked(fetchUser).mockResolvedValue(null)
    const onIdentityResolved = vi.fn()

    render(<IdentityGate onIdentityResolved={onIdentityResolved} />)

    await userEvent.type(screen.getByLabelText('Username'), 'newperson')
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText(/is new/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose avatar' })).toBeInTheDocument()
  })

  it('skips the avatar step for an existing username and posts directly', async () => {
    vi.mocked(fetchUser).mockResolvedValue(EXISTING_USER)
    vi.mocked(createPost).mockResolvedValue({
      id: 1,
      body: 'hello again',
      created_at: new Date().toISOString(),
      author: EXISTING_USER,
      like_count: 0,
      comment_count: 0,
    })
    const onIdentityResolved = vi.fn()

    render(<IdentityGate onIdentityResolved={onIdentityResolved} />)

    await userEvent.type(screen.getByLabelText('Username'), 'returninguser')
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText(/Welcome back/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Choose avatar' })).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText("What's on your mind?"), 'hello again')
    await userEvent.click(screen.getByRole('button', { name: 'Post' }))

    await waitFor(() => {
      expect(createPost).toHaveBeenCalledWith('returninguser', 'hello again')
    })
    expect(claimUser).not.toHaveBeenCalled()
    expect(setIdentity).toHaveBeenCalledWith('returninguser')
    expect(onIdentityResolved).toHaveBeenCalledWith('returninguser')
  })
})
