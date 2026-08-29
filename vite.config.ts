import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
