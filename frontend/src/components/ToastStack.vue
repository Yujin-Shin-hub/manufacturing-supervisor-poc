<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 우측 하단 토스트 스택 — 알림 심각도별 스타일, critical은 수동 닫기 전까지 유지
변경 이력:
  - 2026-07-07: 단계 8 알림 시스템 최초 작성
-->
<script setup lang="ts">
import type { ToastItem } from "../types/notifications";

defineProps<{
  toasts: ToastItem[];
}>();

const emit = defineEmits<{
  dismiss: [toastId: number];
}>();
</script>

<template>
  <div class="toast-stack" aria-live="polite">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast"
        :data-severity="toast.severity"
        role="status"
      >
        <span class="toast-dot" aria-hidden="true"></span>
        <div class="toast-body">
          <p class="toast-title">{{ toast.title }}</p>
          <p v-if="toast.detail" class="toast-detail">{{ toast.detail }}</p>
        </div>
        <button class="toast-close" aria-label="알림 닫기" @click="emit('dismiss', toast.id)">
          ✕
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  right: 1.25rem;
  bottom: 1.25rem;
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  width: min(22rem, calc(100vw - 2.5rem));
}
.toast {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--border-strong);
  border-left: 3px solid var(--accent);
  border-radius: 10px;
  background: var(--bg-raised);
  box-shadow: var(--shadow-float);
}
.toast[data-severity="warning"] {
  border-left-color: var(--status-warning);
}
.toast[data-severity="critical"] {
  border-left-color: var(--status-critical);
}
.toast-dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 0.35rem;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent-glow);
}
.toast[data-severity="warning"] .toast-dot {
  background: var(--status-warning);
  box-shadow: 0 0 8px rgba(250, 178, 25, 0.5);
}
.toast[data-severity="critical"] .toast-dot {
  background: var(--status-critical-strong);
  box-shadow: 0 0 8px rgba(208, 59, 59, 0.6);
}
.toast-body {
  flex: 1;
  min-width: 0;
}
.toast-title {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 650;
  color: var(--ink);
}
.toast-detail {
  margin: 0.2rem 0 0;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--ink-sub);
  word-break: break-word;
}
.toast-close {
  flex: none;
  padding: 0.1rem 0.3rem;
  border: none;
  background: transparent;
  color: var(--ink-dim);
  font-size: 0.75rem;
  cursor: pointer;
  border-radius: 4px;
}
.toast-close:hover {
  color: var(--ink);
  background: var(--bg-hover);
}

.toast-enter-active,
.toast-leave-active,
.toast-move {
  transition: all 0.25s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(0.8rem);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(0.8rem);
}
@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active,
  .toast-move {
    transition: none;
  }
}
</style>
