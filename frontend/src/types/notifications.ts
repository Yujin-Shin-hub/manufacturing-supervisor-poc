/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: 알림센터·토스트·승인(HITL) 프론트 전용 타입 — SSE 이벤트에서 파생되는 표시용 모델
 *           (api-spec 2장 타입은 types/events.ts가 단일 소스이며 여기서는 참조만 한다)
 * 변경 이력:
 *   - 2026-07-07: 단계 8 알림 시스템 최초 작성
 *   - 2026-07-07: 재조정 제안 큐(ProposalItem) 추가 — "어디로 옮길지"를 전면에 보여주는 모델
 */

/** 알림 심각도 — info: 진행 정보, warning: 주의(경고·복구 가능 오류), critical: 즉시 대응 */
export type NotificationSeverity = "info" | "warning" | "critical";

/** 알림센터(벨 아이콘 패널)에 쌓이는 항목 1건. run이 바뀌어도 세션 내에서 유지된다 */
export interface NotificationItem {
  id: number;
  ts: string;
  severity: NotificationSeverity;
  title: string;
  detail: string;
  /** 승인 workflow와 연결된 알림이면 해당 action_id */
  actionId: string | null;
  read: boolean;
}

/** 우측 하단 토스트 1건. sticky=true면 자동 소멸하지 않는다 */
export interface ToastItem {
  id: number;
  severity: NotificationSeverity;
  title: string;
  detail: string;
  sticky: boolean;
}

/** 승인 대기 액션의 프론트 상태 */
export type ApprovalStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "EXPIRED";

/** approval_required 이벤트로 생성되는 HITL 대상 액션 */
export interface PendingApproval {
  actionId: string;
  scheduleId: string;
  riskLevel: string;
  requiredResponse: string;
  /** action_proposed에서 조인한 원 설비 (없으면 null) */
  originalMachine: string | null;
  /** action_proposed에서 조인한 대체 설비 (없으면 null) */
  alternativeMachine: string | null;
  expectedDelayReductionHr: number | null;
  expectedRemainingDelayHr: number | null;
  historicalAcceptanceRate: number | null;
  historicalSampleCount: number | null;
  expectedEffect: string | null;
  qualityHistoryNote: string | null;
  policyScore: number | null;
  policyDecisionReason: string | null;
  ts: string;
  status: ApprovalStatus;
  submitting: boolean;
  errorMessage: string | null;
}

/** 재조정 제안 큐 항목의 상태 — PROPOSED는 승인 불요 제안(정보성) */
export type ProposalStatus = "PENDING" | "PROPOSED" | "ACCEPTED" | "REJECTED" | "EXPIRED";

/** action_proposed 이벤트 1건 = 재조정 제안 큐 1행 ("SCH → 원설비 → 대체설비") */
export interface ProposalItem {
  actionId: string;
  scheduleId: string;
  riskLevel: string;
  originalMachine: string;
  alternativeMachine: string;
  impact: string;
  efficiencyGain: number | null;
  expectedDelayReductionHr: number | null;
  expectedRemainingDelayHr: number | null;
  historicalAcceptanceRate: number | null;
  historicalSampleCount: number | null;
  expectedEffect: string | null;
  qualityHistoryNote: string | null;
  policyScore: number | null;
  policyDecisionReason: string | null;
  approvalRequired: boolean;
  ts: string;
  status: ProposalStatus;
}

/** api-spec 1-4 reject_reason 허용값 (서버 계약과 1:1) */
export const REJECT_REASONS = [
  "machine_reserved",
  "operator_unavailable",
  "recipe_not_ready",
  "quality_risk",
  "setup_time_too_long",
  "priority_changed",
  "manual_override",
  "other",
] as const;

export type RejectReason = (typeof REJECT_REASONS)[number];

/** 거절 사유 표시 라벨 (api-spec 1-4 의미 표 기준) */
export const REJECT_REASON_LABEL: Record<RejectReason, string> = {
  machine_reserved: "후보 설비가 이미 예약됨",
  operator_unavailable: "작업자/교대 인력 부족",
  recipe_not_ready: "recipe·qualification 미준비",
  quality_risk: "품질/공정 리스크 우려",
  setup_time_too_long: "setup 시간이 길어 납기 대응 부적합",
  priority_changed: "납기/고객/생산 priority 변경",
  manual_override: "현장 판단 수동 override",
  other: "기타",
};
