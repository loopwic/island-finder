import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import stylex from '@stylexjs/unplugin/vite';

export default defineConfig({
  plugins: [
    stylex({
      classNamePrefix: 'island',
      debug: false,
      cssInjectionTarget: (fileName) => /(?:^|\/)index(?:-[^/]+)?\.css$/.test(fileName),
      useCSSLayers: { after: ['astryx-theme'], before: ['reset', 'astryx-base'], prefix: 'stylex' },
    }),
    react(),
  ],
  build: {
    outDir: 'apps/web/dist',
    emptyOutDir: true,
  },
  server: {
    port: 4173,
    strictPort: true,
    hmr: true,
    watch: {
      // The Python environment contains thousands of files and is unrelated to
      // the browser bundle. Watching it made an idle dev server continuously
      // stat files on macOS.
      ignored: [
        '**/.venv/**',
        '**/__pycache__/**',
        '**/.pytest_cache/**',
        '**/dist/**',
        '**/native/**',
      ],
    },
  },
});
