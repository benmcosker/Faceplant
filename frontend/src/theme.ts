import { createTheme } from '@mui/material/styles'

// Brand palette lifted straight from the Faceplant logo (public/logo.svg):
//   • INK    — the "faceplant" wordmark            → primary (chrome + text)
//   • SIGNAL — the red mark tile & trailing period → secondary (accent)
//   • CREAM  — the mark's face + the page ground   → background
// "Feed Static": newsprint-flat ground, ink chrome, one electric signal accent.
const INK = '#1f2933'
const SIGNAL = '#ff3b30'
const CREAM = '#f4f3ef'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: INK, light: '#3e4c59', dark: '#0f1419' },
    secondary: { main: SIGNAL, light: '#ff6a62', dark: '#c62a22', contrastText: '#ffffff' },
    background: { default: CREAM, paper: '#ffffff' },
    text: { primary: INK, secondary: '#616e7c' },
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
        root: { border: '1px solid #e2e0d8' },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { backgroundColor: INK, backgroundImage: 'none' },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
    },
  },
})

export default theme
