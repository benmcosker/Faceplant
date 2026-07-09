import { Avatar, Box, Typography } from '@mui/material'
import { type Comment } from '../api'
import { renderBodyWithGifs } from './gifBody'

/** One reply: avatar + author + body (with inline GIFs). Shared by the feed
 * peek and the full comment thread so they render identically. */
export default function CommentItem({ comment }: { comment: Comment }) {
  return (
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Avatar src={comment.author.avatar_url} sx={{ width: 28, height: 28 }} />
      <Box>
        <Typography variant="body2" component="div">
          <strong>{comment.author.username}</strong> {renderBodyWithGifs(comment.body)}
        </Typography>
      </Box>
    </Box>
  )
}
