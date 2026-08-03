import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { ColorModeProvider } from './colorMode'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ColorModeProvider>
      <App />
    </ColorModeProvider>
  </StrictMode>,
)
