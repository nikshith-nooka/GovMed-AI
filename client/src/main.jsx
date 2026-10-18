import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { Chart } from 'chart.js'
import App from './App.jsx'

// Charts use the same system font as the interface.
Chart.defaults.font.family = getComputedStyle(document.documentElement).getPropertyValue('--font-main') || 'system-ui'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
