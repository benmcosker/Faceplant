import { Box, Card, CardContent, Skeleton, Stack } from '@mui/material'

/** Placeholder that mirrors PostCard's layout while the feed is loading. */
export default function PostCardSkeleton() {
  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Skeleton variant="circular" width={40} height={40} />
          <Box sx={{ flexGrow: 1 }}>
            <Skeleton variant="text" width="30%" sx={{ fontSize: '1rem' }} />
            <Skeleton variant="text" width="20%" sx={{ fontSize: '0.75rem' }} />
            <Skeleton variant="text" sx={{ mt: 1 }} />
            <Skeleton variant="text" width="80%" />
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Skeleton variant="rounded" width={48} height={30} />
              <Skeleton variant="rounded" width={48} height={30} />
            </Stack>
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}
