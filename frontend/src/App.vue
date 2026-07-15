<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 관제 콘솔 레이아웃 — 헤더바 / 실행 툴바 / KPI+리스크 추이 / 파이프라인·라인 플로우·
          재조정 제안 큐·이벤트 스트림 그리드 + 리포트 드로어·토스트·승인 모달 오버레이
변경 이력:
  - 2026-07-07: 단계 8 최초 작성
  - 2026-07-07: 다크 관제 콘솔 재설계 — 번호 매긴 패널 제거, 알림 시스템(토스트·모달·알림센터) 연결
  - 2026-07-07: 재설계 2차 — KPI 스트립·리스크 현황 표 추가, 최종 리포트를 우측 드로어로 분리
  - 2026-07-07: 재설계 3차 — 재조정 제안 큐(ActionQueue)를 좌하단 메인 자리에 배치
  - 2026-07-07: 재설계 4차 — 리스크 추이 차트(임계 초과 알림)·Etch 라인 플로우 추가,
                KPI 3개 축소, 리스크 표는 추이·플로우로 대체
  - 2026-07-07: 재설계 5차 — 파이프라인·라인 플로우를 최상단으로, KPI·추이를 중간 행으로 스왑.
                임계값 사용자 지정(v-model + localStorage) 연동
  - 2026-07-14: 오버레이 우선순위 규칙 추가 — 리포트 드로어가 열려 있는 동안 승인 모달을
                보류한다 (드로어를 닫으면 대기 중 승인 건이 모달로 표시). 드로어에
                key_actions 고정 컴포넌트 데이터 전달
  - 2026-07-14: 단계 10 SensorPanel 통합 — MQTT 센서 이벤트 수신 시에만 전용 행 표시
                (MQTT 비활성 데모의 레이아웃은 그대로 유지)
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";

import ActionQueue from "./components/ActionQueue.vue";
import ApprovalModal from "./components/ApprovalModal.vue";
import ArchitectureView from "./components/ArchitectureView.vue";
import KpiStrip from "./components/KpiStrip.vue";
import LineFlow from "./components/LineFlow.vue";
import LogTimeline from "./components/LogTimeline.vue";
import NotificationCenter from "./components/NotificationCenter.vue";
import ReportDrawer from "./components/ReportDrawer.vue";
import RiskTrend from "./components/RiskTrend.vue";
import RunControls from "./components/RunControls.vue";
import SensorPanel from "./components/SensorPanel.vue";
import ToastStack from "./components/ToastStack.vue";
import { useEventStream } from "./composables/useEventStream";
import {
  hourlyRiskSeries,
  RISK_SCORE_CRITICAL_THRESHOLD,
  useFactorySnapshot,
} from "./composables/useFactorySnapshot";
import { useNotifications } from "./composables/useNotifications";
import { useRunControl } from "./composables/useRunControl";
import { useSensorStream } from "./composables/useSensorStream";
import type { EventDataMap, EventName, RunStatus } from "./types/events";

const notifications = useNotifications();
const sensors = useSensorStream();
const stream = useEventStream((event: EventName, data: EventDataMap[EventName]) => {
  notifications.ingest(event, data);
  sensors.ingest(event, data);
});
const control = useRunControl();
const snapshot = useFactorySnapshot();

const RUN_LABEL: Record<RunStatus, string> = {
  IDLE: "대기",
  RUNNING: "실행중",
  DONE: "완료",
  FAILED: "실패",
};

const drawerOpen = ref(false);

// 오버레이 우선순위: 드로어(리포트 읽기)가 최상위 — 열려 있는 동안 승인 모달은 보류한다.
// 승인 건은 PENDING으로 남아 재조정 제안 큐·알림센터에서 처리할 수 있다.
const visibleApproval = computed(() =>
  drawerOpen.value ? null : notifications.modalApproval.value,
);

/** 임계값 저장 키 — 새 세션에서도 사용자가 지정한 값을 유지한다 */
const THRESHOLD_STORAGE_KEY = "fab-supervisor.risk-threshold";

const storedThreshold = Number(window.localStorage.getItem(THRESHOLD_STORAGE_KEY));
const riskThreshold = ref(
  Number.isFinite(storedThreshold) && storedThreshold >= 1 && storedThreshold <= 100
    ? storedThreshold
    : RISK_SCORE_CRITICAL_THRESHOLD,
);

watch(riskThreshold, (value) => {
  window.localStorage.setItem(THRESHOLD_STORAGE_KEY, String(value));
});

// 새 리포트가 도착하면 드로어를 자동으로 연다
watch(
  () => stream.reportMarkdown.value,
  (markdown) => {
    if (markdown !== null) drawerOpen.value = true;
  },
);

// run 종료 시 현황 KPI를 재조회한다 (승인 반영 등 최신화)
watch(
  () => stream.runStatus.value,
  (statusValue) => {
    if (statusValue === "DONE" || statusValue === "FAILED") void snapshot.refresh();
  },
);

