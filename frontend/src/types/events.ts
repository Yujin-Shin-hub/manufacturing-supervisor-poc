/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: SSE 이벤트·상태 타입 정의 — docs/api-spec.md 2장과 1:1 유지 (스펙 변경 없이 타입만 변경 금지)
 * 변경 이력:
 *   - 2026-07-07: 단계 8 최초 작성 (api-spec.md 2-1 이벤트 표·2-2 상태 정의 기준)
 *   - 2026-07-07: action_proposed에 original_machine·impact·efficiency_gain 추가 (api-spec 2-1 동시 갱신)
 *   - 2026-07-14: run_end에 key_actions/key_actions_total 추가 — 리포트 드로어 고정 컴포넌트용
 *                 구조화 핵심 추천 액션 (api-spec 2-1 동시 갱신)
 *   - 2026-07-14: 단계 10 MQTT 센서 스트림 — sensor_update/sensor_alert 이벤트 타입 추가
 *   - 2026-07-16: 단계 11 자동 트리거 — auto_run_triggered 이벤트, run_start mode "auto" 추가
 */

/** api-spec 2-1: agent 값은 다음 다섯 개만 허용 */
export type AgentName =
  | "field_status"
  | "risk_alert"
  | "delay_pred"
  | "dispatching"
  | "scheduling_policy"
  | "supervisor_validation"
  | "report";

export const AGENT_NAMES: readonly AgentName[] = [
  "field_status",
  "risk_alert",
  "delay_pred",
  "dispatching",
  "scheduling_policy",
  "supervisor_validation",
  "report",
] as const;

/** api-spec 2-1: tool 값은 src/tools에 실존하는 함수명만 */
export type ToolName =
  | "score_delay_risk"
  | "find_machine_candidates"
  | "build_reschedule_actions"
  | "summarize_status"
  | "df_to_markdown";

/** api-spec 2: 모든 data에 포함되는 공통 필드 */
export interface EventDataBase {
  seq: number;
  ts: string;
}

export interface RunStartData extends EventDataBase {
  /** "auto"는 단계 11 센서 자동 트리거 전용 — 타임라인에 "자동 실행" 배지로 구분 표시 */
  mode: "ask" | "report" | "auto";
  asof: string;
  query?: string | null;
}

export interface LlmProviderSelectedData extends EventDataBase {
  requested_provider: string;
  active_provider: string;
  fallback_used: boolean;
  model_name: string;
}

export interface RoutingDecisionData extends EventDataBase {
  target_agents: AgentName[];
  execution_order: "sequential";
  reason: string;
}

export interface AgentStartData extends EventDataBase {
  agent: AgentName;
}

export interface ToolCallData extends EventDataBase {
  agent: AgentName;
  tool: ToolName;
  rows: number;
}

export interface AgentEndData extends EventDataBase {
  agent: AgentName;
  summary: string;
  alerts: string[];
}

export interface ActionProposedData extends EventDataBase {
  action_id: string;
  schedule_id: string;
  risk_level: string;
  original_machine: string;
  alternative_machine: string;
  impact: string;
  efficiency_gain: number | null;
  expected_delay_reduction_hr: number | null;
  expected_remaining_delay_hr: number | null;
  historical_acceptance_rate: number | null;
  historical_sample_count: number | null;
  historical_avg_efficiency_gain: number | null;
  quality_risk_count: number | null;
  quality_risk_rate: number | null;
  policy_score: number | null;
  policy_decision_reason: string | null;
  expected_effect: string | null;
  quality_history_note: string | null;
  approval_required: boolean;
}

export interface ApprovalRequiredData extends EventDataBase {
  action_id: string;
  schedule_id: string;
  risk_level: string;
  required_response: string;
}

export interface ActionAcceptedData extends EventDataBase {
  action_id: string;
  schedule_id: string;
  supervisor_id: string;
}

export interface ActionRejectedData extends EventDataBase {
  action_id: string;
  schedule_id: string;
  reject_reason: string;
  reproposal_available: boolean;
}

export interface ActionReproposedData extends EventDataBase {
  previous_action_id: string;
  schedule_id: string;
  alternative_machine: string;
  candidate_rank: number;
}

