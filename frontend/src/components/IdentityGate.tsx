import { useEffect, useState } from 'react'
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
import {
  completeSignup,
  createPost,
  errorMessage,
  requestMagicLink,
  verifyMagicLink,
  type User,
} from '../api'

interface Props {
  onIdentityResolved: (user: User) => void
}

type Step = 'email' | 'sent' | 'signup' | 'verifying'

/**
 * Onboarding flow: request a magic-link email, then (after the link is
 * clicked and lands back here with ?token=) either sign straight in
 * (returning email) or finish signup with a username + avatar + first post
 * (new email).
 */
export default function IdentityGate({ onIdentityResolved }: Props) {
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [pendingToken, setPendingToken] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const [avatar, setAvatar] = useState<File | null>(null)
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // A magic-link click lands back on `/` with ?token=... — no client-side
  // router needed for one query param.
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token')
    if (!token) return
    window.history.replaceState({}, '', window.location.pathname)
    setStep('verifying')
    verifyMagicLink(token)
      .then((result) => {
        if (result.status === 'logged_in') {
          onIdentityResolved(result.user)
        } else {
          setPendingToken(token)
          setEmail(result.email)
          setStep('signup')
        }
      })
      .catch((err) => {
        setError(errorMessage(err))
        setStep('email')
      })
  }, [onIdentityResolved])

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    setError(null)
    try {
      await requestMagicLink(email.trim())
      setStep('sent')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleSignupSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!username.trim() || !avatar || !body.trim() || !pendingToken) {
      if (!avatar) setError('An avatar is required.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const user = await completeSignup(pendingToken, username.trim(), avatar)
      await createPost(body.trim())
      onIdentityResolved(user)
    } catch (err) {
      setError(errorMessage(err))
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
          A think piece. Sign in with your email — we'll send you a link, no password needed.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {step === 'verifying' && <Typography>Checking your link…</Typography>}

        {step === 'email' && (
          <Box component="form" onSubmit={handleEmailSubmit} sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              type="email"
              label="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
            />
            <Button type="submit" variant="contained" disabled={loading}>
              Send link
            </Button>
          </Box>
        )}

        {step === 'sent' && (
          <Box>
            <Typography sx={{ mb: 2 }}>
              Check <strong>{email}</strong> for a sign-in link.
            </Typography>
            <Button size="small" onClick={() => setStep('email')}>
              Use a different email
            </Button>
          </Box>
        )}

        {step === 'signup' && (
          <Box component="form" onSubmit={handleSignupSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography>
              <strong>{email}</strong> checks out. Pick a username, an avatar, and write your first post.
            </Typography>
            <TextField
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
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
