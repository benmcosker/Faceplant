import { IconButton, Tooltip } from '@mui/material'
import DarkModeIcon from '@mui/icons-material/DarkModeOutlined'
import LightModeIcon from '@mui/icons-material/LightModeOutlined'
import { useColorMode } from '../colorMode'

/** Sun/moon toggle for light/dark mode. Shows the icon of the mode you'd switch
 *  *to*, which is the convention users expect. */
export default function ThemeToggle() {
  const { mode, toggle } = useColorMode()
  const toLabel = mode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'
  return (
    <Tooltip title={toLabel}>
      <IconButton color="inherit" onClick={toggle} aria-label={toLabel}>
        {mode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
      </IconButton>
    </Tooltip>
  )
}
