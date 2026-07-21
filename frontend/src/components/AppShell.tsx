import type { ReactNode } from 'react'
import { AppBar, Box, Button, Toolbar, Typography } from '@mui/material'
import LogoutIcon from '@mui/icons-material/Logout'
import CostMeter from './CostMeter'

interface Props {
  username: string | null
  onSwitchUser: () => void
  children: ReactNode
}

/** App chrome: top bar (title + current user + switch-user) wrapping page content. */
export default function AppShell({ username, onSwitchUser, children }: Props) {
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static">
        <Toolbar sx={{ gap: 1 }}>
          <Box
            component="img"
            src="/logo-mark.svg"
            alt=""
            sx={{ width: 30, height: 30, display: 'block' }}
          />
          <Typography variant="h6" sx={{ fontWeight: 800, flexGrow: 1 }}>
            faceplant
          </Typography>

          {username && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CostMeter />
              <Typography>{username}</Typography>
              <Button color="inherit" startIcon={<LogoutIcon />} onClick={onSwitchUser}>
                Log out
              </Button>
            </Box>
          )}
        </Toolbar>
      </AppBar>

      <Box component="main">{children}</Box>
    </Box>
  )
}
