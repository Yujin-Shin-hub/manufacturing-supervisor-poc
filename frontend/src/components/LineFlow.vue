<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: Etch 라인 플로우 — 공정 스텝별 설비 풀에 위험 스케줄 배치를 보여주고,
          "현재 배치 / 제안 적용 후" 토글로 재조정 시 흐름이 어떻게 정리되는지 시각화한다.
          하단 효과 요약은 기존 tool 산출값(efficiency_gain·estimated_delay_hr 등) 집계만 사용한다
변경 이력:
  - 2026-07-07: 단계 8 재설계 4차 — 최초 작성
-->
<script setup lang="ts">
import { computed, ref } from "vue";

import type { FactorySnapshotState } from "../composables/useFactorySnapshot";
import type { NotificationCenterState } from "../composables/useNotifications";
import type { ProposalItem } from "../types/notifications";

const props = defineProps<{
  snapshot: FactorySnapshotState;
  center: NotificationCenterState;
}>();

/** Etch 공정군 스텝 표시 순서 (data/README_dataset.txt의 process_step 나열 순) */
const STEP_ORDER = [
  "ETCH_DIELECTRIC",
  "ETCH_CONDUCTOR",
  "ETCH_VIA",
  "ETCH_ALE_TRIM",
] as const;

/** 설비 과부하 경계 — dispatching 후보 제외 기준(current_load ≥ 0.5)과 별개인 표시용 고부하 기준 */
const LOAD_WARN = 0.8;

/** 설비 카드당 표시할 최대 스케줄 칩 수 */
const MAX_CHIPS = 4;

const mode = ref<"before" | "after">("before");

/** 라인에 표시할 스케줄 칩 1개 (위험 스케줄 1건) */
interface FlowChip {
  scheduleId: string;
  riskLevel: string;
  /** 제안 적용으로 이 설비에 새로 들어온 칩 */
  movedIn: boolean;
  /** 제안 적용으로 이 설비를 떠난 자리 표시 */
  ghost: boolean;
}

const schedulesById = computed(() => {
  const map = new Map<string, { process_step: string; due_date: string }>();
  for (const row of props.snapshot.schedules.value) {
    map.set(row.schedule_id, { process_step: row.process_step, due_date: row.due_date });
  }
  return map;
});

const machineStatusById = computed(() => {
  const map = new Map<string, string>();
  for (const row of props.snapshot.machines.value) {
    if (!map.has(row.machine_id)) map.set(row.machine_id, row.machine_status);
  }
  return map;
});

/** 적용 대상 제안 (거절·만료 제외) — schedule_id 기준 매핑 */
const activeProposals = computed(() => {
  const map = new Map<string, ProposalItem>();
  for (const proposal of props.center.proposals.value) {
    if (proposal.status === "REJECTED" || proposal.status === "EXPIRED") continue;
    map.set(proposal.scheduleId, proposal);
  }
  return map;
});

/**
 * 제안이 현재 모드에서 "이동됨"으로 그려져야 하는지 판단한다.
 * 승인된 제안은 두 모드 모두에서 이동으로 그린다 (이미 결정된 사실).
 *
 * @param proposal 재조정 제안
 * @returns 이동으로 그려야 하면 true
 */
function isMoved(proposal: ProposalItem): boolean {
  if (proposal.status === "ACCEPTED") return true;
  return mode.value === "after";
}

/** 라인 데이터: 스텝 → 설비 카드 목록(각 카드에 칩 배치) */
const lanes = computed(() => {
  const chipsByMachine = new Map<string, FlowChip[]>();

  /**
   * 설비별 칩 버킷에 칩을 추가한다.
   *
   * @param machineId 대상 설비 id
   * @param chip 추가할 칩
   */
  function place(machineId: string, chip: FlowChip): void {
    const bucket = chipsByMachine.get(machineId);
    if (bucket === undefined) chipsByMachine.set(machineId, [chip]);
    else bucket.push(chip);
  }

  for (const risk of props.snapshot.risks.value) {
    if (risk.risk_level !== "CRITICAL" && risk.risk_level !== "HIGH") continue;
    const proposal = activeProposals.value.get(risk.schedule_id);
    if (proposal !== undefined && isMoved(proposal)) {
      place(proposal.alternativeMachine, {
        scheduleId: risk.schedule_id,
        riskLevel: risk.risk_level,
        movedIn: true,
        ghost: false,
      });
      place(proposal.originalMachine, {
        scheduleId: risk.schedule_id,
        riskLevel: risk.risk_level,
        movedIn: false,
        ghost: true,
      });
    } else {
      place(risk.machine_id, {
        scheduleId: risk.schedule_id,
        riskLevel: risk.risk_level,
        movedIn: false,
        ghost: false,
      });
    }
  }

  return STEP_ORDER.map((step) => ({
    step,
    machines: props.snapshot.machines.value
      .filter((row) => row.process_step === step)
      .map((row) => {
        const chips = (chipsByMachine.get(row.machine_id) ?? []).filter((chip) => {
          // 칩은 스케줄의 공정 스텝 레인에만 그린다 (설비는 여러 스텝에 걸칠 수 있다)
          const schedule = schedulesById.value.get(chip.scheduleId);
          return schedule?.process_step === step;
        });
        // 이동 유입 → 잔류 → 이탈 순으로 정렬해 변화가 먼저 보이게 한다
        chips.sort((a, b) => Number(b.movedIn) - Number(a.movedIn) || Number(a.ghost) - Number(b.ghost));
        return {
          machineId: row.machine_id,
          status: row.machine_status,
          load: row.current_load,
          chips,
          inCount: chips.filter((chip) => chip.movedIn).length,
          outCount: chips.filter((chip) => chip.ghost).length,
        };
      }),
  }));
});

