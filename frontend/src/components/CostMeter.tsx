import { useEffect, useState } from 'react'
import { Box, Button, Divider, Popover, Stack, Typography } from '@mui/material'
import PaidOutlinedIcon from '@mui/icons-material/PaidOutlined'
import { fetchCosts, type CostSummary, type SpendEvent } from '../api'

const POLL_MS = 4000

// Enough precision to watch fractions of a cent tick up as the swarm reacts.
const usd = (n: number) => `$${n.toFixed(4)}`

const SOURCE_LABELS: Record<string, string> = {
  bot_reaction: 'Bot swarm',
  ad_tagline: 'Ad targeting',
}

/** Human-readable line for one metered call in the recent-spend ticker. */
function eventLabel(e: SpendEvent): string {
  const actor = e.actor ?? 'someone'
  const human = e.human_username ?? 'the feed'
  if (e.source === 'ad_tagline') return `${actor} targeted ${human}`
  if (e.source === 'bot_reaction') return `${actor} reacted to ${human}`
  return `${actor} → ${human}`
}

/**
 * A dependency-free inline-SVG sparkline of the per-minute spend. Flat when idle,
 * spiky when the swarm wakes up — the shape *is* the story of bursty manufactured
 * engagement.
 */
function Sparkline({ data }: { data: number[] }) {
  const w = 288
  const h = 40
  const max = Math.max(...data, 0)
  if (data.length < 2 || max <= 0) {
    return (
      <Box
        sx={{
          height: h,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'text.disabled',
        }}
      >
        <Typography variant="caption">quiet for now</Typography>
      </Box>
    )
  }
  const step = w / (data.length - 1)
  const points = data
    .map((v, i) => `${(i * step).toFixed(1)},${(h - (v / max) * (h - 4) - 2).toFixed(1)}`)
    .join(' ')
  const area = `0,${h} ${points} ${w},${h}`
  return (
    <Box component="svg" viewBox={`0 0 ${w} ${h}`} sx={{ width: '100%', height: h, display: 'block' }}>
      <polygon points={area} fill="currentColor" opacity={0.12} />
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </Box>
  )
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
  const recent = cost?.recent ?? []

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

          {/* Derived stats: how much each human post costs, and how fast it's burning. */}
          <Box sx={{ display: 'flex', gap: 2, mt: 1.5 }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" color="text.secondary" display="block">
                per post
              </Typography>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                {usd(cost?.cost_per_post_usd ?? 0)}
              </Typography>
            </Box>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" color="text.secondary" display="block">
                spend rate
              </Typography>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                {usd(cost?.rate_per_min_usd ?? 0)}
                <Typography component="span" variant="caption" color="text.secondary">
                  {' '}
                  /min
                </Typography>
              </Typography>
            </Box>
          </Box>

          <Box sx={{ mt: 1, color: 'primary.main' }}>
            <Sparkline data={cost?.spend_per_min ?? []} />
          </Box>
          <Typography variant="caption" color="text.secondary">
            spend per minute · last 15 min
          </Typography>

          <Divider sx={{ my: 1.5 }} />

          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Recent activity
          </Typography>
          <Stack spacing={0.5} sx={{ mb: 1.5 }}>
            {recent.map((e, i) => (
              <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                <Typography variant="body2" noWrap sx={{ minWidth: 0 }}>
                  {eventLabel(e)}
                </Typography>
                <Typography
                  variant="body2"
                  color="success.main"
                  sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}
                >
                  +{usd(e.cost_usd)}
                </Typography>
              </Box>
            ))}
            {recent.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                No spend yet — post something and watch the swarm.
              </Typography>
            )}
          </Stack>

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
                Nothing yet.
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
