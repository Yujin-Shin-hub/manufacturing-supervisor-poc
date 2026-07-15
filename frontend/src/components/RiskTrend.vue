<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 리스크 추이 차트 — delay_risk(지연 리스크 감지 이력)의 detection_time을 1시간 구간으로
          묶어 구간별 max risk_score를 그린다 (수제 SVG, 차트 라이브러리 불사용).
          임계값은 사용자가 직접 조정한다 (기본값 85 = 데이터의 CRITICAL 경계)
변경 이력:
  - 2026-07-07: 단계 8 재설계 4차 — 최초 작성
  - 2026-07-07: 재설계 5차 — 곡선/그라디언트/툴팁 리디자인, 임계값 v-model로 사용자 지정
  - 2026-07-07: 재설계 5차 — 고정 viewBox의 letterbox 문제 해결: ResizeObserver로 컨테이너
                크기에 맞춰 동적 렌더링, 슬림 스트립 높이에 최적화
  - 2026-07-14: chartHost가 v-else로 늦게 렌더될 때 ResizeObserver가 붙지 않아
                600×120 기본 크기에 고정되던 버그 수정 (watch로 observe 대상 갱신)
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  hourlyRiskSeries,
  RISK_SCORE_CRITICAL_THRESHOLD,
  type FactorySnapshotState,
} from "../composables/useFactorySnapshot";

const props = defineProps<{
  snapshot: FactorySnapshotState;
}>();

/** 임계값 — 부모(App)가 알림 판정에 같은 값을 쓰도록 v-model로 공유한다 */
const threshold = defineModel<number>("threshold", {
  default: RISK_SCORE_CRITICAL_THRESHOLD,
});

/* 차트는 컨테이너 픽셀 크기 그대로 그린다 (letterbox 없음, 글자 크기 고정) */
const MARGIN = { left: 30, right: 14, top: 14, bottom: 18 } as const;

const chartHost = ref<HTMLElement | null>(null);
const size = ref({ w: 600, h: 120 });
let observer: ResizeObserver | null = null;

onMounted(() => {
  observer = new ResizeObserver((entries) => {
    const entry = entries[0];
    if (entry === undefined) return;
    const { width, height } = entry.contentRect;
    if (width > 0 && height > 0) size.value = { w: width, h: height };
  });
  if (chartHost.value !== null) observer.observe(chartHost.value);
});
// chart-wrap은 데이터 도착 후에야 렌더된다(v-else) — mount 시점엔 ref가 null이므로
// ref가 생기고/사라질 때마다 observe 대상을 갱신한다 (붙지 않으면 size가 기본값에 고정)
watch(chartHost, (host, previous) => {
  if (observer === null) return;
  if (previous) observer.unobserve(previous);
  if (host) observer.observe(host);
});
onBeforeUnmount(() => observer?.disconnect());

const series = computed(() => hourlyRiskSeries(props.snapshot.risks.value));
const hoverIndex = ref<number | null>(null);

const plotW = computed(() => Math.max(size.value.w - MARGIN.left - MARGIN.right, 10));
const plotH = computed(() => Math.max(size.value.h - MARGIN.top - MARGIN.bottom, 10));
const baseline = computed(() => MARGIN.top + plotH.value);

/**
 * risk_score(0~100)를 y좌표(px)로 변환한다.
 *
 * @param score risk_score 값
 * @returns y좌표
 */
function yOf(score: number): number {
  return MARGIN.top + plotH.value * (1 - score / 100);
}

/**
 * 구간 인덱스를 x좌표(px)로 변환한다.
 *
 * @param index 추이 점 인덱스
 * @returns x좌표
 */
function xOf(index: number): number {
  const count = series.value.length;
  if (count <= 1) return MARGIN.left + plotW.value / 2;
  return MARGIN.left + (plotW.value * index) / (count - 1);
}

/** 차트 점 좌표 목록 */
const points = computed(() =>
  series.value.map((point, index) => ({ x: xOf(index), y: yOf(point.maxScore) })),
);

/**
 * Catmull-Rom 보간으로 점 목록을 부드러운 cubic bezier 경로로 만든다.
 * 제어점 y는 플롯 범위로 클램프해 0/100 근처에서 영역 밖으로 튀지 않게 한다.
 *
 * @param list 좌표 점 목록
 * @returns SVG path d 문자열
 */
function smoothPath(list: { x: number; y: number }[]): string {
  const first = list[0];
  if (first === undefined) return "";
  if (list.length === 1) return `M ${first.x} ${first.y}`;

  const clampY = (value: number): number =>
    Math.min(Math.max(value, MARGIN.top), baseline.value);

  let path = `M ${first.x.toFixed(1)} ${first.y.toFixed(1)}`;
  for (let i = 0; i < list.length - 1; i += 1) {
    const p0 = list[Math.max(i - 1, 0)] ?? first;
    const p1 = list[i] ?? first;
    const p2 = list[i + 1] ?? first;
    const p3 = list[Math.min(i + 2, list.length - 1)] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = clampY(p1.y + (p2.y - p0.y) / 6);
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = clampY(p2.y - (p3.y - p1.y) / 6);
    path +=
      ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)},` +
      ` ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return path;
}

