import { useEffect, useState } from 'react'
import { Alert, Box, Button, Container, Stack } from '@mui/material'
import { ApiError, fetchPosts, type Post } from '../api'
import PostCard from './PostCard'
import PostCardSkeleton from './PostCardSkeleton'

interface Props {
  username: string
}

export default function Feed({ username }: Props) {
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)

  useEffect(() => {
    fetchPosts()
      .then((data) => {
        setPosts(data)
        setHasMore(data.length > 0)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load feed.'))
      .finally(() => setLoading(false))
  }, [])

  async function loadMore() {
    if (posts.length === 0) return
    const cursor = posts[posts.length - 1].id
    const more = await fetchPosts(cursor)
    setPosts((prev) => [...prev, ...more])
    setHasMore(more.length > 0)
  }

  return (
    <Container maxWidth="sm" sx={{ py: 4 }}>
      {error && <Alert severity="error">{error}</Alert>}
      {!loading && posts.length === 0 && !error && (
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
        <Button fullWidth onClick={loadMore}>
          Load more
        </Button>
      )}
    </Container>
  )
}