/** 효과 요약 — 모든 수치는 tool 산출값(efficiency_gain·estimated_delay_hr·machine_status·due_date) 집계 */
const effect = computed(() => {
  const proposals = [...activeProposals.value.values()];
  if (proposals.length === 0) return null;

  const riskByScheduleId = new Map(
    props.snapshot.risks.value.map((row) => [row.schedule_id, row]),
  );
  const asofDate = props.snapshot.asof.value.slice(0, 10);

  let critical = 0;
  let high = 0;
  let gainSum = 0;
  let gainCount = 0;
  let delaySum = 0;
  let escape = 0;
  let dueSoon = 0;

  for (const proposal of proposals) {
    if (proposal.riskLevel === "CRITICAL") critical += 1;
    else if (proposal.riskLevel === "HIGH") high += 1;
    if (proposal.efficiencyGain !== null) {
      gainSum += proposal.efficiencyGain;
      gainCount += 1;
    }
    const risk = riskByScheduleId.get(proposal.scheduleId);
    if (risk !== undefined) delaySum += risk.estimated_delay_hr;
    const originStatus = machineStatusById.value.get(proposal.originalMachine);
    if (originStatus === "정지" || originStatus === "점검중") escape += 1;
    const due = schedulesById.value.get(proposal.scheduleId)?.due_date;
    if (due !== undefined && asofDate !== "" && daysBetween(asofDate, due) <= 3) dueSoon += 1;
  }

  return {
    total: proposals.length,
    critical,
    high,
    avgGain: gainCount > 0 ? gainSum / gainCount : null,
    delaySum,
    escape,
    dueSoon,
  };
});

/**
 * 두 날짜 문자열(YYYY-MM-DD) 사이 일수를 계산한다.
 *
 * @param from 시작 날짜
 * @param to 끝 날짜
 * @returns to - from 일수
 */
function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000);
}
</script>

