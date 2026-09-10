// ============================================================================
// CORTEX — electron-vite configuration: 3 targets (main, preload, renderer)
// Zastępuje stary scripts/build.ts + vite.config.ts
// ============================================================================

import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  main: {
    build: {
      rollupOptions: {
        input: {
          index: path.join(__dirname, 'src/main/index.ts'),
        },
        output: {
          format: 'cjs',
          entryFileNames: 'index.cjs',
        },
      },
    },
    plugins: [externalizeDepsPlugin()],
    resolve: {
      conditions: ['node'],
    },
  },

  preload: {
    build: {
      rollupOptions: {
        input: {
          index: path.join(__dirname, 'src/main/preload.ts'),
        },
        output: {
          format: 'cjs',
          entryFileNames: 'index.cjs',
        },
      },
    },
    plugins: [externalizeDepsPlugin()],
  },

  renderer: {
    root: __dirname,
    build: {
      rollupOptions: {
        input: {
          renderer: path.join(__dirname, 'index.html'),
        },
        output: {
          format: 'es',
        },
      },
      // Don't add crossorigin attribute — Electron loads from file://
      modulePreload: false,
      cssCodeSplit: false,
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    plugins: [
      tailwindcss(),
      react(),
      {
        name: 'remove-crossorigin',
        transformIndexHtml: (html) => html.replace(/\bcrossorigin\b/g, ''),
      },
    ],
    server: {
      port: 3000,
    },
  },
})
