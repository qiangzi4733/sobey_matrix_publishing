import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 源码经 VirtIOFS 共享，文件事件不可靠，改用轮询
    watch: { usePolling: true, interval: 500 },
    proxy: {
      '/api': process.env.API_PROXY_TARGET || 'http://localhost:8000',
    },
  },
})
