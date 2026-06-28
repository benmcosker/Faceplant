import { useState } from 'react'
import {
  Alert,
  Avatar,
  Box,
  Button,
  Container,
  Paper,
  TextField,
  Typography,
} from '@mui/material'
import { ApiError, claimUser, createPost, fetchUser, setIdentity } from '../api'

interface Props {
  onIdentityResolved: (username: string) => void
}

type Step = 'username' | 'new' | 'returning'

/**
 * Onboarding flow: claim/look up a username, then post (avatar required
 * only for a brand-new username — a duplicate username just means "post as
 * that user again").
 */
export default function IdentityGate({ onIdentityResolved }: Props) {
  const [step, setStep] = useState<Step>('username')
  const [username, setUsername] = useState('')
  const [avatar, setAvatar] = useState<File | null>(null)
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleUsernameSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!username.trim()) return
    setLoading(true)
    setError(null)
    try {
      const existing = await fetchUser(username.trim())
      setStep(existing ? 'returning' : 'new')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  async function handlePostSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!body.trim()) return
    if (step === 'new' && !avatar) {
      setError('An avatar is required for a new username.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      if (step === 'new') {
        await claimUser(username.trim(), avatar ?? undefined)
      }
      await createPost(username.trim(), body.trim())
      setIdentity(username.trim().toLowerCase())
      onIdentityResolved(username.trim().toLowerCase())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Container maxWidth="sm" sx={{ py: 8 }}>
      <Paper sx={{ p: 4 }} variant="outlined">
        <Typography variant="h4" sx={{ mb: 1 }}>
          faceplant
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          A think piece. Claim a username — typing one that already exists just posts as that
          person again.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {step === 'username' && (
          <Box component="form" onSubmit={handleUsernameSubmit} sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
            <Button type="submit" variant="contained" disabled={loading}>
              Continue
            </Button>
          </Box>
        )}

        {step === 'new' && (
          <Box component="form" onSubmit={handlePostSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography>
              <strong>{username}</strong> is new. Pick an avatar and write your first post.
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Avatar src={avatar ? URL.createObjectURL(avatar) : undefined} sx={{ width: 56, height: 56 }} />
              <Button component="label" variant="outlined">
                Choose avatar
                <input
                  type="file"
                  hidden
                  accept="image/png,image/jpeg,image/webp,image/gif"
                  onChange={(e) => setAvatar(e.target.files?.[0] ?? null)}
                />
              </Button>
            </Box>
            <TextField
              label="What's on your mind?"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              multiline
              minRows={3}
              autoFocus
            />
            <Button type="submit" variant="contained" disabled={loading}>
              Post
            </Button>
          </Box>
        )}

        {step === 'returning' && (
          <Box component="form" onSubmit={handlePostSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography>
              Welcome back, <strong>{username}</strong>. What's on your mind?
            </Typography>
            <TextField
              label="What's on your mind?"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              multiline
              minRows={3}
              autoFocus
            />
            <Button type="submit" variant="contained" disabled={loading}>
              Post
            </Button>
          </Box>
        )}
      </Paper>
    </Container>
  )
}
