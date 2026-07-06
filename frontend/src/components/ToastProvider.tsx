import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { Alert, Snackbar } from '@mui/material'

type Severity = 'error' | 'success' | 'info' | 'warning'

interface ToastApi {
  showToast: (message: string, severity?: Severity) => void
  /** Shorthand for surfacing a failed action (the common case). */
  error: (message: string) => void
}

// Defaults to a no-op so components can call useToast() without a provider
// (e.g. in isolation tests); the real app wraps them in <ToastProvider>.
const ToastContext = createContext<ToastApi>({
  showToast: () => {},
  error: () => {},
})

export function useToast(): ToastApi {
  return useContext(ToastContext)
}

/**
 * App-wide, non-blocking treatment for *action* failures — a liking or
 * commenting request that fails while the surrounding page is fine. Surfaces a
 * transient Snackbar instead of tearing down the view, so the user can retry.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [toast, setToast] = useState<{ message: string; severity: Severity } | null>(null)

  const showToast = useCallback((message: string, severity: Severity = 'info') => {
    setToast({ message, severity })
    setOpen(true)
  }, [])

  const api = useMemo<ToastApi>(
    () => ({ showToast, error: (message: string) => showToast(message, 'error') }),
    [showToast],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <Snackbar
        open={open}
        autoHideDuration={6000}
        onClose={(_, reason) => {
          if (reason !== 'clickaway') setOpen(false)
        }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        {toast ? (
          <Alert
            severity={toast.severity}
            variant="filled"
            onClose={() => setOpen(false)}
            sx={{ width: '100%' }}
          >
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </ToastContext.Provider>
  )
}