const linePath = computed(() => smoothPath(points.value));

/** 곡선 아래 영역 (그라디언트 채움) */
const areaPath = computed(() => {
  const list = points.value;
  const first = list[0];
  const last = list[list.length - 1];
  if (first === undefined || last === undefined) return "";
  return `${smoothPath(list)} L ${last.x.toFixed(1)} ${baseline.value} L ${first.x.toFixed(1)} ${baseline.value} Z`;
});

/** x축 라벨 — 구간이 많으면 4개 간격으로 솎는다 */
const xTicks = computed(() =>
  series.value
    .map((point, index) => ({ point, index }))
    .filter(({ index }) => series.value.length <= 8 || index % 4 === 0),
);

const thresholdY = computed(() => yOf(threshold.value));
const lastPoint = computed(() => series.value[series.value.length - 1] ?? null);
const hovered = computed(() =>
  hoverIndex.value === null ? null : (series.value[hoverIndex.value] ?? null),
);

/**
 * 마우스 x좌표에서 가장 가까운 구간을 하이라이트한다.
 *
 * @param mouseEvent svg 위 mousemove 이벤트
 */
function onMove(mouseEvent: MouseEvent): void {
  const svg = mouseEvent.currentTarget as SVGSVGElement;
  const rect = svg.getBoundingClientRect();
  const count = series.value.length;
  if (rect.width === 0 || count === 0) return;
  const x = mouseEvent.clientX - rect.left;
  const step = count <= 1 ? plotW.value : plotW.value / (count - 1);
  const index = Math.round((x - MARGIN.left) / step);
  hoverIndex.value = Math.min(Math.max(index, 0), count - 1);
}

/**
 * 임계값 입력을 1~100 정수로 정리한다.
 */
function onThresholdChange(): void {
  const value = Number(threshold.value);
  if (Number.isNaN(value)) {
    threshold.value = RISK_SCORE_CRITICAL_THRESHOLD;
    return;
  }
  threshold.value = Math.min(Math.max(Math.round(value), 1), 100);
}
</script>

