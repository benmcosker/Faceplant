import { useEffect, useState } from 'react'
import { Box, CircularProgress } from '@mui/material'
import { fetchMe, logout, type User } from './api'
import AppShell from './components/AppShell'
import IdentityGate from './components/IdentityGate'
import Feed from './components/Feed'
import { ToastProvider } from './components/ToastProvider'

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .finally(() => setChecking(false))
  }, [])

  async function handleLogout() {
    await logout()
    setUser(null)
  }

  return (
    <ToastProvider>
      <AppShell username={user?.username ?? null} onSwitchUser={handleLogout}>
        {checking ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : user ? (
          <Feed />
        ) : (
          <IdentityGate onIdentityResolved={setUser} />
        )}
      </AppShell>
    </ToastProvider>
  )
}

export default App
