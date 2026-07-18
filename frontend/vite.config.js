import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import {fileURLToPath, URL} from "node:url";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }

          if (id.includes('@lobehub/icons')) {
            return 'vendor-icons'
          }

          if (id.includes('react-router-dom') || id.includes('@remix-run/router')) {
            return 'vendor-router'
          }

          if (id.includes('i18next') || id.includes('react-i18next')) {
            return 'vendor-i18n'
          }

          if (id.includes('react') || id.includes('react-dom')) {
            return 'vendor-react'
          }

          return 'vendor'
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:9797',
        changeOrigin: false,
        xfwd: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
    }
  },
})
