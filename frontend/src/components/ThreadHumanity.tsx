import { Chip, Tooltip } from '@mui/material'
import PersonOutlineIcon from '@mui/icons-material/PersonOutlined'
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined'

interface Props {
  share: number // 0..1, human_messages / total_messages
  human: number
  total: number
}

type Tone = 'success' | 'warning' | 'error'

/** Color ramps down as the humans get drowned out: green → amber → red. */
function tone(share: number): Tone {
  if (share >= 0.5) return 'success'
  if (share >= 0.15) return 'warning'
  return 'error'
}

/**
 * The "% human in this thread" counter — the dead-internet gut-punch. Measured
 * by message (post + comments), so a lone human post buried under a bot swarm
 * craters toward 0%. At exactly 0% humans it flips to a "dead internet" label.
 */
export default function ThreadHumanity({ share, human, total }: Props) {
  const pct = Math.round(share * 100)
  const dead = human === 0
  const label = dead ? 'dead internet' : `${pct}% human`
  const color: Tone = dead ? 'error' : tone(share)

  return (
    <Tooltip title={`${human} of ${total} ${total === 1 ? 'message' : 'messages'} in this thread ${human === 1 ? 'is' : 'are'} human`}>
      <Chip
        size="small"
        variant="outlined"
        color={color}
        icon={dead ? <SmartToyOutlinedIcon /> : <PersonOutlineIcon />}
        label={label}
        aria-label={`thread is ${dead ? 'dead internet, no humans' : `${pct} percent human`}`}
        sx={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}
      />
    </Tooltip>
  )
}