// 리스크 추이 최신 구간이 사용자 지정 임계를 넘으면 조치 권고 알림을 발송한다
// (판단 기준은 차트와 동일한 hourlyRiskSeries·동일 임계값 — 임계+구간 키로 1회만)
watch(
  [() => snapshot.risks.value, riskThreshold],
  ([rows, thresholdValue]) => {
    const series = hourlyRiskSeries(rows);
    const latest = series[series.length - 1];
    if (latest === undefined || latest.maxScore < thresholdValue) return;
    notifications.pushAlert(
      "critical",
      "리스크 추이 임계 초과",
      `최근 구간(${latest.label}) max risk_score ${latest.maxScore.toFixed(1)} ≥ ` +
        `${thresholdValue} — 재조정 실행으로 제안을 생성하세요.`,
      `risk-threshold-${thresholdValue}-${latest.hourKey}`,
    );
  },
);
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true"></span>
        <div class="brand-text">
          <span class="brand-name">FAB SUPERVISOR</span>
          <span class="brand-sub">Etch 공정 관제 콘솔</span>
        </div>
      </div>

      <div class="topbar-status">
        <span class="chip" :data-status="stream.runStatus.value">
          RUN · {{ RUN_LABEL[stream.runStatus.value] }}
        </span>
        <span :class="['chip', stream.connected.value ? 'chip--ok' : 'chip--bad']">
          SSE {{ stream.connected.value ? "연결됨" : "끊김" }}
        </span>
        <button
          class="btn btn--ghost btn--sm report-btn"
          :class="{ 'report-btn--ready': stream.reportMarkdown.value !== null }"
          :disabled="stream.reportMarkdown.value === null"
          @click="drawerOpen = true"
        >
          리포트
        </button>
        <NotificationCenter :center="notifications" />
      </div>
    </header>

    <RunControls :control="control" :run-status="stream.runStatus.value" />

    <main class="panels" :class="{ 'panels--sensors': sensors.hasData.value }">
      <ArchitectureView
        class="pipeline-area"
        :nodes="stream.nodes"
        :run-status="stream.runStatus.value"
      />
      <LineFlow class="flow-area" :snapshot="snapshot" :center="notifications" />
      <SensorPanel v-if="sensors.hasData.value" class="sensor-area" :stream="sensors" />
      <div class="overview-strip">
        <KpiStrip
          class="kpi-area"
          :snapshot="snapshot"
          :pending-approvals="notifications.pendingApprovalCount.value"
        />
        <RiskTrend
          v-model:threshold="riskThreshold"
          class="trend-area"
          :snapshot="snapshot"
        />
      </div>
      <ActionQueue class="queue-area" :center="notifications" />
      <LogTimeline class="events-area" :timeline="stream.timeline.value" />
    </main>

    <ReportDrawer
      :open="drawerOpen"
      :report-markdown="stream.reportMarkdown.value"
      :key-actions="stream.keyActions.value"
      :key-actions-total="stream.keyActionsTotal.value"
      @close="drawerOpen = false"
    />
    <ToastStack :toasts="notifications.toasts.value" @dismiss="notifications.dismissToast" />
    <ApprovalModal
      :approval="visibleApproval"
      @accept="notifications.acceptAction"
      @reject="notifications.rejectAction"
      @defer="notifications.deferApproval"
    />
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ── 헤더바 ── */
.topbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.65rem 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg-panel);
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}
.brand-mark {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 10px var(--accent-glow), 0 0 22px var(--accent-glow);
}
.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.brand-name {
  font-size: 0.86rem;
  font-weight: 750;
  letter-spacing: 0.14em;
  color: var(--ink);
}
.brand-sub {
  font-size: 0.68rem;
  color: var(--ink-dim);
}
.topbar-status {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 0.55rem;
}
.report-btn--ready {
  border-color: var(--accent-dim);
  color: var(--accent);
}

/* ── 관제 그리드: 파이프라인|플로우 / (센서 스트림, MQTT 수신 시) / 현황 스트립(전폭) / 제안 큐|이벤트 ── */
.panels {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  grid-template-rows: minmax(0, 1.15fr) 7.5rem minmax(0, 0.85fr);
  gap: 0.8rem;
  padding: 0.8rem 1.25rem 1rem;
  min-height: 0;
}
/* 센서 스트림이 살아있을 때만 4행 그리드 — MQTT 비활성 데모는 기존 3행 유지 */
.panels--sensors {
  grid-template-rows: minmax(0, 1fr) minmax(9rem, 0.55fr) 7rem minmax(0, 0.75fr);
}
.pipeline-area {
  grid-column: 1;
  grid-row: 1;
}
.flow-area {
  grid-column: 2;
  grid-row: 1;
}
.sensor-area {
  grid-column: 1 / -1;
  grid-row: 2;
}
.overview-strip {
  grid-column: 1 / -1;
  grid-row: 2;
  display: flex;
  gap: 0.8rem;
  min-height: 0;
}
.panels--sensors .overview-strip {
  grid-row: 3;
}
.kpi-area {
  flex: none;
  width: 22rem;
}
.trend-area {
  flex: 1;
  min-width: 0;
}
.queue-area {
  grid-column: 1;
  grid-row: 3;
}
.events-area {
  grid-column: 2;
  grid-row: 3;
}
.panels--sensors .queue-area {
  grid-row: 4;
}
.panels--sensors .events-area {
  grid-row: 4;
}

@media (max-width: 1050px) {
  .panels,
  .panels--sensors {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    overflow-y: auto;
  }
  .pipeline-area,
  .flow-area,
  .queue-area,
  .events-area,
  .panels--sensors .queue-area,
  .panels--sensors .events-area {
    grid-column: auto;
    grid-row: auto;
    min-height: 18rem;
  }
  .sensor-area {
    grid-column: auto;
    grid-row: auto;
    min-height: 14rem;
  }
  .panels--sensors .overview-strip {
    grid-row: auto;
  }
  .overview-strip {
    grid-column: auto;
    grid-row: auto;
    flex-direction: column;
  }
  .kpi-area {
    width: auto;
  }
  .trend-area {
    min-height: 11rem;
  }
}
</style>