<template>
  <section class="panel-card line-flow">
    <header class="panel-head">
      <h2 class="panel-label">Etch 라인 플로우</h2>
      <div class="segment mode-toggle" role="group" aria-label="배치 보기 모드">
        <button
          type="button"
          :class="{ 'is-active': mode === 'before' }"
          @click="mode = 'before'"
        >
          현재 배치
        </button>
        <button type="button" :class="{ 'is-active': mode === 'after' }" @click="mode = 'after'">
          제안 적용 후
        </button>
      </div>
      <div class="panel-meta">
        <span>CRITICAL·HIGH 스케줄 배치</span>
      </div>
    </header>

    <div class="lanes">
      <div v-for="lane in lanes" :key="lane.step" class="lane">
        <div class="lane-label">
          <span class="lane-step">{{ lane.step.replace("ETCH_", "") }}</span>
          <span class="lane-sub">ETCH</span>
        </div>

        <div class="machines">
          <div
            v-for="machine in lane.machines"
            :key="`${lane.step}-${machine.machineId}`"
            class="machine"
            :data-status="machine.status"
          >
            <div class="machine-head">
              <span class="machine-id">{{ machine.machineId }}</span>
              <span class="machine-status">{{ machine.status }}</span>
              <span v-if="mode === 'after' && machine.outCount > 0" class="delta delta-out"
                >−{{ machine.outCount }}</span
              >
              <span v-if="machine.inCount > 0" class="delta delta-in">+{{ machine.inCount }}</span>
            </div>

            <div
              class="load-track"
              role="img"
              :aria-label="`current_load ${machine.load.toFixed(2)}`"
            >
              <div
                class="load-fill"
                :class="{ 'load-fill--warn': machine.load >= LOAD_WARN }"
                :style="{ width: `${Math.min(machine.load, 1) * 100}%` }"
              ></div>
              <div class="load-tick" :style="{ left: `${LOAD_WARN * 100}%` }"></div>
              <span class="load-value">{{ machine.load.toFixed(2) }}</span>
            </div>

            <div class="chips">
              <span
                v-for="chip in machine.chips.slice(0, MAX_CHIPS)"
                :key="`${chip.scheduleId}-${chip.ghost}`"
                class="chip-item"
                :class="{ 'chip-item--in': chip.movedIn, 'chip-item--ghost': chip.ghost }"
                :data-level="chip.riskLevel"
              >
                <template v-if="chip.movedIn">▸ </template>{{ chip.scheduleId }}
              </span>
              <span v-if="machine.chips.length > MAX_CHIPS" class="chip-more">
                +{{ machine.chips.length - MAX_CHIPS }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <footer v-if="effect !== null" class="effect" :class="{ 'effect--active': mode === 'after' }">
      <span class="effect-title">제안 {{ effect.total }}건 적용 시 조치 범위</span>
      <ul class="effect-chips">
        <li>CRITICAL {{ effect.critical }} · HIGH {{ effect.high }} 조치 대상</li>
        <li v-if="effect.avgGain !== null">평균 부하 개선 {{ effect.avgGain.toFixed(2) }}</li>
        <li>지연 노출 {{ effect.delaySum.toFixed(1) }}h 대상</li>
        <li>정지·점검중 설비 이탈 {{ effect.escape }}건</li>
        <li>납기 3일 이내 {{ effect.dueSoon }}건 포함</li>
      </ul>
    </footer>
  </section>
</template>

<style scoped>
.line-flow {
  min-height: 0;
}
.mode-toggle {
  margin-left: 0.6rem;
}
.mode-toggle button {
  padding: 0.18rem 0.6rem;
  font-size: 0.72rem;
}

.lanes {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.4rem 0.9rem;
}
.lane {
  display: flex;
  gap: 0.8rem;
  padding: 0.5rem 0;
}
.lane + .lane {
  border-top: 1px dashed var(--border);
}
.lane-label {
  flex: none;
  width: 6.4rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  line-height: 1.25;
}
.lane-step {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  font-weight: 700;
  color: var(--ink-sub);
}
.lane-sub {
  font-size: 0.62rem;
  letter-spacing: 0.1em;
  color: var(--ink-dim);
}
.machines {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9.6rem, 1fr));
  gap: 0.55rem;
}
.machine {
  padding: 0.5rem 0.6rem 0.55rem;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: var(--bg-raised);
}
.machine[data-status="정지"] {
  border-color: color-mix(in srgb, var(--status-critical) 55%, var(--border-strong));
}
.machine[data-status="점검중"] {
  border-color: color-mix(in srgb, var(--status-warning) 45%, var(--border-strong));
}
.machine-head {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}
.machine-id {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 700;
  color: var(--ink);
}
.machine-status {
  font-size: 0.64rem;
  color: var(--status-done-fg);
}
.machine[data-status="정지"] .machine-status {
  color: var(--status-failed-fg);
}
.machine[data-status="점검중"] .machine-status {
  color: var(--status-warning);
}
.delta {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 0.66rem;
  font-weight: 750;
}
.delta-in {
  color: var(--accent);
}
.delta-out {
  color: var(--ink-dim);
}
.delta-in + .delta-in,
.delta-out + .delta-in {
  margin-left: 0.2rem;
}

.load-track {
  position: relative;
  height: 6px;
  margin: 0.45rem 0 0.5rem;
  border-radius: 4px;
  background: var(--bg-inset);
  overflow: visible;
}
.load-fill {
  height: 100%;
  border-radius: 4px;
  background: var(--accent-dim);
}
.load-fill--warn {
  background: var(--status-serious);
}
.load-tick {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 1.5px;
  background: var(--status-critical);
  opacity: 0.7;
}
.load-value {
  position: absolute;
  right: 0;
  top: -1.05rem;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  color: var(--ink-dim);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.28rem;
  min-height: 1.1rem;
}
.chip-item {
  padding: 0.05rem 0.4rem;
  border: 1px solid var(--border-strong);
  border-radius: 5px;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  color: var(--ink-sub);
  white-space: nowrap;
}
.chip-item[data-level="CRITICAL"] {
  border-color: color-mix(in srgb, var(--status-critical) 65%, transparent);
  color: var(--status-failed-fg);
}
.chip-item[data-level="HIGH"] {
  border-color: color-mix(in srgb, var(--status-serious) 60%, transparent);
  color: var(--status-serious);
}
.chip-item--in {
  background: var(--accent-soft);
  border-color: var(--accent-dim);
  color: var(--accent-strong);
}
.chip-item--ghost {
  opacity: 0.4;
  text-decoration: line-through;
}
.chip-more {
  font-size: 0.62rem;
  color: var(--ink-dim);
  align-self: center;
}

.effect {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.9rem;
  padding: 0.55rem 1rem 0.65rem;
  border-top: 1px solid var(--border);
  transition: background 0.2s ease;
}
.effect--active {
  background: var(--accent-soft);
}
.effect-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--ink);
}
.effect-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.9rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.effect-chips li {
  font-size: 0.7rem;
  color: var(--ink-sub);
  font-variant-numeric: tabular-nums;
}
.effect--active .effect-chips li {
  color: var(--ink);
}
</style>
