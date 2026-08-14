import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
  // After vitest was added (upgrading Rollup internally), Rollup became strict
  // about resolving the `scheduler` package imported by @fluentui/react-context-selector.
  // Pre-bundling it with esbuild ensures it is available in the dep cache.
  optimizeDeps: {
    include: ['scheduler'],
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:7071',
        changeOrigin: true,
      },
    },
  },
});
