<!--
작성자  : 신유진
작성일  : 2026-07-14
작성 목적: 리포트 드로어의 "핵심 추천 액션" 고정 컴포넌트 — run_end.key_actions 구조화 데이터를
          주입받아 렌더링한다 (A안). markdown 표를 대체하며, 수치는 서버 산출값을 표시만 한다
          (반올림 자릿수는 api-spec 3-1: 시간 1dp, 점수 1dp, 비율→% 변환은 표시 계층 1회).
변경 이력:
  - 2026-07-14: 최초 작성 (대시보드 리포트 개선 — 드로어 표 가독성 P1)
-->
<script setup lang="ts">
import type { KeyActionData } from "../types/events";

const props = defineProps<{
  actions: KeyActionData[];
  total: number;
}>();

/**
 * 시간(h) 값을 표시 문자열로 변환한다 (api-spec 3-1: 1dp).
 *
 * @param value 서버 산출 시간 값 또는 null
 * @return "5.0h" 형태 문자열, 근거 없으면 "-"
 */
function formatHours(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(1)}h`;
}

/**
 * 비율(0~1)을 퍼센트 문자열로 변환한다 (단위 변환은 표시 계층 1회, api-spec 3-3).
 *
 * @param value 서버 산출 비율 값 또는 null
 * @return "39%" 형태 문자열, 근거 없으면 "-"
 */
function formatRate(value: number | null): string {
  return value === null ? "-" : `${Math.round(value * 100)}%`;
}

/**
 * policy_score를 표시 문자열로 변환한다 (1dp).
 *
 * @param value 서버 산출 점수 값 또는 null
 * @return "52.1" 형태 문자열, 근거 없으면 "-"
 */
function formatScore(value: number | null): string {
  return value === null ? "-" : value.toFixed(1);
}

/**
 * 지연 완화 바의 채움 비율(%)을 계산한다 — 표시용 비율만 계산하고 새 수치를 만들지 않는다.
 *
 * @param action 핵심 추천 액션 1건
 * @return 0~100 채움 퍼센트. 근거가 없으면 0
 */
function reductionPercent(action: KeyActionData): number {
  const total = action.estimated_delay_hr;
  const cut = action.expected_delay_reduction_hr;
  if (total === null || cut === null || total <= 0) return 0;
  return Math.min(Math.max((cut / total) * 100, 0), 100);
}

/** 남은 건수 안내 문구용 */
const shownCount = (): number => props.actions.length;
</script>

<template>
  <section class="key-actions" aria-label="핵심 추천 액션">
    <header class="ka-head">
      <h2 class="ka-title">핵심 추천 액션</h2>
      <span class="ka-sub">
        승인 필요 순
        <template v-if="total > shownCount()"> · 전체 {{ total }}건 중 상위 {{ shownCount() }}건</template>
      </span>
    </header>

    <ol class="ka-list">
      <li v-for="action in actions" :key="action.rank" class="ka-row">
        <div class="ka-line1">
          <span class="ka-rank">{{ action.rank }}</span>
          <span class="ka-sched">{{ action.schedule_id }}</span>
          <span class="ka-move">
            <span v-if="action.original_machine" class="from">{{ action.original_machine }}</span>
            <span v-if="action.original_machine" class="arrow" aria-label="에서">→</span>
            <span class="to">{{ action.alternative_machine ?? "-" }}</span>
          </span>
          <span
            v-if="action.risk_level"
            class="ka-risk"
            :data-risk="action.risk_level"
          >{{ action.risk_level }}</span>
          <span class="ka-score" title="policy_score">
            policy <strong>{{ formatScore(action.policy_score) }}</strong>
          </span>
        </div>

        <div class="ka-line2">
          <span class="ka-delay">
            <span class="delay-label">
              지연 {{ formatHours(action.estimated_delay_hr) }} →
              <strong>{{ formatHours(action.expected_remaining_delay_hr) }}</strong>
              <em v-if="action.expected_delay_reduction_hr !== null">
                (−{{ formatHours(action.expected_delay_reduction_hr) }})
              </em>
            </span>
            <span class="delay-track" aria-hidden="true">
              <span class="delay-cut" :style="{ width: `${reductionPercent(action)}%` }"></span>
            </span>
          </span>
          <span class="ka-rate">
            이력 승인률 <strong>{{ formatRate(action.historical_acceptance_rate) }}</strong>
            <small v-if="action.historical_sample_count !== null">n={{ action.historical_sample_count }}</small>
          </span>
        </div>

        <p v-if="action.expected_effect" class="ka-effect">
          {{ action.expected_effect }}
          <template v-if="action.quality_history_note"> · {{ action.quality_history_note }}</template>
        </p>
      </li>
    </ol>

    <p v-if="total > shownCount()" class="ka-footnote">
      나머지 {{ total - shownCount() }}건은 아래 설비 재배정 제안 절의 근거 표에 있습니다.
    </p>
  </section>
</template>

<style scoped>
.key-actions {
  margin: 0.4rem 0 1.2rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-panel);
  background: var(--bg-inset);
  overflow: hidden;
}
.ka-head {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  padding: 0.7rem 1rem 0.55rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg-raised);
}
.ka-title {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 750;
  color: var(--ink);
}
.ka-title::before {
  content: "";
  display: inline-block;
  width: 3px;
  height: 0.85em;
  margin-right: 0.5rem;
  vertical-align: -0.08em;
  border-radius: 2px;
  background: var(--accent);
}
.ka-sub {
  font-size: 0.7rem;
  color: var(--ink-dim);
}

.ka-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.ka-row {
  padding: 0.7rem 1rem 0.75rem;
}
.ka-row + .ka-row {
  border-top: 1px solid var(--border);
}

.ka-line1 {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.ka-rank {
  flex: none;
  width: 1.15rem;
  height: 1.15rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  color: var(--ink-sub);
  font-size: 0.66rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  align-self: center;
}
.ka-sched {
  font-family: var(--font-mono);
  font-size: 0.84rem;
  font-weight: 750;
  color: var(--ink);
}
.ka-move {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  white-space: nowrap;
}
.ka-move .from {
  color: var(--ink-dim);
  text-decoration: line-through;
}
.ka-move .arrow {
  margin: 0 0.3rem;
  color: var(--accent);
}
.ka-move .to {
  font-weight: 750;
  color: var(--accent-strong);
}
.ka-risk {
  padding: 0.1em 0.5em;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  font-weight: 750;
  letter-spacing: 0.05em;
  background: var(--status-critical-soft);
  color: var(--status-critical-strong);
}
.ka-risk[data-risk="HIGH"] {
  background: var(--status-serious-soft);
  color: var(--status-serious);
}
.ka-score {
  margin-left: auto;
  font-size: 0.72rem;
  color: var(--ink-dim);
  white-space: nowrap;
}
.ka-score strong {
  font-family: var(--font-mono);
  font-size: 0.84rem;
  color: var(--accent-strong);
}

.ka-line2 {
  display: flex;
  align-items: center;
  gap: 1.1rem;
  margin-top: 0.45rem;
  flex-wrap: wrap;
}
.ka-delay {
  flex: 1 1 12rem;
  min-width: 10rem;
}
.delay-label {
  display: block;
  font-size: 0.72rem;
  color: var(--ink-sub);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.delay-label strong {
  color: var(--ink);
}
.delay-label em {
  font-style: normal;
  color: var(--status-done-fg);
}
.delay-track {
  display: block;
  height: 4px;
  margin-top: 0.28rem;
  border-radius: 2px;
  background: var(--status-critical-soft);
  overflow: hidden;
}
.delay-cut {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: var(--status-good);
}
.ka-rate {
  font-size: 0.72rem;
  color: var(--ink-dim);
  white-space: nowrap;
}
.ka-rate strong {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--ink);
}
.ka-rate small {
  margin-left: 0.25rem;
  color: var(--ink-dim);
}

.ka-effect {
  margin: 0.45rem 0 0;
  font-size: 0.74rem;
  line-height: 1.5;
  color: var(--ink-dim);
}

.ka-footnote {
  margin: 0;
  padding: 0.55rem 1rem 0.7rem;
  border-top: 1px solid var(--border);
  font-size: 0.7rem;
  color: var(--ink-dim);
}
</style>
