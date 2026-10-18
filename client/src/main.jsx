import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { Chart } from 'chart.js'
import App from './App.jsx'

// Charts use the interface's system font and neutral greys that read on light and dark surfaces.
Chart.defaults.font.family = getComputedStyle(document.documentElement).getPropertyValue('--font-main') || 'system-ui'
Chart.defaults.color = '#8E8E93'
Chart.defaults.borderColor = 'rgba(142, 142, 147, 0.2)'
Chart.defaults.plugins.legend.labels.boxWidth = 12
Chart.defaults.plugins.legend.labels.boxHeight = 12
Chart.defaults.datasets.bar.borderRadius = 4
// Honour the reduced-motion preference: no grow-in animation for charts.
if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) Chart.defaults.animation = false

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
