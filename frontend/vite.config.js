import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/",
  build: {
    outDir: "dist",
    // 沙箱/回收站环境删除 dist 受限，关闭自动清空（新文件覆盖写；旧 assets 无害残留）
    emptyOutDir: false,
  },
  server: {
    port: 5173,
    proxy: {
      // 本地开发：/api 转发到后端（docker compose 后同源，无需代理）
      "/api": "http://localhost:8090",
    },
  },
});
