<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 실행 툴바 — mode 세그먼트·asof·query·LLM provider 입력과 실행 버튼 (docs/dashboard.md 화면 구성)
변경 이력:
  - 2026-07-07: 단계 8 최초 작성
  - 2026-07-07: 색상·버튼·칩을 styles/tokens.css·ui.css 공통 모듈로 교체
  - 2026-07-07: 헤더바에서 분리된 툴바로 재구성 — mode 세그먼트 토글, 다크 컨트롤 스타일
-->
<script setup lang="ts">
import type { RunControlState, RunMode } from "../composables/useRunControl";
import type { RunStatus } from "../types/events";

const props = defineProps<{
  control: RunControlState;
  runStatus: RunStatus;
}>();

const MODES: readonly { value: RunMode; label: string }[] = [
  { value: "report", label: "리포트" },
  { value: "ask", label: "질의" },
];

/**
 * 실행 버튼 클릭 시 /run 트리거를 위임한다.
 */
function onRunClick(): void {
  void props.control.startRun();
}
</script>

<template>
  <div class="toolbar">
    <div class="segment" role="group" aria-label="실행 모드">
      <button
        v-for="mode in MODES"
        :key="mode.value"
        type="button"
        :class="{ 'is-active': control.form.mode === mode.value }"
        @click="control.form.mode = mode.value"
      >
        {{ mode.label }}
      </button>
    </div>

    <label class="field">
      <span>기준시각</span>
      <input
        v-model="control.form.asof"
        class="control"
        type="text"
        placeholder="YYYY-MM-DD HH:MM (생략 시 서버 결정)"
        size="22"
      />
    </label>

    <label v-if="control.form.mode === 'ask'" class="field field-query">
      <span>질문</span>
      <input
        v-model="control.form.query"
        class="control"
        type="text"
        placeholder="예: 지금 어느 공정이 제일 위험해?"
      />
    </label>

    <label class="field">
      <span>LLM</span>
      <select v-model="control.form.llm_provider" class="control">
        <option value="auto">auto</option>
        <option value="qwen">qwen</option>
        <option value="openai">openai</option>
      </select>
    </label>

    <button
      class="btn run-btn"
      :disabled="control.submitting.value || runStatus === 'RUNNING'"
      @click="onRunClick"
    >
      <svg v-if="runStatus !== 'RUNNING'" viewBox="0 0 12 12" width="10" height="10" aria-hidden="true">
        <path d="M2.5 1.5v9l8-4.5z" fill="currentColor" />
      </svg>
      {{ runStatus === "RUNNING" ? "실행 중…" : "실행" }}
    </button>

    <p v-if="control.errorMessage.value" class="error-message" role="alert">
      {{ control.errorMessage.value }}
    </p>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.7rem;
  padding: 0.55rem 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg-panel);
}
.field {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.75rem;
  color: var(--ink-dim);
  white-space: nowrap;
}
.field-query {
  flex: 1 1 16rem;
}
.field-query .control {
  width: 100%;
}
.run-btn {
  margin-left: auto;
}
.error-message {
  flex-basis: 100%;
  margin: 0;
  font-size: 0.76rem;
  color: var(--status-critical-strong);
}
@media (max-width: 900px) {
  .run-btn {
    margin-left: 0;
  }
}
</style>
