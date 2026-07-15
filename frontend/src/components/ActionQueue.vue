<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 재조정 제안 큐 — "어떤 스케줄을 어느 설비로 옮길지"를 전면에 보여주는 패널.
          행마다 원설비→대체설비 전환 방향과 승인/검토 버튼(HITL)을 배치한다
변경 이력:
  - 2026-07-07: 단계 8 재설계 3차 — 최초 작성
-->
<script setup lang="ts">
import { computed } from "vue";

import type { NotificationCenterState } from "../composables/useNotifications";
import type { ProposalStatus } from "../types/notifications";

const props = defineProps<{
  center: NotificationCenterState;
}>();

const STATUS_LABEL: Record<Exclude<ProposalStatus, "PENDING">, string> = {
  PROPOSED: "승인 불요",
  ACCEPTED: "승인됨",
  REJECTED: "거절됨",
  EXPIRED: "만료",
};

const pendingCount = computed(
  () => props.center.proposals.value.filter((entry) => entry.status === "PENDING").length,
);

/**
 * efficiency_gain을 표시 자릿수 규칙(api-spec 3-1: 비율 2dp)에 맞춰 문자열로 만든다.
 *
 * @param gain 이벤트가 전달한 efficiency_gain (없으면 null)
 * @returns "부하 -0.23" 형태 문자열. 값이 없으면 빈 문자열
 */
function formatGain(gain: number | null): string {
  return gain === null ? "" : `부하 −${gain.toFixed(2)}`;
}

function formatHours(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(1)}h`;
}

function formatRate(value: number | null): string {
  return value === null ? "이력 없음" : `${Math.round(value * 100)}%`;
}
</script>

<template>
  <section class="panel-card action-queue">
    <header class="panel-head">
      <h2 class="panel-label">재조정 제안</h2>
      <div class="panel-meta">
        <span v-if="pendingCount > 0" class="chip chip--warn">승인 대기 {{ pendingCount }}</span>
        <span v-else>{{ center.proposals.value.length }}건</span>
      </div>
    </header>

    <p v-if="center.proposals.value.length === 0" class="empty">
      실행이 완료되면 위험 스케줄의 설비 전환 제안이 여기에 표시됩니다.<br />
      <span class="empty-sub">예: SCH-0003 · ETCH-105 → ETCH-102</span>
    </p>

    <ol v-else class="rows">
      <li v-for="proposal in center.proposals.value" :key="proposal.actionId" class="row">
        <span class="risk" :data-level="proposal.riskLevel">{{ proposal.riskLevel }}</span>

        <div class="move">
          <span class="schedule">{{ proposal.scheduleId }}</span>
          <span class="transfer">
            <span class="from">{{ proposal.originalMachine }}</span>
            <svg class="arrow" viewBox="0 0 28 8" aria-label="에서" role="img">
              <path d="M0 4h24M20 1l5 3-5 3" fill="none" stroke="currentColor" stroke-width="1.5" />
            </svg>
            <span class="to">{{ proposal.alternativeMachine }}</span>
          </span>
          <span class="meta">
            <template v-if="formatGain(proposal.efficiencyGain)">{{ formatGain(proposal.efficiencyGain) }} · </template>영향 {{ proposal.impact }}
          </span>
          <span class="effect">
            지연 {{ formatHours(proposal.expectedDelayReductionHr) }} 완화 ·
            승인률 {{ formatRate(proposal.historicalAcceptanceRate) }}
          </span>
        </div>

        <div v-if="proposal.status === 'PENDING'" class="row-actions">
          <button class="btn btn--sm" @click="center.acceptAction(proposal.actionId)">승인</button>
          <button class="btn btn--ghost btn--sm" @click="center.openApprovalModal(proposal.actionId)">
            검토
          </button>
        </div>
        <span
          v-else
          class="chip state-chip"
          :class="{
            'chip--ok': proposal.status === 'ACCEPTED',
            'chip--bad': proposal.status === 'REJECTED',
          }"
        >
          {{ STATUS_LABEL[proposal.status] }}
        </span>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.action-queue {
  min-height: 0;
}
.empty {
  margin: 0;
  padding: 1.4rem 1.1rem;
  color: var(--ink-dim);
  font-size: 0.8rem;
  line-height: 1.6;
}
.empty-sub {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  opacity: 0.8;
}
.rows {
  flex: 1;
  overflow-y: auto;
  margin: 0;
  padding: 0.3rem 0;
  list-style: none;
}
.row {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.55rem 1rem;
}
.row + .row {
  border-top: 1px solid var(--border);
}
.row:hover {
  background: var(--bg-hover);
}

.risk {
  flex: none;
  width: 4.6rem;
  padding: 0.14rem 0;
  border-radius: 6px;
  text-align: center;
  font-size: 0.64rem;
  font-weight: 750;
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
  background: var(--bg-raised);
  color: var(--ink-dim);
}
.risk[data-level="CRITICAL"] {
  background: var(--status-critical-soft);
  color: var(--status-failed-fg);
}
.risk[data-level="HIGH"] {
  background: var(--status-serious-soft);
  color: var(--status-serious);
}
.risk[data-level="MEDIUM"] {
  background: var(--status-warning-soft);
  color: var(--status-warning);
}

.move {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 0.7rem;
  flex-wrap: wrap;
}
.schedule {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 650;
  color: var(--ink);
}
.transfer {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--font-mono);
  font-size: 0.82rem;
}
.from {
  color: var(--ink-dim);
  text-decoration: line-through;
  text-decoration-color: color-mix(in srgb, var(--ink-dim) 55%, transparent);
  text-decoration-thickness: 1px;
}
.arrow {
  width: 26px;
  height: 8px;
  color: var(--accent);
  flex: none;
}
.to {
  font-weight: 750;
  color: var(--accent-strong);
}
.meta {
  font-size: 0.7rem;
  color: var(--ink-dim);
  white-space: nowrap;
}
.effect {
  flex-basis: 100%;
  font-size: 0.72rem;
  color: var(--accent-strong);
}
.row-actions {
  flex: none;
  display: flex;
  gap: 0.4rem;
}
.state-chip {
  flex: none;
}
</style>
