/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: Vite 설정 — dev 서버(5173)에서 /run·/events·/api·/health를 FastAPI(8000)로 proxy
 * 변경 이력:
 *   - 2026-07-07: 단계 8 최초 작성 (docs/api-spec.md 0장 proxy 계약)
 */
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const BACKEND_ORIGIN = "http://localhost:8000";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/run": BACKEND_ORIGIN,
      "/events": BACKEND_ORIGIN,
      "/api": BACKEND_ORIGIN,
      "/health": BACKEND_ORIGIN,
    },
  },
});
