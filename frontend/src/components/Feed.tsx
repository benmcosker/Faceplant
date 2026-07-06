import { useCallback, useEffect, useState } from 'react'
import { Alert, Box, Button, Container, Stack } from '@mui/material'
import { errorMessage, fetchPosts, type Post } from '../api'
import PostCard from './PostCard'
import PostCardSkeleton from './PostCardSkeleton'
import ErrorState from './ErrorState'
import { useToast } from './ToastProvider'

interface Props {
  username: string
}

export default function Feed({ username }: Props) {
  const toast = useToast()
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchPosts()
      .then((data) => {
        setPosts(data)
        setHasMore(data.length > 0)
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // A failed "load more" is non-blocking — the feed above it is still valid —
  // so it's surfaced as a toast rather than replacing the whole view.
  async function loadMore() {
    if (posts.length === 0) return
    setLoadingMore(true)
    try {
      const cursor = posts[posts.length - 1].id
      const more = await fetchPosts(cursor)
      setPosts((prev) => [...prev, ...more])
      setHasMore(more.length > 0)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <Container maxWidth="sm" sx={{ py: 4 }}>
      {error && !loading ? (
        <ErrorState message={error} onRetry={load} title="Couldn't load the feed" />
      ) : (
        <>
          {!loading && posts.length === 0 && (
            <Alert severity="info">No posts yet. Be the first.</Alert>
          )}
          {loading ? (
            <Box role="status" aria-label="Loading posts">
              {Array.from({ length: 3 }).map((_, i) => (
                <PostCardSkeleton key={i} />
              ))}
            </Box>
          ) : (
            <Stack>
              {posts.map((post) => (
                <PostCard key={post.id} post={post} username={username} />
              ))}
            </Stack>
          )}
          {hasMore && posts.length > 0 && (
            <Button fullWidth onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Loading…' : 'Load more'}
            </Button>
          )}
        </>
      )}
    </Container>
  )
}
