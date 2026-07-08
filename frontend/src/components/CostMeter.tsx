import { useEffect, useState } from 'react'
import { Box, Button, Divider, Popover, Stack, Typography } from '@mui/material'
import PaidOutlinedIcon from '@mui/icons-material/PaidOutlined'
import { fetchCosts, type CostSummary } from '../api'

const POLL_MS = 4000

// Enough precision to watch fractions of a cent tick up as the swarm reacts.
const usd = (n: number) => `$${n.toFixed(4)}`

const SOURCE_LABELS: Record<string, string> = {
  bot_reaction: 'Bot swarm',
  ad_tagline: 'Ad targeting',
}

/**
 * "The Meter" — a live readout of the estimated Claude spend behind the feed.
 * Polls /api/costs, so it visibly ticks up as the bot swarm reacts and the ad
 * network generates taglines. The point: manufactured engagement isn't free.
 */
export default function CostMeter() {
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)

  useEffect(() => {
    let cancelled = false
    const tick = () =>
      fetchCosts().then((c) => {
        if (!cancelled && c) setCost(c)
      })
    tick()
    const id = setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const total = cost?.total_cost_usd ?? 0

  return (
    <>
      <Button
        color="inherit"
        size="small"
        startIcon={<PaidOutlinedIcon />}
        onClick={(e) => setAnchorEl(e.currentTarget)}
        aria-label="AI cost meter"
        sx={{ textTransform: 'none', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}
      >
        {usd(total)}
      </Button>
      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Box sx={{ p: 2, width: 320 }}>
          <Typography variant="overline" color="text.secondary">
            The cost of manufactured engagement
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 800, fontVariantNumeric: 'tabular-nums' }}>
            {usd(total)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            estimated Claude spend · {cost?.total_calls ?? 0} API calls
          </Typography>

          <Divider sx={{ my: 1.5 }} />

          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            What's spending
          </Typography>
          <Stack spacing={0.5} sx={{ mb: 1.5 }}>
            {Object.entries(cost?.by_source ?? {}).map(([source, s]) => (
              <Box key={source} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">{SOURCE_LABELS[source] ?? source}</Typography>
                <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {usd(s.cost_usd)}
                </Typography>
              </Box>
            ))}
            {(!cost || Object.keys(cost.by_source).length === 0) && (
              <Typography variant="body2" color="text.secondary">
                No spend yet — post something and watch the swarm.
              </Typography>
            )}
          </Stack>

          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Cost per human user
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {usd(cost?.cost_per_human_user_avg ?? 0)} avg across {cost?.human_user_count ?? 0} humans
          </Typography>
          <Stack spacing={0.5} sx={{ mt: 0.5 }}>
            {(cost?.per_human_user ?? []).slice(0, 5).map((u) => (
              <Box key={u.username} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">{u.username}</Typography>
                <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {usd(u.cost_usd)}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Box>
      </Popover>
    </>
  )
}
