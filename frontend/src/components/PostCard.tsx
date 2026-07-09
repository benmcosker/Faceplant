import { useState } from 'react'
import { Avatar, Box, Button, Card, CardContent, Stack, Typography } from '@mui/material'
import FavoriteIcon from '@mui/icons-material/Favorite'
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder'
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutlined'
import { errorMessage, toggleLike, type Post } from '../api'
import CommentItem from './CommentItem'
import CommentSection from './CommentSection'
import { renderBodyWithGifs } from './gifBody'
import { useToast } from './ToastProvider'

interface Props {
  post: Post
  username: string
}

export default function PostCard({ post, username }: Props) {
  const toast = useToast()
  const [liked, setLiked] = useState(false)
  const [likeCount, setLikeCount] = useState(post.like_count)
  const [commentCount, setCommentCount] = useState(post.comment_count)
  const [showComments, setShowComments] = useState(false)

  // Replies beyond the inline peek, revealed by expanding the full thread.
  const moreCount = commentCount - post.top_comments.length

  async function handleLike() {
    try {
      const result = await toggleLike(post.id, username)
      setLiked(result.liked)
      setLikeCount(result.count)
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Avatar src={post.author.avatar_url} />
          <Box sx={{ flexGrow: 1 }}>
            <Typography sx={{ fontWeight: 700 }}>{post.author.username}</Typography>
            <Typography variant="caption" color="text.secondary">
              {new Date(post.created_at).toLocaleString()}
            </Typography>
            <Typography component="div" sx={{ mt: 1 }}>
              {renderBodyWithGifs(post.body)}
            </Typography>

            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Button
                size="small"
                startIcon={liked ? <FavoriteIcon color="secondary" /> : <FavoriteBorderIcon />}
                onClick={handleLike}
              >
                {likeCount}
              </Button>
              <Button
                size="small"
                startIcon={<ChatBubbleOutlineIcon />}
                onClick={() => setShowComments((v) => !v)}
              >
                {commentCount}
              </Button>
            </Stack>

            {/* Peek: the first replies inline, so the swarm is visible without a
                click. Expands to the full thread on demand. */}
            {!showComments && post.top_comments.length > 0 && (
              <Stack
                spacing={1.5}
                sx={{ mt: 1.5, pl: 2, borderLeft: '2px solid', borderColor: 'divider' }}
              >
                {post.top_comments.map((c) => (
                  <CommentItem key={c.id} comment={c} />
                ))}
                {moreCount > 0 && (
                  <Button
                    size="small"
                    onClick={() => setShowComments(true)}
                    sx={{ alignSelf: 'flex-start', textTransform: 'none' }}
                  >
                    Show {moreCount} more {moreCount === 1 ? 'reply' : 'replies'}
                  </Button>
                )}
              </Stack>
            )}

            {showComments && (
              <CommentSection
                postId={post.id}
                username={username}
                onCommentAdded={() => setCommentCount((c) => c + 1)}
              />
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}
