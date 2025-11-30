// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 凡是 /api 开头的请求，全部转发给 Python 后端
      '/api': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
        secure: false,
      },
      // 图片和报告的静态资源也需要转发
      '/files': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
      '/reports': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      }
    }
  }
})