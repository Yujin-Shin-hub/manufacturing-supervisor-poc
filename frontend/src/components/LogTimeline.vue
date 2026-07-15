<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 이벤트 스트림 — 이벤트 시간순 리스트, 원문 payload 접기/펼치기 (docs/dashboard.md)
변경 이력:
  - 2026-07-07: 단계 8 최초 작성
  - 2026-07-07: 색상을 styles/tokens.css 변수로 교체
  - 2026-07-07: 다크 콘솔 스타일 재작성 — 레일 도트·시각 분리·workflow 이벤트 요약 추가
  - 2026-07-14: 단계 10 sensor_alert 요약 문구 추가 (sensor_update는 타임라인 미수집)
-->
<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

import type { EventDataMap, EventName, TimelineEntry } from "../types/events";

const props = defineProps<{
  timeline: TimelineEntry[];
}>();

const listElement = ref<HTMLElement | null>(null);

watch(
  () => props.timeline.length,
  async () => {
    await nextTick();
    listElement.value?.scrollTo({ top: listElement.value.scrollHeight });
  },
);

/**
 * 타임라인 한 줄에 표시할 이벤트 요약 문구를 만든다.
 *
 * @param entry 수신 이벤트 1건 (event 타입명 + data 원문)
 * @returns 사람이 훑어보기 좋은 한 줄 요약 문자열
 */
function summarize(entry: TimelineEntry): string {
  const data = entry.data as EventDataMap[EventName] & Record<string, unknown>;
  switch (entry.event) {
    case "run_start":
      return `mode=${data.mode} asof=${data.asof}`;
    case "llm_provider_selected":
      return `${data.requested_provider} → ${data.active_provider} (${data.model_name})`;
    case "routing_decision":
      return `→ ${(data.target_agents as string[]).join(", ")}`;
    case "agent_start":
      return `${data.agent}`;
    case "tool_call":
      return `${data.agent} · ${data.tool} (${data.rows}행)`;
    case "agent_end":
      return `${data.agent} · alerts ${(data.alerts as string[]).length}건`;
    case "action_proposed":
      return `${data.action_id} ${data.schedule_id} → ${data.alternative_machine}`;
    case "approval_required":
      return `${data.action_id} ${data.risk_level}`;
    case "action_accepted":
      return `${data.action_id} · ${data.supervisor_id}`;
    case "action_rejected":
      return `${data.action_id} · ${data.reject_reason}`;
    case "action_reproposed":
      return `${data.previous_action_id} → ${data.alternative_machine} (rank ${data.candidate_rank})`;
    case "action_escalated":
      return `${data.action_id} · ${data.escalation_reason}`;
    case "sensor_alert":
      return `${data.line} ${data.sensor} · ${data.rule} (${(data.values as number[]).join(" → ")} ${data.unit})`;
    case "error":
      return `${data.agent ?? "-"} · ${data.message}`;
    case "run_end":
      return `status=${data.status}`;
    default:
      return "";
  }
}

/**
 * 이벤트 시각 문자열에서 시:분:초만 잘라 표시한다.
 *
 * @param ts "YYYY-MM-DD HH:MM:SS" 형태의 이벤트 시각
 * @returns "HH:MM:SS" 부분 문자열
 */
function timeOf(ts: string): string {
  return ts.length >= 19 ? ts.slice(11, 19) : ts;
}
</script>

<template>
  <section class="panel-card log-timeline">
    <header class="panel-head">
      <h2 class="panel-label">이벤트 스트림</h2>
      <div class="panel-meta">
        <span>{{ timeline.length }} events</span>
      </div>
    </header>

    <p v-if="timeline.length === 0" class="empty">
      이벤트 대기 중 — 실행을 시작하면 라우팅·툴콜·리포트 이벤트가 실시간으로 쌓입니다.
    </p>

    <ol v-else ref="listElement" class="entries">
      <li v-for="entry in timeline" :key="entry.data.seq" class="entry" :data-event="entry.event">
        <details>
          <summary>
            <span class="rail-dot" aria-hidden="true"></span>
            <time class="ts">{{ timeOf(entry.data.ts) }}</time>
            <span class="event">{{ entry.event }}</span>
            <span class="summary-text">{{ summarize(entry) }}</span>
            <span class="seq">#{{ String(entry.data.seq).padStart(2, "0") }}</span>
          </summary>
          <pre class="payload">{{ JSON.stringify(entry.data, null, 2) }}</pre>
        </details>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.log-timeline {
  min-height: 0;
}
.empty {
  margin: 0;
  padding: 1.4rem 1.1rem;
  color: var(--ink-dim);
  font-size: 0.8rem;
  line-height: 1.5;
}
.entries {
  flex: 1;
  overflow-y: auto;
  margin: 0;
  padding: 0.35rem 0;
  list-style: none;
}
summary {
  display: flex;
  align-items: baseline;
  gap: 0.55rem;
  padding: 0.34rem 0.9rem;
  cursor: pointer;
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  list-style: none;
}
summary::-webkit-details-marker {
  display: none;
}
summary:hover {
  background: var(--bg-hover);
}
.rail-dot {
  flex: none;
  align-self: center;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-dim);
}
.ts {
  flex: none;
  color: var(--ink-dim);
  font-family: var(--font-mono);
  font-size: 0.7rem;
}
.event {
  flex: none;
  font-weight: 650;
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--ink-sub);
}
.summary-text {
  flex: 1;
  color: var(--ink-dim);
  overflow: hidden;
  text-overflow: ellipsis;
}
.seq {
  flex: none;
  color: var(--ink-dim);
  font-family: var(--font-mono);
  font-size: 0.66rem;
  opacity: 0.7;
}
.payload {
  margin: 0.15rem 0.9rem 0.5rem 2rem;
  padding: 0.55rem 0.75rem;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-inset);
  color: var(--ink-sub);
  font-size: 0.7rem;
  line-height: 1.55;
}

/* 이벤트 계열별 색상 — 레일 도트와 이벤트명에 동일 적용 */
.entry[data-event="run_start"] .rail-dot,
.entry[data-event="routing_decision"] .rail-dot,
.entry[data-event="agent_start"] .rail-dot {
  background: var(--accent);
}
.entry[data-event="routing_decision"] .event,
.entry[data-event="agent_start"] .event {
  color: var(--accent);
}
.entry[data-event="agent_end"] .rail-dot,
.entry[data-event="run_end"] .rail-dot {
  background: var(--status-done-fg);
}
.entry[data-event="agent_end"] .event,
.entry[data-event="run_end"] .event {
  color: var(--status-done-fg);
}
.entry[data-event="tool_call"] .rail-dot {
  background: var(--ink-sub);
}
.entry[data-event="action_proposed"] .rail-dot,
.entry[data-event="action_reproposed"] .rail-dot,
.entry[data-event="action_accepted"] .rail-dot,
.entry[data-event="action_rejected"] .rail-dot {
  background: var(--status-warning);
}
.entry[data-event="approval_required"] .rail-dot,
.entry[data-event="action_escalated"] .rail-dot,
.entry[data-event="error"] .rail-dot {
  background: var(--status-critical-strong);
}
.entry[data-event="approval_required"] .event,
.entry[data-event="action_escalated"] .event,
.entry[data-event="error"] .event {
  color: var(--status-failed-fg);
}
</style>
