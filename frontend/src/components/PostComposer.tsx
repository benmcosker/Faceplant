import { useState } from 'react'
import { Box, Button, Paper, TextField } from '@mui/material'
import { createPost, errorMessage, type Post } from '../api'
import { useToast } from './ToastProvider'

interface Props {
  onPosted: (post: Post) => void
}

/** Always-visible composer for a signed-in user's next post. */
export default function PostComposer({ onPosted }: Props) {
  const toast = useToast()
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!body.trim()) return
    setSubmitting(true)
    try {
      const post = await createPost(body.trim())
      setBody('')
      onPosted(post)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="What's on your mind?"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          multiline
          minRows={1}
          maxRows={6}
        />
        <Button type="submit" variant="contained" disabled={submitting}>
          Post
        </Button>
      </Box>
    </Paper>
  )
}
