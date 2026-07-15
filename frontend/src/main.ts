/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: Vue 앱 엔트리 — 전역 스타일 모듈(tokens/ui/base) 로드 후 App 마운트
 * 변경 이력:
 *   - 2026-07-07: 단계 8 최초 작성
 */
import { createApp } from "vue";

import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/ui.css";
import App from "./App.vue";

createApp(App).mount("#app");
