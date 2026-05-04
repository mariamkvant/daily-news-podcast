import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // In production, VITE_API_URL is set to the backend Railway URL.
  // In dev, proxy /api to localhost:8000.
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/audio': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
