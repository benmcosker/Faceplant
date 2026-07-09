import { useEffect, useState } from 'react'
import { Box, Button, Stack, TextField, Typography } from '@mui/material'
import { addComment, errorMessage, fetchComments, type Comment } from '../api'
import CommentItem from './CommentItem'
import CommentSkeleton from './CommentSkeleton'
import ErrorState from './ErrorState'
import { useToast } from './ToastProvider'

interface Props {
  postId: number
  username: string
  onCommentAdded: () => void
}

export default function CommentSection({ postId, username, onCommentAdded }: Props) {
  const toast = useToast()
  const [comments, setComments] = useState<Comment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchComments(postId)
      .then((data) => {
        if (!cancelled) setComments(data)
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [postId, retryKey])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!body.trim()) return
    setSubmitting(true)
    try {
      const comment = await addComment(postId, username, body.trim())
      setComments((prev) => [...prev, comment])
      setBody('')
      onCommentAdded()
    } catch (err) {
      // Keep the typed text so the user can retry the failed reply.
      toast.error(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box sx={{ mt: 2, pl: 2, borderLeft: '2px solid', borderColor: 'divider' }}>
      {loading ? (
        <Stack spacing={1.5} sx={{ mb: 2 }} role="status" aria-label="Loading comments">
          {Array.from({ length: 2 }).map((_, i) => (
            <CommentSkeleton key={i} />
          ))}
        </Stack>
      ) : error ? (
        <Box sx={{ mb: 2 }}>
          <ErrorState compact message={error} onRetry={() => setRetryKey((k) => k + 1)} />
        </Box>
      ) : (
        <Stack spacing={1.5} sx={{ mb: 2 }}>
          {comments.map((c) => (
            <CommentItem key={c.id} comment={c} />
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
          placeholder="Write a comment… or /giphy a keyword"
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
