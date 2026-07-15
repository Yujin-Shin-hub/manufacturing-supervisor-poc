<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 최종 리포트 드로어 — run_end의 report_markdown을 우측 슬라이드 패널로 크게 보여준다
          (marked 렌더링, 완료 시 자동 오픈·헤더 버튼으로 재오픈)
변경 이력:
  - 2026-07-07: 단계 8 대시보드 재설계 2차 — ReportPanel(그리드 패널)을 드로어로 대체
  - 2026-07-14: 리포트 A안 — key_actions가 있으면 markdown의 핵심 추천 액션 절
                (key_actions 마커 구간)을 KeyActionsPanel 고정 컴포넌트로 대체 렌더링
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";
import { marked } from "marked";

import type { KeyActionData } from "../types/events";
import KeyActionsPanel from "./KeyActionsPanel.vue";

const props = defineProps<{
  open: boolean;
  reportMarkdown: string | null;
  keyActions: KeyActionData[];
  keyActionsTotal: number;
}>();

const emit = defineEmits<{
  close: [];
}>();

/** report.py가 핵심 추천 액션 절을 감싸는 마커 (api-spec 2-1 run_end 규칙) */
const KEY_ACTIONS_BLOCK = /<!-- key_actions:start -->[\s\S]*?<!-- key_actions:end -->/;

/**
 * markdown을 핵심 추천 액션 마커 기준으로 앞/뒤 두 조각으로 나눈다.
 * key_actions 구조화 데이터가 있을 때만 절을 도려내고, 없으면 markdown 표를 그대로 둔다.
 */
const parts = computed<{ before: string; after: string; replaced: boolean }>(() => {
  const markdown = props.reportMarkdown ?? "";
  if (props.keyActions.length === 0) return { before: markdown, after: "", replaced: false };
  const match = markdown.match(KEY_ACTIONS_BLOCK);
  if (match === null || match.index === undefined) {
    return { before: markdown, after: "", replaced: false };
  }
  return {
    before: markdown.slice(0, match.index),
    after: markdown.slice(match.index + match[0].length),
    replaced: true,
  };
});

const htmlBefore = computed<string>(() =>
  parts.value.before === "" ? "" : (marked.parse(parts.value.before) as string),
);
const htmlAfter = computed<string>(() =>
  parts.value.after === "" ? "" : (marked.parse(parts.value.after) as string),
);

/**
 * Esc 키로 드로어를 닫는다.
 *
 * @param keyEvent 전역 keydown 이벤트
 */
function onKeydown(keyEvent: KeyboardEvent): void {
  if (keyEvent.key === "Escape" && props.open) emit("close");
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="drawer-root">
      <div class="drawer-backdrop" @click="emit('close')"></div>
      <aside class="drawer" role="dialog" aria-label="최종 리포트">
        <header class="drawer-head">
          <h2 class="drawer-title">최종 리포트</h2>
          <span v-if="reportMarkdown !== null" class="chip" data-status="DONE">생성됨</span>
          <button class="btn btn--ghost btn--sm close-btn" @click="emit('close')">닫기 (Esc)</button>
        </header>

        <p v-if="reportMarkdown === null" class="empty">
          아직 생성된 리포트가 없습니다. 실행이 완료되면 리스크 TOP·설비 후보·재조정 액션 표가
          포함된 리포트가 여기에 표시됩니다.
        </p>
        <!-- report_markdown은 코드(EventBus)가 발행한 서버 생성 콘텐츠만 렌더링한다 -->
        <div v-else class="report-body">
          <div v-if="htmlBefore" class="report-markdown" v-html="htmlBefore"></div>
          <KeyActionsPanel
            v-if="parts.replaced"
            :actions="keyActions"
            :total="keyActionsTotal"
          />
          <div v-if="htmlAfter" class="report-markdown" v-html="htmlAfter"></div>
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.drawer-root {
  position: fixed;
  inset: 0;
  z-index: 58;
}
.drawer-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(4, 8, 15, 0.55);
}
.drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(42rem, 94vw);
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border-strong);
  background: var(--bg-panel);
  box-shadow: var(--shadow-float);
}
.drawer-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.85rem 1.2rem;
  border-bottom: 1px solid var(--border);
  flex: none;
}
.drawer-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
}
.drawer-title::before {
  content: "";
  display: inline-block;
  width: 3px;
  height: 0.9em;
  margin-right: 0.55rem;
  vertical-align: -0.08em;
  border-radius: 2px;
  background: var(--accent);
}
.close-btn {
  margin-left: auto;
}
.empty {
  margin: 0;
  padding: 1.4rem 1.2rem;
  color: var(--ink-dim);
  font-size: 0.8rem;
  line-height: 1.5;
}
.report-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.1rem 1.4rem 1.4rem;
  font-size: 0.86rem;
  line-height: 1.65;
  color: var(--ink-sub);
}
.report-body :deep(h1),
.report-body :deep(h2),
.report-body :deep(h3) {
  margin: 1em 0 0.45em;
  line-height: 1.3;
  color: var(--ink);
}
.report-body :deep(h1:first-child),
.report-body :deep(h2:first-child) {
  margin-top: 0;
}
.report-body :deep(strong) {
  color: var(--ink);
}
.report-body :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 0.6em 0;
  font-size: 0.79rem;
  font-variant-numeric: tabular-nums;
}
.report-body :deep(th),
.report-body :deep(td) {
  border: 1px solid var(--border-strong);
  padding: 0.32em 0.65em;
  text-align: left;
}
.report-body :deep(th) {
  background: var(--bg-raised);
  color: var(--ink);
  font-weight: 650;
}
.report-body :deep(tbody tr:nth-child(even)) {
  background: rgba(255, 255, 255, 0.02);
}
.report-body :deep(code) {
  background: var(--bg-raised);
  padding: 0.12em 0.35em;
  border-radius: 4px;
  font-size: 0.77rem;
  font-family: var(--font-mono);
  color: var(--accent-strong);
}
.report-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1em 0;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.22s ease;
}
.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 0.22s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(2.5rem);
}
@media (prefers-reduced-motion: reduce) {
  .drawer-enter-active,
  .drawer-leave-active,
  .drawer-enter-active .drawer,
  .drawer-leave-active .drawer {
    transition: none;
  }
}
</style>
