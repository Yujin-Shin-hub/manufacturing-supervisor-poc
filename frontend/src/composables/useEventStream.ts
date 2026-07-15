/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: SSE(/events) 수신·재접속·상태머신 — 이벤트→상태 전이는 docs/api-spec.md 2-2가 유일한 기준
 * 변경 이력:
 *   - 2026-07-07: 단계 8 최초 작성 (EventSource 생성은 이 composable에만 둔다)
 *   - 2026-07-07: 알림 시스템 연동용 onEvent 훅 추가 (수신 이벤트를 외부 구독자에 전달)
 *   - 2026-07-14: run_end.key_actions 수신 — 리포트 드로어 고정 컴포넌트용 상태 추가
 *   - 2026-07-14: 단계 10 — sensor_update는 초당 최대 18건이라 타임라인에서 제외
 *                 (센서 패널이 전용 표시 계층, sensor_alert는 타임라인 유지)
 */
import { onBeforeUnmount, onMounted, reactive, ref, type Ref } from "vue";

import {
  AGENT_NAMES,
  EVENT_NAMES,
  NODE_KEYS,
  type EventDataMap,
  type EventName,
  type KeyActionData,
  type NodeKey,
  type NodeStatus,
  type RunStatus,
  type TimelineEntry,
} from "../types/events";

export interface EventStreamState {
  runStatus: Ref<RunStatus>;
  nodes: Record<NodeKey, NodeStatus>;
  timeline: Ref<TimelineEntry[]>;
  reportMarkdown: Ref<string | null>;
  /** run_end.key_actions — 리포트 드로어 고정 컴포넌트의 데이터 소스 */
  keyActions: Ref<KeyActionData[]>;
  keyActionsTotal: Ref<number>;
  connected: Ref<boolean>;
}

/** 수신 이벤트를 상태머신 반영 후 외부(알림 시스템 등)에 전달하는 훅 타입 */
export type EventHook = (event: EventName, data: EventDataMap[EventName]) => void;

/**
 * /events SSE 스트림을 구독하고 api-spec 2-2 상태머신에 따라 Run·노드 상태를 갱신한다.
 *
 * @param onEvent 이벤트 1건 처리 후 호출되는 선택 훅 (알림센터 ingest 연결용)
 * @returns runStatus·노드 상태·타임라인·최종 리포트·연결 상태를 담은 반응형 상태 객체
 */
export function useEventStream(onEvent?: EventHook): EventStreamState {
  const runStatus = ref<RunStatus>("IDLE");
  const nodes = reactive<Record<NodeKey, NodeStatus>>(initialNodes());
  const timeline = ref<TimelineEntry[]>([]);
  const reportMarkdown = ref<string | null>(null);
  const keyActions = ref<KeyActionData[]>([]);
  const keyActionsTotal = ref(0);
  const connected = ref(false);

  let source: EventSource | null = null;

  /**
   * 노드 상태 전이를 적용한다. 전이표에 없는 순서는 무시하고 콘솔 경고만 남긴다 (api-spec 2-2 순서 보장 5).
   *
   * @param key 전이 대상 노드 키
   * @param next 전이할 노드 상태
   * @param allowedFrom 전이가 허용되는 현재 상태 목록
   */
  function transition(key: NodeKey, next: NodeStatus, allowedFrom: NodeStatus[]): void {
    const current = nodes[key];
    if (!allowedFrom.includes(current)) {
      console.warn(
        `[useEventStream] out-of-order transition ignored: ${key} ${current} -> ${next}`,
      );
      return;
    }
    nodes[key] = next;
  }

  /**
   * 수신 이벤트 1건을 타임라인에 쌓고 상태머신 전이를 수행한다.
   *
   * @param event api-spec 2-1의 이벤트 타입명
   * @param data 이벤트 data payload (seq·ts 공통 필드 포함)
   */
  function apply<E extends EventName>(event: E, data: EventDataMap[E]): void {
    // sensor_update는 고빈도 텔레메트리라 타임라인에 쌓지 않는다 (센서 패널이 전용 뷰)
    if (event !== "sensor_update") {
      timeline.value = [...timeline.value, { event, data }];
    }

    switch (event) {
      case "run_start": {
        runStatus.value = "RUNNING";
        for (const key of NODE_KEYS) nodes[key] = "PENDING";
        timeline.value = [{ event, data }];
        reportMarkdown.value = null;
        keyActions.value = [];
        keyActionsTotal.value = 0;
        break;
      }
      case "routing_decision": {
        const decision = data as EventDataMap["routing_decision"];
        transition("routing", "DONE", ["PENDING", "RUNNING"]);
        for (const agent of AGENT_NAMES) {
          // report/supervisor_validation은 target_agents에 실리지 않는 고정 조립·검증 단계라 제외한다
          if (agent === "report" || agent === "supervisor_validation") continue;
          if (!decision.target_agents.includes(agent)) nodes[agent] = "SKIPPED";
        }
        break;
      }
      case "agent_start": {
        const agent = (data as EventDataMap["agent_start"]).agent;
        transition(agent, "RUNNING", ["PENDING"]);
        break;
      }
      case "agent_end": {
        const agent = (data as EventDataMap["agent_end"]).agent;
        transition(agent, "DONE", ["RUNNING"]);
        break;
      }
      case "error": {
        const err = data as EventDataMap["error"];
        if (err.agent !== null) transition(err.agent, "FAILED", ["PENDING", "RUNNING"]);
        break;
      }
      case "run_end": {
        const end = data as EventDataMap["run_end"];
        runStatus.value = end.status === "done" ? "DONE" : "FAILED";
        reportMarkdown.value = end.report_markdown;
        keyActions.value = end.key_actions ?? [];
        keyActionsTotal.value = end.key_actions_total ?? 0;
        // RUNNING으로 남은 노드가 있으면 FAILED 처리 (api-spec 2-2 전이표)
        for (const key of NODE_KEYS) {
          if (nodes[key] === "RUNNING") nodes[key] = "FAILED";
        }
        break;
      }
      default:
        break;
    }

    onEvent?.(event, data);
  }

  /**
   * EventSource를 생성하고 api-spec 2-1의 모든 이벤트 타입 리스너를 등록한다.
   */
  function connect(): void {
    source = new EventSource("/events");
    source.onopen = () => {
      connected.value = true;
    };
    source.onerror = () => {
      // EventSource가 Last-Event-ID를 포함해 자동 재접속한다 (서버가 buffer replay 담당)
      connected.value = false;
    };
    for (const name of EVENT_NAMES) {
      source.addEventListener(name, (raw: MessageEvent<string>) => {
        try {
          apply(name, JSON.parse(raw.data));
        } catch (parseError) {
          console.warn(`[useEventStream] invalid event payload: ${name}`, parseError);
        }
      });
    }
  }

  onMounted(connect);
  onBeforeUnmount(() => {
    source?.close();
    source = null;
  });

  return { runStatus, nodes, timeline, reportMarkdown, keyActions, keyActionsTotal, connected };
}

/**
 * 모든 노드를 PENDING으로 초기화한 상태 맵을 만든다.
 *
 * @returns Routing + Worker 5종 노드의 초기 상태 맵
 */
function initialNodes(): Record<NodeKey, NodeStatus> {
  return Object.fromEntries(NODE_KEYS.map((key) => [key, "PENDING"])) as Record<
    NodeKey,
    NodeStatus
  >;
}
