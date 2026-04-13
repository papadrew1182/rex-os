import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build-time release identity.
// Vercel provides VERCEL_GIT_COMMIT_SHA, Railway provides
// RAILWAY_GIT_COMMIT_SHA, GitHub Actions provides GITHUB_SHA. Any is fine —
// they all uniquely identify the committed state being built. Falls back to
// ``dev`` so a local `vite dev` still works.
const GIT_SHA =
  process.env.REX_RELEASE ||
  process.env.VERCEL_GIT_COMMIT_SHA ||
  process.env.RAILWAY_GIT_COMMIT_SHA ||
  process.env.GITHUB_SHA ||
  'dev'
const BUILD_TIME = new Date().toISOString()

export default defineConfig({
  plugins: [react()],
  define: {
    __REX_GIT_SHA__: JSON.stringify(GIT_SHA),
    __REX_BUILD_TIME__: JSON.stringify(BUILD_TIME),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
