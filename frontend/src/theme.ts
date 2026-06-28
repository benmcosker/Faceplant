import { createTheme } from '@mui/material/styles'

// "Feed Static" — newsprint-flat background, electric ink accent.
const INK = '#1f2933'
const SIGNAL = '#ff3b30'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: INK, light: '#3e4c59', dark: '#0f1419' },
    secondary: { main: SIGNAL, contrastText: '#ffffff' },
    background: { default: '#f4f3ef', paper: '#ffffff' },
    text: { primary: '#1f2933', secondary: '#616e7c' },
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