export interface ActionEscalatedData extends EventDataBase {
  action_id: string;
  schedule_id: string;
  escalation_level: string;
  escalation_reason: string;
}

/** api-spec 2-1 단계 10: MQTT factory/# payload 검증 후 발행되는 센서 측정값 1건 */
export interface SensorUpdateData extends EventDataBase {
  line: string;
  sensor: string;
  value: number;
  unit: string;
  observed_ts: string;
}

/** api-spec 2-1 단계 10: 동일 라인·센서 60초 내 3회 연속 임계 초과 알림 (판정은 서버 코드) */
export interface SensorAlertData extends EventDataBase {
  line: string;
  sensor: string;
  rule: string;
  values: number[];
  unit: string;
}

/** api-spec 2-1 단계 11: sensor_alert가 쿨다운을 통과해 Supervisor 자동 실행이 시작될 때 */
export interface AutoRunTriggeredData extends EventDataBase {
  cause: "sensor_alert";
  line: string;
  query: string;
}

export interface ErrorData extends EventDataBase {
  agent: AgentName | null;
  message: string;
  recoverable: boolean;
}

/** run_end.key_actions 1건 — dispatching 근거 표 상위 추천의 구조화 데이터 (api-spec 2-1) */
export interface KeyActionData {
  rank: number;
  action_id: string | null;
  schedule_id: string;
  original_machine: string | null;
  alternative_machine: string | null;
  risk_level: string | null;
  impact: string | null;
  estimated_delay_hr: number | null;
  expected_delay_reduction_hr: number | null;
  expected_remaining_delay_hr: number | null;
  historical_acceptance_rate: number | null;
  historical_sample_count: number | null;
  policy_score: number | null;
  expected_effect: string | null;
  quality_history_note: string | null;
}

export interface RunEndData extends EventDataBase {
  status: "done" | "failed";
  report_markdown: string | null;
  key_actions: KeyActionData[] | null;
  key_actions_total: number | null;
}

/** api-spec 2-1 이벤트 표의 event 타입명 ↔ data 스키마 매핑 */
export interface EventDataMap {
  run_start: RunStartData;
  llm_provider_selected: LlmProviderSelectedData;
  routing_decision: RoutingDecisionData;
  agent_start: AgentStartData;
  tool_call: ToolCallData;
  agent_end: AgentEndData;
  action_proposed: ActionProposedData;
  approval_required: ApprovalRequiredData;
  action_accepted: ActionAcceptedData;
  action_rejected: ActionRejectedData;
  action_reproposed: ActionReproposedData;
  action_escalated: ActionEscalatedData;
  sensor_update: SensorUpdateData;
  sensor_alert: SensorAlertData;
  auto_run_triggered: AutoRunTriggeredData;
  error: ErrorData;
  run_end: RunEndData;
}

export type EventName = keyof EventDataMap;

export const EVENT_NAMES: readonly EventName[] = [
  "run_start",
  "llm_provider_selected",
  "routing_decision",
  "agent_start",
  "tool_call",
  "agent_end",
  "action_proposed",
  "approval_required",
  "action_accepted",
  "action_rejected",
  "action_reproposed",
  "action_escalated",
  "sensor_update",
  "sensor_alert",
  "auto_run_triggered",
  "error",
  "run_end",
] as const;

/** 타임라인에 쌓이는 수신 이벤트 1건 (원문 payload 보존) */
export interface TimelineEntry {
  event: EventName;
  data: EventDataMap[EventName];
}

/** api-spec 2-2: Run 상태 (전역 1개) */
export type RunStatus = "IDLE" | "RUNNING" | "DONE" | "FAILED";

/** api-spec 2-2: 노드 상태 (Routing + Worker/검증/리포트, 각각 독립) */
export type NodeStatus = "PENDING" | "RUNNING" | "DONE" | "FAILED" | "SKIPPED";

/** 아키텍처 뷰 노드 키: Routing 노드 + Worker/검증/리포트 */
export type NodeKey = "routing" | AgentName;

export const NODE_KEYS: readonly NodeKey[] = ["routing", ...AGENT_NAMES] as const;
