import { Alert, AlertTitle, Button } from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'

interface Props {
  message: string
  /** When provided, shows a "Try again" action that re-runs the failed request. */
  onRetry?: () => void
  title?: string
  /** Drops the title for tight spots like a comment thread. */
  compact?: boolean
}

/**
 * Inline treatment for a *load* failure — used where content can't be shown at
 * all (a feed that won't load, a comment thread that won't fetch). Pairs the
 * message with a retry action so the failure is recoverable in place.
 */
export default function ErrorState({ message, onRetry, title = 'Something went wrong', compact }: Props) {
  return (
    <Alert
      severity="error"
      role="alert"
      action={
        onRetry ? (
          <Button color="inherit" size="small" startIcon={<RefreshIcon />} onClick={onRetry}>
            Try again
          </Button>
        ) : undefined
      }
    >
      {!compact && <AlertTitle>{title}</AlertTitle>}
      {message}
    </Alert>
  )
}
