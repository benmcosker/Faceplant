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
  fetchMe,
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

  // Magic links open in a new tab in most webmail clients, so the tab that's
  // still sitting on "sent" never learns the token was verified there. Recheck
  // auth whenever this tab regains focus, so switching back finds you logged in
  // instead of stuck offering to "use a different email".
  useEffect(() => {
    if (step !== 'sent') return
    let cancelled = false
    const check = () => {
      if (document.visibilityState !== 'visible') return
      fetchMe().then((user) => {
        if (!cancelled && user) onIdentityResolved(user)
      })
    }
    document.addEventListener('visibilitychange', check)
    window.addEventListener('focus', check)
    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', check)
      window.removeEventListener('focus', check)
    }
  }, [step, onIdentityResolved])

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
        <Typography variant="h4" sx={{ mb: 0.5 }}>
          faceplant
        </Typography>
        <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 700, color: 'secondary.main' }}>
          Engagement is free. We show you the bill.
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          A social network that's honest about being fake — the likes are bots, the ads read
          your mood, and a live meter tallies what your manufactured engagement really costs.
          Sign in with your email; we'll send a link, no password.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {step === 'verifying' && <Typography>Verifying you're human…</Typography>}

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
            <Button type="submit" variant="contained" disabled={loading} sx={{ whiteSpace: 'nowrap' }}>
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
              <strong>{email}</strong> checks out — you're real, for now. Pick a handle, a face,
              and write your first post.
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
