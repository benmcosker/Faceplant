import { Box, Skeleton } from '@mui/material'

/** Placeholder that mirrors a single comment row while comments are loading. */
export default function CommentSkeleton() {
  return (
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Skeleton variant="circular" width={28} height={28} />
      <Box sx={{ flexGrow: 1 }}>
        <Skeleton variant="text" width="90%" />
      </Box>
    </Box>
  )
}
