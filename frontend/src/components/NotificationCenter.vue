<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 알림센터 — 헤더 벨 아이콘(미확인 배지) + 드롭다운 패널. 승인 대기 건은 여기서 즉시 승인하거나
          모달 검토로 넘긴다 (HITL 진입점)
변경 이력:
  - 2026-07-07: 단계 8 알림 시스템 최초 작성
-->
<script setup lang="ts">
import type { NotificationCenterState } from "../composables/useNotifications";

const props = defineProps<{
  center: NotificationCenterState;
}>();

/**
 * 알림 항목의 시각 문자열에서 시:분:초만 잘라 표시한다.
 *
 * @param ts "YYYY-MM-DD HH:MM:SS" 형태의 이벤트 시각
 * @return "HH:MM:SS" 부분 문자열
 */
function timeOf(ts: string): string {
  return ts.length >= 19 ? ts.slice(11, 19) : ts;
}

/**
 * 해당 알림에 아직 응답하지 않은 승인 건이 연결되어 있는지 확인한다.
 *
 * @param actionId 알림에 연결된 action_id (없으면 null)
 * @return 승인 대기(PENDING) 상태면 true
 */
function isPendingApproval(actionId: string | null): boolean {
  if (actionId === null) return false;
  return props.center.approvals.value.some(
    (approval) => approval.actionId === actionId && approval.status === "PENDING",
  );
}
</script>

<template>
  <div class="noti-root">
    <button
      class="bell"
      :class="{ 'bell--open': center.panelOpen.value }"
      aria-label="알림센터 열기"
      @click="center.togglePanel()"
    >
      <svg viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true">
        <path
          d="M12 3a6 6 0 0 0-6 6v3.2l-1.6 3A1 1 0 0 0 5.3 16.7h13.4a1 1 0 0 0 .9-1.5L18 12.2V9a6 6 0 0 0-6-6Z"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linejoin="round"
        />
        <path d="M9.8 19.5a2.3 2.3 0 0 0 4.4 0" stroke="currentColor" stroke-width="1.7" />
      </svg>
      <span v-if="center.unreadCount.value > 0" class="badge">
        {{ center.unreadCount.value > 99 ? "99+" : center.unreadCount.value }}
      </span>
    </button>

    <Transition name="drop">
      <section v-if="center.panelOpen.value" class="panel" aria-label="알림 목록">
        <header class="panel-top">
          <h3>알림</h3>
          <span v-if="center.pendingApprovalCount.value > 0" class="chip--warn chip">
            승인 대기 {{ center.pendingApprovalCount.value }}
          </span>
          <button class="close" aria-label="알림센터 닫기" @click="center.closePanel()">✕</button>
        </header>

        <p v-if="center.items.value.length === 0" class="empty">
          아직 알림이 없습니다. 실행을 시작하면 경고·승인 요청이 여기에 쌓입니다.
        </p>

        <ol v-else class="list">
          <li
            v-for="item in center.items.value"
            :key="item.id"
            class="item"
            :data-severity="item.severity"
          >
            <span class="item-dot" aria-hidden="true"></span>
            <div class="item-body">
              <div class="item-line">
                <span class="item-title">{{ item.title }}</span>
                <time class="item-ts">{{ timeOf(item.ts) }}</time>
              </div>
              <p class="item-detail">{{ item.detail }}</p>
              <div v-if="isPendingApproval(item.actionId)" class="item-actions">
                <button
                  class="btn btn--sm"
                  @click="item.actionId !== null && center.acceptAction(item.actionId)"
                >
                  승인
                </button>
                <button
                  class="btn btn--ghost btn--sm"
                  @click="item.actionId !== null && center.openApprovalModal(item.actionId)"
                >
                  검토
                </button>
              </div>
            </div>
          </li>
        </ol>
      </section>
    </Transition>
  </div>
</template>

<style scoped>
.noti-root {
  position: relative;
}
.bell {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--bg-raised);
  color: var(--ink-sub);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.bell:hover,
.bell--open {
  color: var(--accent);
  border-color: var(--accent-dim);
}
.badge {
  position: absolute;
  top: -0.4rem;
  right: -0.4rem;
  min-width: 1.1rem;
  padding: 0.05rem 0.28rem;
  border-radius: 999px;
  background: var(--status-critical);
  color: #fff;
  font-size: 0.62rem;
  font-weight: 750;
  font-family: var(--font-mono);
  text-align: center;
  box-shadow: 0 0 0 2px var(--bg-page);
}

.panel {
  position: absolute;
  top: calc(100% + 0.6rem);
  right: 0;
  z-index: 50;
  width: min(24rem, calc(100vw - 2rem));
  max-height: min(30rem, 70vh);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  background: var(--bg-panel);
  box-shadow: var(--shadow-float);
  overflow: hidden;
}
.panel-top {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.7rem 0.9rem;
  border-bottom: 1px solid var(--border);
}
.panel-top h3 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 700;
}
.close {
  margin-left: auto;
  padding: 0.15rem 0.35rem;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--ink-dim);
  font-size: 0.72rem;
  cursor: pointer;
}
.close:hover {
  color: var(--ink);
  background: var(--bg-hover);
}
.empty {
  margin: 0;
  padding: 1.4rem 1rem;
  font-size: 0.78rem;
  color: var(--ink-dim);
  text-align: center;
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-y: auto;
}
.item {
  display: flex;
  gap: 0.6rem;
  padding: 0.65rem 0.9rem;
}
.item + .item {
  border-top: 1px solid var(--border);
}
.item-dot {
  flex: none;
  width: 7px;
  height: 7px;
  margin-top: 0.42rem;
  border-radius: 50%;
  background: var(--accent);
}
.item[data-severity="warning"] .item-dot {
  background: var(--status-warning);
}
.item[data-severity="critical"] .item-dot {
  background: var(--status-critical-strong);
}
.item-body {
  flex: 1;
  min-width: 0;
}
.item-line {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}
.item-title {
  flex: 1;
  min-width: 0;
  font-size: 0.79rem;
  font-weight: 650;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-ts {
  flex: none;
  font-size: 0.68rem;
  color: var(--ink-dim);
  font-family: var(--font-mono);
}
.item-detail {
  margin: 0.15rem 0 0;
  font-size: 0.74rem;
  line-height: 1.45;
  color: var(--ink-sub);
  word-break: break-word;
}
.item-actions {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.drop-enter-active,
.drop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-0.4rem);
}
@media (prefers-reduced-motion: reduce) {
  .drop-enter-active,
  .drop-leave-active {
    transition: none;
  }
}
</style>
