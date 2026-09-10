import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  test: {
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    passWithNoTests: true,
    environment: 'jsdom',
    testTimeout: 60_000,
    hookTimeout: 30_000,
    pool: 'forks',
    css: {
      modules: {
        classNameStrategy: 'non-scoped',
      },
    },
  },
  // Required for React JSX/TSX resolution
  esbuild: {
    jsx: 'automatic',
  },
});
