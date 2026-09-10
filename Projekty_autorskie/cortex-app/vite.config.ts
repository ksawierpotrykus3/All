// ============================================================================
// CORTEX — vite config dla czystego renderera (web dev / localhost)
// Używany przez `npm run dev:renderer`. Electron używa electron.vite.config.ts.
// ============================================================================

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  root: __dirname,
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
  build: {
    rollupOptions: {
      input: {
        renderer: path.join(__dirname, 'index.html'),
      },
      output: {
        format: 'es',
      },
    },
    modulePreload: false,
    cssCodeSplit: false,
  },
  plugins: [
    react(),
    tailwindcss(),
  ],
})