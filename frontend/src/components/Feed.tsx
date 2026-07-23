import { Fragment, useCallback, useEffect, useState } from 'react'
import { Alert, Box, Button, Container, Stack } from '@mui/material'
import { type Ad, errorMessage, fetchPosts, fetchSponsored, type Post } from '../api'
import PostCard from './PostCard'
import PostCardSkeleton from './PostCardSkeleton'
import PostComposer from './PostComposer'
import SponsoredCard from './SponsoredCard'
import ErrorState from './ErrorState'
import { useToast } from './ToastProvider'

// How often to check for new posts (e.g. bot-originated ones) landing at the
// top of the feed, without the viewer having to reload the page.
const NEW_POSTS_POLL_MS = 5000

export default function Feed() {
  const toast = useToast()
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [ad, setAd] = useState<Ad | null>(null)

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

  // Silently pick up new posts (including bot-originated ones) as they land,
  // prepending anything not already in the list. Best-effort — a failed
  // background poll shouldn't surface an error over an otherwise-fine feed.
  useEffect(() => {
    const id = setInterval(() => {
      fetchPosts()
        .then((latest) => {
          setPosts((prev) => {
            const known = new Set(prev.map((p) => p.id))
            const fresh = latest.filter((p) => !known.has(p.id))
            return fresh.length ? [...fresh, ...prev] : prev
          })
        })
        .catch(() => {})
    }, NEW_POSTS_POLL_MS)
    return () => clearInterval(id)
  }, [])

  // The platform's targeted "sponsored" post, keyed to this viewer's profiled
  // mood. Best-effort — fetchSponsored never throws, just yields null.
  useEffect(() => {
    let cancelled = false
    fetchSponsored().then((a) => {
      if (!cancelled) setAd(a)
    })
    return () => {
      cancelled = true
    }
  }, [])

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
      <PostComposer onPosted={(post) => setPosts((prev) => [post, ...prev])} />
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
              {posts.map((post, i) => (
                <Fragment key={post.id}>
                  <PostCard post={post} />
                  {/* Slot the targeted ad into the feed after the first post. */}
                  {i === 0 && ad && <SponsoredCard ad={ad} />}
                </Fragment>
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
