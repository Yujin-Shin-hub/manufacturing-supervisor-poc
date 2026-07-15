<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 실행 파이프라인 그래프 — Supervisor→Routing→Worker→report SVG 노드 그래프.
          활성 엣지 위로 플라즈마 패킷이 흐르며 실행 위치를 보여준다 (그래프 라이브러리 불사용)
변경 이력:
  - 2026-07-07: 단계 8 최초 작성 (상태 정의는 docs/api-spec.md 2-2)
  - 2026-07-07: 노드 색상·범례 칩을 styles/tokens.css·ui.css 공통 모듈로 교체
  - 2026-07-07: 트리형 배치를 SVG 그래프 + animateMotion 패킷 애니메이션으로 전면 교체
  - 2026-07-14: 노드 라벨 한글화 (NODE_LABELS — 키·이벤트 매칭은 영문 그대로,
                표시만 한글. 라벨 폰트를 mono→sans로 교체)
-->
<script setup lang="ts">
import { computed } from "vue";

import type { NodeKey, NodeStatus, RunStatus } from "../types/events";

const props = defineProps<{
  nodes: Record<NodeKey, NodeStatus>;
  runStatus: RunStatus;
}>();

const STATUS_LABEL: Record<NodeStatus, string> = {
  PENDING: "대기",
  RUNNING: "실행중",
  DONE: "완료",
  FAILED: "실패",
  SKIPPED: "생략",
};

const LEGEND_STATUSES: readonly NodeStatus[] = [
  "PENDING",
  "RUNNING",
  "DONE",
  "FAILED",
  "SKIPPED",
];

