import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    host: true, // listen on 0.0.0.0 so the Vite dev server is reachable from outside its Docker container
    port: 5173,
    strictPort: true,
  },
})