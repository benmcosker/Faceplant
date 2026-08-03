import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { createAppTheme, type ColorMode } from './theme'

const STORAGE_KEY = 'faceplant-color-mode'

interface ColorModeContextValue {
  mode: ColorMode
  toggle: () => void
}

const ColorModeContext = createContext<ColorModeContextValue | null>(null)

/** First-load mode: a previously saved choice wins; otherwise follow the OS
 *  `prefers-color-scheme`; otherwise light. Read synchronously so there's no
 *  flash of the wrong theme on mount. */
export function getInitialMode(): ColorMode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') return saved
    if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark'
  } catch {
    // localStorage / matchMedia unavailable (SSR, privacy mode) — fall through.
  }
  return 'light'
}

/** Wraps the app in a MUI ThemeProvider whose theme tracks a light/dark mode the
 *  user can toggle. The choice is persisted to localStorage. */
export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ColorMode>(getInitialMode)

  const toggle = useCallback(() => {
    setMode((prev) => {
      const next: ColorMode = prev === 'light' ? 'dark' : 'light'
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        // Persisting is best-effort; the in-memory toggle still works without it.
      }
      return next
    })
  }, [])

  const theme = useMemo(() => createAppTheme(mode), [mode])
  const value = useMemo(() => ({ mode, toggle }), [mode, toggle])

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  )
}

export function useColorMode(): ColorModeContextValue {
  const ctx = useContext(ColorModeContext)
  if (!ctx) throw new Error('useColorMode must be used within a ColorModeProvider')
  return ctx
}
