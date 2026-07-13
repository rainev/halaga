import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    host: true, // listen on 0.0.0.0 so the container is reachable
    port: 5173,
    watch: {
      usePolling: true, // reliable file-watching across the Docker bind mount
    },
  },
})