/** 그래프 좌표 정의 — viewBox 0 0 760 396 기준 고정 배치 */
interface GraphNode {
  key: "supervisor" | NodeKey;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

const WORKER_KEYS: readonly NodeKey[] = [
  "field_status",
  "risk_alert",
  "delay_pred",
  "dispatching",
  "scheduling_policy",
];

/** 노드 표시 라벨 (한글) — 이벤트·큐와의 대조는 이벤트 스트림의 영문 키로 한다 */
const NODE_LABELS: Record<GraphNode["key"], string> = {
  supervisor: "슈퍼바이저",
  routing: "라우팅",
  field_status: "현장 현황",
  risk_alert: "리스크 알림",
  delay_pred: "지연 예측",
  dispatching: "설비 재배정",
  scheduling_policy: "정책 검증",
  supervisor_validation: "최종 검증",
  report: "리포트",
};
const WORKER_X: readonly number[] = [18, 166, 314, 462, 610];
const WORKER_W = 132;
const WORKER_Y = 214;
const WORKER_H = 54;

const GRAPH_NODES: readonly GraphNode[] = [
  { key: "supervisor", label: NODE_LABELS.supervisor, x: 295, y: 16, w: 170, h: 46 },
  { key: "routing", label: NODE_LABELS.routing, x: 295, y: 110, w: 170, h: 46 },
  ...WORKER_KEYS.map((key, index) => ({
    key,
    label: NODE_LABELS[key],
    x: WORKER_X[index] ?? 0,
    y: WORKER_Y,
    w: WORKER_W,
    h: WORKER_H,
  })),
  { key: "supervisor_validation", label: NODE_LABELS.supervisor_validation, x: 295, y: 286, w: 170, h: 38 },
  { key: "report", label: NODE_LABELS.report, x: 295, y: 342, w: 170, h: 46 },
];

type EdgeState = "idle" | "active" | "done" | "failed" | "skipped";

interface GraphEdge {
  id: string;
  path: string;
  state: EdgeState;
}

/** Routing은 run_start~routing_decision 사이 이벤트가 없으므로 실행 중 표시는 파생값으로 만든다 */
const routingDisplay = computed<NodeStatus>(() =>
  props.nodes.routing === "PENDING" && props.runStatus === "RUNNING"
    ? "RUNNING"
    : props.nodes.routing,
);

/**
 * 노드의 화면 표시용 상태를 반환한다 (routing만 파생 상태를 사용).
 *
 * @param key 그래프 노드 키
 * @return 표시할 노드 상태
 */
function displayStatus(key: GraphNode["key"]): NodeStatus | "SUPERVISOR" {
  if (key === "supervisor") return "SUPERVISOR";
  if (key === "routing") return routingDisplay.value;
  return props.nodes[key];
}

/**
 * 대상 노드 상태를 유입 엣지 상태로 변환한다.
 *
 * @param target 엣지가 향하는 노드의 상태
 * @return 엣지 표시 상태
 */
function edgeStateFor(target: NodeStatus): EdgeState {
  if (target === "RUNNING") return "active";
  if (target === "DONE") return "done";
  if (target === "FAILED") return "failed";
  if (target === "SKIPPED") return "skipped";
  return "idle";
}

const edges = computed<GraphEdge[]>(() => {
  const list: GraphEdge[] = [];

  list.push({
    id: "pg-sup-routing",
    path: "M 380 62 C 380 78, 380 94, 380 110",
    state: edgeStateFor(routingDisplay.value),
  });

  WORKER_KEYS.forEach((key, index) => {
    const cx = (WORKER_X[index] ?? 0) + WORKER_W / 2;
    list.push({
      id: `pg-routing-${key}`,
      path: `M 380 156 C 380 188, ${cx} 180, ${cx} ${WORKER_Y}`,
      state: edgeStateFor(props.nodes[key]),
    });

    // Worker → validation 엣지: 검증 실행 중이면 완료된 Worker의 결과가 흘러 들어가는 모습
    const workerStatus = props.nodes[key];
    let outState: EdgeState = "idle";
    if (workerStatus === "SKIPPED") outState = "skipped";
    else if (workerStatus === "FAILED") outState = "failed";
    else if (workerStatus === "DONE") {
      outState =
        props.nodes.supervisor_validation === "RUNNING"
          ? "active"
          : edgeStateFor(props.nodes.supervisor_validation);
    }
    list.push({
      id: `pg-${key}-validation`,
      path: `M ${cx} ${WORKER_Y + WORKER_H} C ${cx} 280, 380 276, 380 286`,
      state: outState,
    });
  });

  list.push({
    id: "pg-validation-report",
    path: "M 380 324 C 380 330, 380 336, 380 342",
    state:
      props.nodes.supervisor_validation === "DONE"
        ? edgeStateFor(props.nodes.report)
        : edgeStateFor(props.nodes.supervisor_validation),
  });

  return list;
});
</script>

<template>
  <section class="panel-card pipeline">
    <header class="panel-head">
      <h2 class="panel-label">실행 파이프라인</h2>
      <div class="panel-meta">
        <span v-if="runStatus === 'RUNNING'" class="live">
          <span class="live-dot" aria-hidden="true"></span>LIVE
        </span>
      </div>
    </header>

    <div class="graph-wrap">
      <svg class="graph" viewBox="0 0 760 396" role="img" aria-label="에이전트 실행 파이프라인 그래프">
        <!-- 엣지 -->
        <g>
          <template v-for="edge in edges" :key="edge.id">
            <path :id="edge.id" class="edge" :data-state="edge.state" :d="edge.path" />
            <g v-if="edge.state === 'active'" class="packets">
              <circle class="packet" r="3.6">
                <animateMotion dur="1.5s" repeatCount="indefinite">
                  <mpath :href="`#${edge.id}`" />
                </animateMotion>
              </circle>
              <circle class="packet packet--trail" r="2.4">
                <animateMotion dur="1.5s" begin="-0.75s" repeatCount="indefinite">
                  <mpath :href="`#${edge.id}`" />
                </animateMotion>
              </circle>
            </g>
          </template>
        </g>

        <!-- 노드 -->
        <g
          v-for="node in GRAPH_NODES"
          :key="node.key"
          class="pnode"
          :data-status="displayStatus(node.key)"
        >
          <rect class="pnode-box" :x="node.x" :y="node.y" :width="node.w" :height="node.h" rx="10" />
          <text
            class="pnode-name"
            :x="node.x + node.w / 2"
            :y="node.y + (node.key === 'supervisor' ? 28 : 22)"
            text-anchor="middle"
          >
            {{ node.label }}
          </text>
          <text
            v-if="node.key !== 'supervisor'"
            class="pnode-state"
            :x="node.x + node.w / 2"
            :y="node.y + node.h - 12"
            text-anchor="middle"
          >
            {{ STATUS_LABEL[displayStatus(node.key) as NodeStatus] }}
          </text>
        </g>
      </svg>
    </div>

