import { createTheme, type Theme } from '@mui/material/styles'

// Brand palette lifted straight from the Faceplant logo (public/logo.svg):
//   • INK    — the "faceplant" wordmark            → chrome + text
//   • SIGNAL — the red mark tile & trailing period → accent (secondary)
//   • CREAM  — the mark's face + the page ground   → light-mode background
// "Feed Static": newsprint-flat ground, ink chrome, one electric signal accent.
const INK = '#1f2933'
const SIGNAL = '#ff3b30'
const CREAM = '#f4f3ef'

// Dark mode keeps the same bones — ink chrome, signal accent — but inverts the
// ground: a deeper-than-ink near-black page so the INK app bar still reads as
// chrome, with ink used as the raised card surface and cream flipped to text.
const NIGHT = '#14181d' // page ground, darker than INK so the bar stands off it
const NIGHT_PAPER = '#1f2933' // = INK, the raised surface
const NIGHT_TEXT = '#e6e8ea'

export type ColorMode = 'light' | 'dark'

/** Build the MUI theme for a color mode. Same design tokens (shape, type,
 *  component defaults) in both; only the palette and a couple of mode-dependent
 *  surface colors change, so the app's identity survives the flip. */
export function createAppTheme(mode: ColorMode): Theme {
  const isDark = mode === 'dark'

  const cardBorder = isDark ? '#2b333c' : '#e2e0d8'
  // Light: ink chrome. Dark: still ink, but now visibly raised off the darker ground.
  const appBarBg = INK

  return createTheme({
    palette: {
      mode,
      primary: isDark
        ? { main: '#cbd2d9', light: '#e4e7eb', dark: '#9aa5b1' }
        : { main: INK, light: '#3e4c59', dark: '#0f1419' },
      secondary: { main: SIGNAL, light: '#ff6a62', dark: '#c62a22', contrastText: '#ffffff' },
      background: isDark
        ? { default: NIGHT, paper: NIGHT_PAPER }
        : { default: CREAM, paper: '#ffffff' },
      text: isDark
        ? { primary: NIGHT_TEXT, secondary: '#9aa5b1' }
        : { primary: INK, secondary: '#616e7c' },
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      h4: { fontWeight: 800 },
      h6: { fontWeight: 700 },
    },
    components: {
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: { border: `1px solid ${cardBorder}` },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: { backgroundColor: appBarBg, backgroundImage: 'none' },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
      },
    },
  })
}

// The default (light) theme, kept as a named export so any code that imported the
// old static `theme` keeps working.
const theme = createAppTheme('light')
export default theme
