// Vite 配置：React 插件 + 开发服务器代理
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],           // 启用 React JSX 支持
  server: {
    host: "127.0.0.1",          // 明确监听 IPv4，避免 localhost 解析到 ::1 导致连不上
    port: 5173,                 // 前端开发端口
    proxy: {
      "/api": "http://127.0.0.1:8000",  // 将 /api 请求转发到后端
    },
  },
});
