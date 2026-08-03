import { Box } from '@mui/material'

interface Props {
  /** Theme color token or CSS color for the dot. Defaults to the signal red. */
  color?: string
  /** Diameter in px. */
  size?: number
}

/**
 * A small "live" indicator dot with a soft pulse — the shared motif that marks
 * the surfaces where the machine is actively watching or spending in real time
 * (The Meter, the targeted ad). Purely decorative, and it holds still for anyone
 * who's asked their OS to reduce motion.
 */
export default function PulseDot({ color = 'secondary.main', size = 7 }: Props) {
  return (
    <Box
      component="span"
      aria-hidden
      sx={{
        width: size,
        height: size,
        borderRadius: '50%',
        bgcolor: color,
        display: 'inline-block',
        flexShrink: 0,
        '@keyframes faceplantPulse': {
          '0%, 100%': { opacity: 1, transform: 'scale(1)' },
          '50%': { opacity: 0.3, transform: 'scale(0.7)' },
        },
        animation: 'faceplantPulse 1.6s ease-in-out infinite',
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }}
    />
  )
}
