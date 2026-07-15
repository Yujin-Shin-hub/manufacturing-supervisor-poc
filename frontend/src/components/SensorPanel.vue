<!--
작성자  : 신유진
작성일  : 2026-07-14
작성 목적: 단계 10 센서 패널 — MQTT 스트림의 라인별 최신 센서값 + 최근 60초 스파크라인
          (vanilla canvas, docs/sensor-stream.md). sensor_alert 시 해당 라인 카드를
          경고색으로 토글한다. 임계치 판정은 서버 rules.py — 프론트는 표시만 한다.
변경 이력:
  - 2026-07-14: 단계 10 최초 작성
-->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from "vue";

import type { SensorSeries, SensorStreamState } from "../composables/useSensorStream";

const props = defineProps<{
  stream: SensorStreamState;
}>();

/** 센서 표시 순서·한글 라벨 (docs/sensor-stream.md 토픽 설계의 3종) */
const SENSOR_LABELS: Record<string, string> = {
  temperature: "온도",
  vibration: "진동",
  throughput: "처리량",
};
const SENSOR_ORDER = ["temperature", "vibration", "throughput"];

/**
 * 라인의 센서 시리즈를 고정 순서로 반환한다 (미수신 센서는 건너뛴다).
 *
 * @param line 라인 이름
 * @return 표시 순서대로 정렬된 시리즈 목록
 */
function orderedSeries(line: string): SensorSeries[] {
  const bucket = props.stream.lines[line] ?? {};
  const known = SENSOR_ORDER.filter((sensor) => sensor in bucket).map(
    (sensor) => bucket[sensor] as SensorSeries,
  );
  const extra = Object.values(bucket).filter((entry) => !SENSOR_ORDER.includes(entry.sensor));
  return [...known, ...extra];
}

/**
 * 센서값 표시 문자열 — 서버가 이미 반올림해 보낸 값을 그대로 표기한다 (새 수치 생성 없음).
 *
 * @param entry 센서 시리즈
 * @return "72.4 C" 형태 문자열
 */
function formatValue(entry: SensorSeries): string {
  return `${entry.latest} ${entry.unit}`;
}

/* ── 스파크라인 (vanilla canvas) ── */

const canvasRefs = new Map<string, HTMLCanvasElement>();

/**
 * canvas ref 콜백 — 라인·센서 키로 canvas를 등록한다.
 *
 * @param key "line/sensor" 키
 * @param el 등록/해제할 canvas 엘리먼트
 */
function registerCanvas(key: string, el: HTMLCanvasElement | null): void {
  if (el === null) canvasRefs.delete(key);
  else canvasRefs.set(key, el);
}

/**
 * 등록된 모든 스파크라인을 다시 그린다 (1초 틱마다 — 초당 1회면 충분, 최적화 금지 스코프 가드).
 */
function drawAll(): void {
  const nowMs = props.stream.now.value;
  for (const line of props.stream.lineNames.value) {
    for (const entry of orderedSeries(line)) {
      const canvas = canvasRefs.get(`${line}/${entry.sensor}`);
      if (canvas) drawSparkline(canvas, entry, nowMs);
    }
  }
}

/**
 * 시리즈 1개의 최근 60초 스파크라인을 canvas에 그린다.
 *
 * @param canvas 대상 canvas
 * @param entry 센서 시리즈
 * @param nowMs 현재 시각 (x축 오른쪽 끝)
 */