    <footer class="legend-row">
      <ul class="legend">
        <li v-for="statusName in LEGEND_STATUSES" :key="statusName" class="chip" :data-status="statusName">
          {{ STATUS_LABEL[statusName] }}
        </li>
      </ul>
    </footer>
  </section>
</template>

<style scoped>
.pipeline {
  min-height: 0;
}
.live {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--accent);
  font-weight: 700;
  letter-spacing: 0.12em;
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent-glow);
  animation: live-pulse 1.2s ease-in-out infinite;
}
@keyframes live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.graph-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  padding: 0.6rem 0.8rem;
  /* 관제 도면 느낌의 미세 도트 그리드 */
  background-image: radial-gradient(rgba(163, 176, 196, 0.07) 1px, transparent 1px);
  background-size: 22px 22px;
}
.graph {
  width: 100%;
  height: 100%;
  min-height: 0;
}

/* ── 엣지 ── */
.edge {
  fill: none;
  stroke: var(--border-strong);
  stroke-width: 1.5;
  stroke-dasharray: 3 7;
  stroke-linecap: round;
}
.edge[data-state="active"] {
  stroke: var(--accent-dim);
  stroke-dasharray: none;
}
.edge[data-state="done"] {
  stroke: var(--accent-dim);
  stroke-dasharray: none;
  opacity: 0.85;
}
.edge[data-state="failed"] {
  stroke: var(--status-critical);
  stroke-dasharray: none;
  opacity: 0.7;
}
.edge[data-state="skipped"] {
  opacity: 0.3;
}

/* ── 플라즈마 패킷 ── */
.packet {
  fill: var(--accent-strong);
  filter: drop-shadow(0 0 3px var(--accent)) drop-shadow(0 0 7px var(--accent-glow));
}
.packet--trail {
  opacity: 0.55;
}

/* ── 노드 ── */
.pnode-box {
  fill: var(--bg-raised);
  stroke: var(--border-strong);
  stroke-width: 1.2;
  transition: stroke 0.2s ease, fill 0.2s ease;
}
.pnode-name {
  fill: var(--ink);
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 650;
}
.pnode-state {
  fill: var(--ink-dim);
  font-size: 10.5px;
  font-weight: 600;
}

.pnode[data-status="SUPERVISOR"] .pnode-box {
  fill: var(--accent-soft);
  stroke: var(--accent-dim);
}
.pnode[data-status="SUPERVISOR"] .pnode-name {
  fill: var(--accent-strong);
  letter-spacing: 0.04em;
}

.pnode[data-status="RUNNING"] .pnode-box {
  stroke: var(--accent);
  fill: var(--accent-soft);
  filter: drop-shadow(0 0 7px var(--accent-glow));
  animation: node-pulse 1.4s ease-in-out infinite;
}
.pnode[data-status="RUNNING"] .pnode-state {
  fill: var(--accent);
}

.pnode[data-status="DONE"] .pnode-box {
  stroke: var(--status-good);
  fill: var(--status-good-soft);
}
.pnode[data-status="DONE"] .pnode-state {
  fill: var(--status-done-fg);
}

.pnode[data-status="FAILED"] .pnode-box {
  stroke: var(--status-critical);
  fill: var(--status-critical-soft);
}
.pnode[data-status="FAILED"] .pnode-state {
  fill: var(--status-failed-fg);
}

.pnode[data-status="SKIPPED"] .pnode-box {
  stroke-dasharray: 4 4;
  opacity: 0.55;
}
.pnode[data-status="SKIPPED"] .pnode-name {
  fill: var(--ink-dim);
}

@keyframes node-pulse {
  0%,
  100% {
    stroke-opacity: 1;
  }
  50% {
    stroke-opacity: 0.45;
  }
}

.legend-row {
  padding: 0.55rem 1rem 0.7rem;
  border-top: 1px solid var(--border);
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (prefers-reduced-motion: reduce) {
  .packets {
    display: none;
  }
  .pnode[data-status="RUNNING"] .pnode-box,
  .live-dot {
    animation: none;
  }
}
</style>
