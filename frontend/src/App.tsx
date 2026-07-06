import { useState } from 'react'
import { clearIdentity, getIdentity } from './api'
import AppShell from './components/AppShell'
import IdentityGate from './components/IdentityGate'
import Feed from './components/Feed'
import { ToastProvider } from './components/ToastProvider'

function App() {
  const [username, setUsername] = useState<string | null>(getIdentity())

  function handleSwitchUser() {
    clearIdentity()
    setUsername(null)
  }

  return (
    <ToastProvider>
      <AppShell username={username} onSwitchUser={handleSwitchUser}>
        {username ? <Feed username={username} /> : <IdentityGate onIdentityResolved={setUsername} />}
      </AppShell>
    </ToastProvider>
  )
}

export default App