<template>
  <section class="panel-card trend">
    <header class="panel-head trend-head">
      <h2 class="panel-label">리스크 추이</h2>
      <label class="th-field">
        <span>임계</span>
        <input
          v-model.number="threshold"
          class="control th-input"
          type="number"
          min="1"
          max="100"
          step="1"
          aria-label="임계 risk_score"
          @change="onThresholdChange"
        />
      </label>
      <div class="panel-meta">
        <span
          v-if="lastPoint !== null"
          class="last-badge"
          :class="{ 'last-badge--over': lastPoint.maxScore >= threshold }"
        >
          최근 {{ lastPoint.maxScore.toFixed(1) }}
        </span>
        <span title="delay_risk 감지 이력(detection_time)을 1시간 구간으로 묶은 구간별 최고 risk_score">
          delay_risk · 시간당 max risk_score
        </span>
      </div>
    </header>

    <p v-if="series.length === 0" class="empty">
      {{ snapshot.loading.value ? "현황 로드 중…" : "감지된 리스크가 없습니다." }}
    </p>

    <div v-else ref="chartHost" class="chart-wrap">
      <svg
        class="chart"
        :viewBox="`0 0 ${size.w} ${size.h}`"
        :width="size.w"
        :height="size.h"
        role="img"
        aria-label="시간당 최대 risk_score 추이"
        @mousemove="onMove"
        @mouseleave="hoverIndex = null"
      >
        <defs>
          <linearGradient id="rt-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.26" />
            <stop offset="100%" stop-color="var(--accent)" stop-opacity="0" />
          </linearGradient>
        </defs>

        <!-- 임계 초과 위험 구간 음영 -->
        <rect
          class="danger-zone"
          :x="MARGIN.left"
          :y="MARGIN.top"
          :width="plotW"
          :height="Math.max(thresholdY - MARGIN.top, 0)"
        />

        <!-- y 그리드 + 라벨 (0/50/100) -->
        <g v-for="grid in [0, 50, 100]" :key="grid">
          <line class="grid" :x1="MARGIN.left" :x2="size.w - MARGIN.right" :y1="yOf(grid)" :y2="yOf(grid)" />
          <text class="axis-label" :x="MARGIN.left - 6" :y="yOf(grid) + 3" text-anchor="end">
            {{ grid }}
          </text>
        </g>

        <!-- 임계선 + 라벨 -->
        <line
          class="threshold"
          :x1="MARGIN.left"
          :x2="size.w - MARGIN.right"
          :y1="thresholdY"
          :y2="thresholdY"
        />
        <text class="threshold-label" :x="MARGIN.left + 4" :y="thresholdY - 4">
          임계 {{ threshold }}
        </text>

        <!-- 영역 + 곡선 -->
        <path class="area" :d="areaPath" />
        <path class="line" :d="linePath" />

        <!-- 크로스헤어 -->
        <g v-if="hoverIndex !== null && hovered !== null">
          <line
            class="crosshair"
            :x1="xOf(hoverIndex)"
            :x2="xOf(hoverIndex)"
            :y1="MARGIN.top"
            :y2="baseline"
          />
          <circle class="hover-ring" :cx="xOf(hoverIndex)" :cy="yOf(hovered.maxScore)" r="6.5" />
        </g>

        <!-- 점: 임계 이상만 강조 -->
        <circle
          v-for="(point, index) in series"
          :key="point.hourKey"
          class="dot"
          :class="{ 'dot--over': point.maxScore >= threshold }"
          :cx="xOf(index)"
          :cy="yOf(point.maxScore)"
          :r="point.maxScore >= threshold ? 3 : 2"
        />

        <!-- 최근값 점 강조 -->
        <circle
          v-if="lastPoint !== null"
          class="last-dot"
          :class="{ 'last-dot--over': lastPoint.maxScore >= threshold }"
          :cx="xOf(series.length - 1)"
          :cy="yOf(lastPoint.maxScore)"
          r="3.8"
        />

        <!-- x 라벨 -->
        <text
          v-for="{ point, index } in xTicks"
          :key="`x-${point.hourKey}`"
          class="axis-label"
          :x="xOf(index)"
          :y="size.h - 4"
          text-anchor="middle"
        >
          {{ point.label }}
        </text>
      </svg>

      <!-- 툴팁 -->
      <div
        v-if="hoverIndex !== null && hovered !== null"
        class="tooltip"
        :class="{ 'tooltip--flip': yOf(hovered.maxScore) < 56 }"
        :style="{ left: `${xOf(hoverIndex)}px`, top: `${yOf(hovered.maxScore)}px` }"
      >
        <span class="tooltip-time">{{ hovered.hourKey.slice(5, 10) }} {{ hovered.label }}</span>
        <span class="tooltip-value">max {{ hovered.maxScore.toFixed(1) }}</span>
        <span class="tooltip-count">감지 {{ hovered.count }}건</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.trend {
  min-height: 0;
}
.trend-head {
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
}
.th-field {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-left: 0.7rem;
  font-size: 0.7rem;
  color: var(--ink-dim);
}
.th-input {
  width: 4.2rem;
  padding: 0.12rem 0.4rem;
  font-size: 0.74rem;
  font-family: var(--font-mono);
  text-align: right;
}
.last-badge {
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--accent-dim);
  background: var(--accent-soft);
  color: var(--accent-strong);
  font-size: 0.66rem;
  font-weight: 700;
}
.last-badge--over {
  border-color: color-mix(in srgb, var(--status-critical) 55%, transparent);
  background: var(--status-critical-soft);
  color: var(--status-critical-strong);
}
.empty {
  margin: 0;
  padding: 1rem 1.1rem;
  color: var(--ink-dim);
  font-size: 0.78rem;
}
.chart-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.chart {
  position: absolute;
  inset: 0;
}
.danger-zone {
  fill: var(--status-critical);
  opacity: 0.05;
}
.grid {
  stroke: var(--border);
  stroke-width: 1;
  opacity: 0.55;
}
.axis-label {
  fill: var(--ink-dim);
  font-size: 9.5px;
  font-family: var(--font-mono);
}
.threshold {
  stroke: var(--status-critical);
  stroke-width: 1.2;
  stroke-dasharray: 6 4;
  opacity: 0.9;
}
.threshold-label {
  fill: var(--status-critical-strong);
  font-size: 9.5px;
  font-weight: 700;
  font-family: var(--font-mono);
}
.area {
  fill: url(#rt-area);
}
.line {
  fill: none;
  stroke: var(--accent);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: drop-shadow(0 0 5px rgba(69, 196, 245, 0.35));
}
.crosshair {
  stroke: var(--ink-dim);
  stroke-width: 1;
  stroke-dasharray: 2 3;
  opacity: 0.7;
}
.hover-ring {
  fill: none;
  stroke: var(--accent-strong);
  stroke-width: 1.4;
  opacity: 0.9;
}
.dot {
  fill: var(--bg-panel);
  stroke: var(--accent);
  stroke-width: 1.5;
}
.dot--over {
  fill: var(--status-critical);
  stroke: var(--status-critical-strong);
}
.last-dot {
  fill: var(--accent-strong);
  filter: drop-shadow(0 0 5px var(--accent-glow));
}
.last-dot--over {
  fill: var(--status-critical-strong);
  filter: drop-shadow(0 0 5px rgba(208, 59, 59, 0.6));
}
.tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 10px));
  display: flex;
  flex-direction: column;
  gap: 0.08rem;
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--bg-raised);
  box-shadow: var(--shadow-float);
  pointer-events: none;
  white-space: nowrap;
  z-index: 5;
}
.tooltip--flip {
  transform: translate(-50%, 12px);
}
.tooltip-time {
  font-size: 0.62rem;
  color: var(--ink-dim);
  font-family: var(--font-mono);
}
.tooltip-value {
  font-size: 0.76rem;
  font-weight: 750;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.tooltip-count {
  font-size: 0.64rem;
  color: var(--ink-sub);
}
</style>