function drawSparkline(canvas: HTMLCanvasElement, entry: SensorSeries, nowMs: number): void {
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth;
  const cssHeight = canvas.clientHeight;
  if (cssWidth === 0 || cssHeight === 0) return;
  if (canvas.width !== cssWidth * dpr || canvas.height !== cssHeight * dpr) {
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
  }
  const ctx = canvas.getContext("2d");
  if (ctx === null) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const samples = entry.samples;
  if (samples.length < 2) return;

  let min = Infinity;
  let max = -Infinity;
  for (const sample of samples) {
    if (sample.value < min) min = sample.value;
    if (sample.value > max) max = sample.value;
  }
  const span = max - min || 1;
  const pad = 2;

  const alerting = props.stream.isAlerting(entry);
  const style = getComputedStyle(canvas);
  const stroke = style.getPropertyValue(alerting ? "--status-critical-strong" : "--accent").trim();

  ctx.beginPath();
  for (let index = 0; index < samples.length; index += 1) {
    const sample = samples[index];
    if (sample === undefined) continue;
    const x = cssWidth - ((nowMs - sample.at) / 60_000) * cssWidth;
    const y = pad + (1 - (sample.value - min) / span) * (cssHeight - pad * 2);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 1.4;
  ctx.lineJoin = "round";
  ctx.stroke();

  // 최근값 강조점
  const last = samples[samples.length - 1];
  if (last !== undefined) {
    const x = cssWidth - ((nowMs - last.at) / 60_000) * cssWidth;
    const y = pad + (1 - (last.value - min) / span) * (cssHeight - pad * 2);
    ctx.beginPath();
    ctx.arc(Math.min(x, cssWidth - 2), y, 2, 0, Math.PI * 2);
    ctx.fillStyle = stroke;
    ctx.fill();
  }
}

let stopWatch: (() => void) | null = null;
onMounted(() => {
  stopWatch = watch(() => props.stream.now.value, drawAll, { immediate: true });
});
onBeforeUnmount(() => stopWatch?.());
</script>

<template>
  <section class="panel-card sensors" aria-label="실시간 센서 스트림">
    <header class="panel-head">
      <h2 class="panel-label">센서 스트림</h2>
      <div class="panel-meta">
        <span v-if="stream.receiving.value" class="live">
          <span class="live-dot" aria-hidden="true"></span>MQTT LIVE
        </span>
        <span v-else class="stale">수신 없음</span>
      </div>
    </header>

    <div class="line-grid">
      <article
        v-for="line in stream.lineNames.value"
        :key="line"
        class="line-card"
        :data-alert="stream.lineAlerting(line) ? 'true' : undefined"
      >
        <header class="line-head">
          <span class="line-name">{{ line }}</span>
          <span v-if="stream.lineAlerting(line)" class="line-alert-badge">임계 초과</span>
        </header>
        <div
          v-for="entry in orderedSeries(line)"
          :key="entry.sensor"
          class="sensor-row"
          :data-alert="stream.isAlerting(entry) ? 'true' : undefined"
        >
          <span class="sensor-name">{{ SENSOR_LABELS[entry.sensor] ?? entry.sensor }}</span>
          <canvas
            :ref="(el) => registerCanvas(`${line}/${entry.sensor}`, el as HTMLCanvasElement | null)"
            class="spark"
            :title="entry.alertRule ?? undefined"
          ></canvas>
          <span class="sensor-value">{{ formatValue(entry) }}</span>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.sensors {
  min-height: 0;
}
.live {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--accent);
  font-weight: 700;
  letter-spacing: 0.1em;
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent-glow);
  animation: sensor-live-pulse 1.2s ease-in-out infinite;
}
.stale {
  color: var(--ink-dim);
}
@keyframes sensor-live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.line-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0.55rem;
  padding: 0.6rem 0.8rem 0.75rem;
  overflow-y: auto;
}
.line-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-raised);
  padding: 0.5rem 0.65rem 0.55rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.line-card[data-alert] {
  border-color: var(--status-critical);
  box-shadow: 0 0 0 1px var(--status-critical), 0 0 14px var(--status-critical-soft);
}
.line-head {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}
.line-name {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 750;
  color: var(--ink);
}
.line-alert-badge {
  margin-left: auto;
  padding: 0.08em 0.5em;
  border-radius: 4px;
  background: var(--status-critical-soft);
  color: var(--status-critical-strong);
  font-size: 0.62rem;
  font-weight: 750;
  letter-spacing: 0.05em;
}

.sensor-row {
  display: grid;
  grid-template-columns: 3.2rem 1fr 5.4rem;
  align-items: center;
  gap: 0.5rem;
  padding: 0.16rem 0;
}
.sensor-name {
  font-size: 0.68rem;
  color: var(--ink-dim);
  white-space: nowrap;
}
.spark {
  width: 100%;
  height: 1.15rem;
  display: block;
}
.sensor-value {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  color: var(--ink-sub);
  text-align: right;
  white-space: nowrap;
}
.sensor-row[data-alert] .sensor-value {
  color: var(--status-critical-strong);
  font-weight: 700;
}

@media (prefers-reduced-motion: reduce) {
  .live-dot {
    animation: none;
  }
}
</style>
