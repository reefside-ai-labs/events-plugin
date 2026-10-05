import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const proxy = {
    '/jellyfin': {
      target: env.JELLYFIN_SERVER_URL || 'http://127.0.0.1:8097',
      changeOrigin: true,
      rewrite: (path: string) => path.replace(/^\/jellyfin/, ''),
    },
  }
  return {
    server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
  }
})
