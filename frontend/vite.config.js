import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }
  },
  // Where the built app will be served from. Defaults to the site root; set
  // VITE_BASE=/v2/ to build a copy that lives under a sub-path. Vite bakes this
  // into every asset URL and exposes it as import.meta.env.BASE_URL, which the
  // router and the API client read — so one variable moves all three.
  base: process.env.VITE_BASE ?? '/',

  build: {
    outDir: '../api/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8765',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ''),
      }
    }
  }
})
