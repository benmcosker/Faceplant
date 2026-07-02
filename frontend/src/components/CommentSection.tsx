import { useEffect, useState } from 'react'
import { Avatar, Box, Button, Stack, TextField, Typography } from '@mui/material'
import { addComment, fetchComments, type Comment } from '../api'
import { renderBodyWithGifs } from './gifBody'

interface Props {
  postId: number
  username: string
  onCommentAdded: () => void
}

export default function CommentSection({ postId, username, onCommentAdded }: Props) {
  const [comments, setComments] = useState<Comment[]>([])
  const [loading, setLoading] = useState(true)
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchComments(postId).then((data) => {
      if (!cancelled) {
        setComments(data)
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [postId])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!body.trim()) return
    setSubmitting(true)
    try {
      const comment = await addComment(postId, username, body.trim())
      setComments((prev) => [...prev, comment])
      setBody('')
      onCommentAdded()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box sx={{ mt: 2, pl: 2, borderLeft: '2px solid', borderColor: 'divider' }}>
      {loading ? (
        <Typography variant="body2" color="text.secondary">
          Loading comments…
        </Typography>
      ) : (
        <Stack spacing={1.5} sx={{ mb: 2 }}>
          {comments.map((c) => (
            <Box key={c.id} sx={{ display: 'flex', gap: 1 }}>
              <Avatar src={c.author.avatar_url} sx={{ width: 28, height: 28 }} />
              <Box>
                <Typography variant="body2" component="div">
                  <strong>{c.author.username}</strong> {renderBodyWithGifs(c.body)}
                </Typography>
              </Box>
            </Box>
          ))}
          {comments.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              No comments yet.
            </Typography>
          )}
        </Stack>
      )}

      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', gap: 1 }}>
        <TextField
          size="small"
          fullWidth
          placeholder="Write a comment…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <Button type="submit" size="small" variant="outlined" disabled={submitting}>
          Reply
        </Button>
      </Box>
    </Box>
  )
}
