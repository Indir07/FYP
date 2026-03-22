import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev UI + /api share one origin → browser calls `/api/...` only (see src/lib/apiBase.ts).
    // Backend CORS still lists 5173–5176 for any direct :8000 calls (tools, misconfig).
    // `strictPort` not set: if 5173 is busy Vite tries 5174, 5175, …
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_PROXY ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
