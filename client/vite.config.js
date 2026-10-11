import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // README runs the API on 8000; set GOVBENCH_API_URL to point elsewhere (e.g. http://localhost:8001).
        target: process.env.GOVBENCH_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
