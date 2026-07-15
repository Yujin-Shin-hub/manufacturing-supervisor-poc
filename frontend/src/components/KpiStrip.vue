<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: KPI 스탯 바 — 핵심 3개(진행중 스케줄 · CRITICAL 리스크 · 승인 대기)를 슬림한
          단일 카드로 표시 (리스크 추이와 같은 줄에 낮게 깔린다)
변경 이력:
  - 2026-07-07: 단계 8 대시보드 재설계 2차 — 최초 작성
  - 2026-07-07: 재설계 4차 — 타일 5→3 축소
  - 2026-07-07: 재설계 5차 — 개별 카드 3장을 구분선 있는 단일 슬림 스탯 바로 압축
-->
<script setup lang="ts">
import type { FactorySnapshotState } from "../composables/useFactorySnapshot";

defineProps<{
  snapshot: FactorySnapshotState;
  pendingApprovals: number;
}>();
</script>

<template>
  <div class="panel-card kpi-bar" role="group" aria-label="현황 요약">
    <div class="stat">
      <span class="stat-label">진행중 스케줄</span>
      <span class="stat-value">
        {{ snapshot.scheduleActive.value }}<span class="stat-sub">/{{ snapshot.scheduleTotal.value }}</span>
      </span>
    </div>

    <div class="stat" :data-alert="snapshot.criticalCount.value > 0 ? 'critical' : undefined">
      <span class="stat-label">CRITICAL 리스크</span>
      <span class="stat-value">{{ snapshot.criticalCount.value }}<span class="stat-sub">건</span></span>
    </div>

    <div class="stat" :data-alert="pendingApprovals > 0 ? 'warning' : undefined">
      <span class="stat-label">승인 대기</span>
      <span class="stat-value">{{ pendingApprovals }}<span class="stat-sub">건</span></span>
    </div>

    <p v-if="snapshot.errorMessage.value" class="kpi-error" role="alert">
      현황 조회 실패: {{ snapshot.errorMessage.value }}
    </p>
  </div>
</template>

<style scoped>
.kpi-bar {
  position: relative;
  flex-direction: row;
  align-items: stretch;
}
.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.25rem;
  padding: 0.55rem 1.1rem;
}
.stat + .stat {
  border-left: 1px solid var(--border);
}
.stat-label {
  font-size: 0.64rem;
  font-weight: 650;
  letter-spacing: 0.05em;
  color: var(--ink-dim);
  white-space: nowrap;
}
.stat-value {
  font-size: 1.35rem;
  font-weight: 750;
  line-height: 1.05;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.stat-sub {
  margin-left: 0.12rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--ink-dim);
}

/* 0건이 아닐 때만 상태색 — 색은 숫자에, 라벨은 항상 함께 */
.stat[data-alert="critical"] .stat-value {
  color: var(--status-failed-fg);
}
.stat[data-alert="warning"] .stat-value {
  color: var(--status-warning);
}

.kpi-error {
  position: absolute;
  inset: auto 0.6rem 0.2rem;
  margin: 0;
  font-size: 0.66rem;
  color: var(--status-critical-strong);
}
</style>
