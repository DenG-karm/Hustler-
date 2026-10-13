import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './theme/ThemeContext'
import { installNetworkSecurityTrap } from './lib/securityGuard'

// K-709: Sıfır Ağ İzolasyonu ve CSP Güvenlik Kalkanını Başlat
installNetworkSecurityTrap()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="system">
      <App />
    </ThemeProvider>
  </StrictMode>,
)
