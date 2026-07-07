import { Avatar, Box, Button, Card, CardContent, Typography } from '@mui/material'
import CampaignIcon from '@mui/icons-material/Campaign'
import type { Ad } from '../api'
import { useToast } from './ToastProvider'

/**
 * An emotion-targeted "sponsored" post. The banner states the surveillance out
 * loud — "targeted to your mood: X" — which is the whole point of the feature.
 */
export default function SponsoredCard({ ad }: { ad: Ad }) {
  const toast = useToast()
  return (
    <Card
      variant="outlined"
      sx={{ mb: 2, borderColor: 'secondary.main', bgcolor: 'rgba(255, 59, 48, 0.04)' }}
    >
      <Box
        sx={{
          px: 2,
          py: 0.75,
          bgcolor: 'secondary.main',
          color: 'secondary.contrastText',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <CampaignIcon fontSize="small" />
        <Typography
          variant="caption"
          sx={{ fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase' }}
        >
          Sponsored · targeted to your mood: {ad.mood}
        </Typography>
      </Box>
      <CardContent>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Avatar sx={{ bgcolor: 'primary.main' }}>{ad.advertiser.charAt(0)}</Avatar>
          <Box sx={{ flexGrow: 1 }}>
            <Typography sx={{ fontWeight: 700 }}>{ad.advertiser}</Typography>
            <Typography sx={{ mt: 0.5, fontStyle: 'italic' }}>{ad.tagline}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {ad.body}
            </Typography>
            <Button
              size="small"
              variant="contained"
              color="secondary"
              sx={{ mt: 1.5 }}
              onClick={() => toast.showToast("This ad isn't real. The targeting is.", 'info')}
            >
              {ad.cta}
            </Button>
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}
