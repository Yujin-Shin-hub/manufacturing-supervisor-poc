/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: 알림 시스템 상태 저장소 — SSE 이벤트를 알림·토스트·승인(HITL) 모델로 변환하고
 *           승인/거절 API(api-spec 1-4) 호출을 담당한다. run이 바뀌어도 알림 이력은 유지된다
 * 변경 이력:
 *   - 2026-07-07: 단계 8 알림 시스템 최초 작성
 *   - 2026-07-07: 재조정 제안 큐(proposals) 추가 — ActionQueue 패널의 데이터 소스
 *   - 2026-07-14: 나중에 처리(defer)가 모달 큐 전체를 보류하도록 변경 — 승인 12건이
 *                 연속 모달로 이어지던 문제 해소 (건들은 PENDING으로 제안 큐·알림센터에 유지)
 *   - 2026-07-14: 단계 10 sensor_alert 알림 연동 — 지속 이상 시 서버가 ~3초마다 재발행하므로
 *                 라인·센서별 60초 스로틀로 토스트·알림센터 스팸을 막는다 (카드 경고색은 매번 갱신)
 *   - 2026-07-16: 단계 11 auto_run_triggered 알림·토스트 추가 (서버 쿨다운이 재발행을 막는다)
 */
import { computed, ref, type ComputedRef, type Ref } from "vue";

import type { EventDataMap, EventName } from "../types/events";
import type {
  NotificationItem,
  NotificationSeverity,
  PendingApproval,
  ProposalItem,
  ProposalStatus,
  RejectReason,
  ToastItem,
} from "../types/notifications";

/** 단일 사용자 PoC의 고정 supervisor 식별자 (api-spec 1-4 예시와 동일 체계) */
const SUPERVISOR_ID = "SUP-001";

/** 토스트 자동 소멸 시간(ms). critical(sticky)은 적용되지 않는다 */
const TOAST_TTL_MS = 6000;

/** sensor_alert 알림 스로틀(ms) — 같은 라인·센서의 반복 alert는 이 간격으로만 알린다 */
const SENSOR_ALERT_THROTTLE_MS = 60_000;

export interface NotificationCenterState {
  items: Ref<NotificationItem[]>;
  toasts: Ref<ToastItem[]>;
  approvals: Ref<PendingApproval[]>;
  /** 현재 run의 재조정 제안 큐 (run_start 시 초기화) */
  proposals: Ref<ProposalItem[]>;
  unreadCount: ComputedRef<number>;
  pendingApprovalCount: ComputedRef<number>;
  panelOpen: Ref<boolean>;
  modalApproval: ComputedRef<PendingApproval | null>;
  ingest: (event: EventName, data: EventDataMap[EventName]) => void;
  pushAlert: (
    severity: NotificationSeverity,
    title: string,
    detail: string,
    dedupeKey: string,
  ) => void;
  togglePanel: () => void;
  closePanel: () => void;
  openApprovalModal: (actionId: string) => void;
  deferApproval: () => void;
  acceptAction: (actionId: string) => Promise<void>;
  rejectAction: (actionId: string, reason: RejectReason, comment: string) => Promise<void>;
  dismissToast: (toastId: number) => void;
}

/**
 * 알림센터·토스트·승인 모달의 반응형 상태와 HITL API 호출 함수를 제공한다.
 *
 * @return 알림 이력, 토스트 스택, 승인 대기 목록, 모달 큐 제어·승인/거절 함수를 담은 상태 객체
 */
export function useNotifications(): NotificationCenterState {
  const items = ref<NotificationItem[]>([]);
  const toasts = ref<ToastItem[]>([]);
  const approvals = ref<PendingApproval[]>([]);
  const proposals = ref<ProposalItem[]>([]);
  const panelOpen = ref(false);
  /** 중앙 모달에 띄울 action_id 큐 — 선두가 현재 모달 */
  const modalQueue = ref<string[]>([]);
  /** 라인/센서별 마지막 sensor_alert 알림 시각 — 스로틀 기준 */
  const sensorAlertNotifiedAt = new Map<string, number>();

  let nextId = 1;

  const unreadCount = computed(() => items.value.filter((item) => !item.read).length);
  const pendingApprovalCount = computed(
    () => approvals.value.filter((approval) => approval.status === "PENDING").length,
  );
  const modalApproval = computed<PendingApproval | null>(() => {
    const actionId = modalQueue.value[0];
    if (actionId === undefined) return null;
    return approvals.value.find((approval) => approval.actionId === actionId) ?? null;
  });

  /**
   * 알림센터 항목을 추가한다 (최신이 배열 앞).
   *
   * @param severity 알림 심각도
   * @param title 알림 제목 (한 줄)
   * @param detail 보조 설명
   * @param ts 이벤트 발생 시각 문자열
   * @param actionId 승인 workflow 연결 시 해당 action_id
   */
  function pushItem(
    severity: NotificationSeverity,
    title: string,
    detail: string,
    ts: string,
    actionId: string | null = null,
  ): void {
    items.value = [
      { id: nextId++, ts, severity, title, detail, actionId, read: false },
      ...items.value,
    ];
  }

  /**
   * 우측 하단 토스트를 띄운다. critical은 sticky로 수동 닫기 전까지 유지된다.
   *
   * @param severity 토스트 심각도
   * @param title 토스트 제목
   * @param detail 보조 설명
   */
  function pushToast(severity: NotificationSeverity, title: string, detail: string): void {
    const toast: ToastItem = {
      id: nextId++,
      severity,
      title,
      detail,
      sticky: severity === "critical",
    };
    toasts.value = [...toasts.value, toast];
    if (!toast.sticky) {
      window.setTimeout(() => dismissToast(toast.id), TOAST_TTL_MS);
    }
  }

  /**
   * 토스트를 스택에서 제거한다.
   *
   * @param toastId 제거할 토스트 id
   */
  function dismissToast(toastId: number): void {
    toasts.value = toasts.value.filter((toast) => toast.id !== toastId);
  }

  /**
   * 승인 대기 액션의 상태를 갱신한다. PENDING이 아닌 항목은 건드리지 않는다 (중복 이벤트 멱등 처리).
   * 제안 큐의 같은 액션도 함께 전이한다.
   *
   * @param actionId 대상 action_id
   * @param status 전이할 승인 상태
   */
  function resolveApproval(actionId: string, status: PendingApproval["status"]): void {
    const approval = approvals.value.find((entry) => entry.actionId === actionId);
    if (approval !== undefined && approval.status === "PENDING") {
      approval.status = status;
      approval.submitting = false;
      approval.errorMessage = null;
    }
    if (status !== "PENDING") updateProposal(actionId, status);
    modalQueue.value = modalQueue.value.filter((queued) => queued !== actionId);
  }

  /**
   * 제안 큐 항목의 상태를 갱신한다. 이미 응답된 항목은 건드리지 않는다 (멱등).
   *
   * @param actionId 대상 action_id
   * @param status 전이할 제안 상태
   */
  function updateProposal(actionId: string, status: ProposalStatus): void {
    const proposal = proposals.value.find((entry) => entry.actionId === actionId);
    if (proposal === undefined) return;
    if (proposal.status !== "PENDING" && proposal.status !== "PROPOSED") return;
    proposal.status = status;
  }

  /**
   * SSE 이벤트 1건을 알림·토스트·승인 상태로 반영한다. useEventStream의 onEvent 훅으로 호출된다.
   *
   * @param event api-spec 2-1의 이벤트 타입명
   * @param data 이벤트 data payload
   */
  function ingest(event: EventName, data: EventDataMap[EventName]): void {
    switch (event) {
      case "run_start": {
        // 이전 run의 미응답 승인은 기준시각이 바뀌어 더 이상 유효하지 않다 (api-spec 1-4 EXPIRED)
        for (const approval of approvals.value) {
          if (approval.status === "PENDING") approval.status = "EXPIRED";
        }
        // 제안 큐는 현재 run의 결론만 보여준다 (이력은 알림센터에 남는다)
        proposals.value = [];
        modalQueue.value = [];
        break;
      }
      case "agent_end": {
        const end = data as EventDataMap["agent_end"];
        if (end.alerts.length === 0) break;
        for (const alert of end.alerts) {
          pushItem("warning", `${end.agent} 경고`, alert, end.ts);
        }
        const extra = end.alerts.length > 1 ? ` 외 ${end.alerts.length - 1}건` : "";
        const firstAlert = end.alerts[0] ?? "";
        pushToast("warning", `${end.agent} 경고 ${end.alerts.length}건`, firstAlert + extra);
        break;
      }
      case "action_proposed": {
        const proposed = data as EventDataMap["action_proposed"];
        proposals.value = [
          ...proposals.value,
          {
            actionId: proposed.action_id,
            scheduleId: proposed.schedule_id,
            riskLevel: proposed.risk_level,
            originalMachine: proposed.original_machine,
            alternativeMachine: proposed.alternative_machine,
            impact: proposed.impact,
            efficiencyGain: proposed.efficiency_gain,
            expectedDelayReductionHr: proposed.expected_delay_reduction_hr,
            expectedRemainingDelayHr: proposed.expected_remaining_delay_hr,
            historicalAcceptanceRate: proposed.historical_acceptance_rate,
            historicalSampleCount: proposed.historical_sample_count,
            expectedEffect: proposed.expected_effect,
            qualityHistoryNote: proposed.quality_history_note,
            policyScore: proposed.policy_score,
            policyDecisionReason: proposed.policy_decision_reason,
            approvalRequired: proposed.approval_required,
            ts: proposed.ts,
            status: proposed.approval_required ? "PENDING" : "PROPOSED",
          },
        ];
        pushItem(
          "info",
          `재조정 제안 ${proposed.action_id}`,
          `${proposed.schedule_id} · ${proposed.original_machine} → ${proposed.alternative_machine} (${proposed.risk_level})`,
          proposed.ts,
          proposed.action_id,
        );
        // 승인이 필요한 제안은 곧바로 approval_required가 뒤따르므로 토스트는 생략한다
        if (!proposed.approval_required) {
          pushToast(
            "info",
            "재조정 액션 제안",
            `${proposed.schedule_id} · ${proposed.original_machine} → ${proposed.alternative_machine}`,
          );
        }
        break;
      }
      case "approval_required": {
        const required = data as EventDataMap["approval_required"];
        const proposal = proposals.value.find(
          (entry) => entry.actionId === required.action_id,
        );
        approvals.value = [
          {
            actionId: required.action_id,
            scheduleId: required.schedule_id,
            riskLevel: required.risk_level,
            requiredResponse: required.required_response,
            originalMachine: proposal?.originalMachine ?? null,
            alternativeMachine: proposal?.alternativeMachine ?? null,
            expectedDelayReductionHr: proposal?.expectedDelayReductionHr ?? null,
            expectedRemainingDelayHr: proposal?.expectedRemainingDelayHr ?? null,
            historicalAcceptanceRate: proposal?.historicalAcceptanceRate ?? null,
            historicalSampleCount: proposal?.historicalSampleCount ?? null,
            expectedEffect: proposal?.expectedEffect ?? null,
            qualityHistoryNote: proposal?.qualityHistoryNote ?? null,
            policyScore: proposal?.policyScore ?? null,
            policyDecisionReason: proposal?.policyDecisionReason ?? null,
            ts: required.ts,
            status: "PENDING",
            submitting: false,
            errorMessage: null,
          },
          ...approvals.value,
        ];
        pushItem(
          "critical",
          `승인 필요 ${required.action_id}`,
          `${required.schedule_id} · ${required.risk_level} · ${required.required_response}`,
          required.ts,
          required.action_id,
        );
        if (!modalQueue.value.includes(required.action_id)) {
          modalQueue.value = [...modalQueue.value, required.action_id];
        }
        break;
      }
      case "action_accepted": {
        const accepted = data as EventDataMap["action_accepted"];
        resolveApproval(accepted.action_id, "ACCEPTED");
        pushItem(
          "info",
          `${accepted.action_id} 승인 완료`,
          `${accepted.schedule_id} · ${accepted.supervisor_id}`,
          accepted.ts,
          accepted.action_id,
        );
        pushToast("info", `${accepted.action_id} 승인 완료`, accepted.schedule_id);
        break;
      }
      case "action_rejected": {
        const rejected = data as EventDataMap["action_rejected"];
        resolveApproval(rejected.action_id, "REJECTED");
        pushItem(
          "info",
          `${rejected.action_id} 거절`,
          `${rejected.schedule_id} · 사유 ${rejected.reject_reason}`,
          rejected.ts,
          rejected.action_id,
        );
        pushToast("info", `${rejected.action_id} 거절 처리`, rejected.reject_reason);
        break;
      }
      case "action_escalated": {
        const escalated = data as EventDataMap["action_escalated"];
        pushItem(
          "critical",
          `에스컬레이션 ${escalated.action_id}`,
          `${escalated.schedule_id} · ${escalated.escalation_reason}`,
          escalated.ts,
          escalated.action_id,
        );
        pushToast(
          "critical",
          "에스컬레이션 발생",
          `${escalated.action_id} · ${escalated.escalation_reason}`,
        );
        break;
      }
      case "sensor_alert": {
        const alert = data as EventDataMap["sensor_alert"];
        const throttleKey = `${alert.line}/${alert.sensor}`;
        const lastNotified = sensorAlertNotifiedAt.get(throttleKey) ?? 0;
        // 이상이 지속되면 rule 엔진이 ~3초마다 재발행한다 — 알림은 라인·센서당 60초에 1건만
        if (Date.now() - lastNotified < SENSOR_ALERT_THROTTLE_MS) break;
        sensorAlertNotifiedAt.set(throttleKey, Date.now());
        const valuesText = alert.values.join(" → ");
        pushItem(
          "critical",
          `센서 이상 · ${alert.line} ${alert.sensor}`,
          `${alert.rule}: ${valuesText} ${alert.unit}`,
          alert.ts,
        );
        pushToast(
          "critical",
          `${alert.line} ${alert.sensor} 임계 초과`,
          `${alert.rule} — ${valuesText} ${alert.unit}`,
        );
        break;
      }
      case "auto_run_triggered": {
        // 자동 트리거는 서버 쿨다운(라인당 5분)이 걸려 있어 별도 스로틀이 필요 없다
        const triggered = data as EventDataMap["auto_run_triggered"];
        pushItem(
          "warning",
          `자동 실행 · ${triggered.line}`,
          `${triggered.cause} → ${triggered.query}`,
          triggered.ts,
        );
        pushToast("warning", `${triggered.line} 자동 실행 시작`, triggered.query);
        break;
      }
      case "error": {
        const err = data as EventDataMap["error"];
        const severity: NotificationSeverity = err.recoverable ? "warning" : "critical";
        pushItem(severity, `오류 · ${err.agent ?? "supervisor"}`, err.message, err.ts);
        pushToast(
          severity,
          err.recoverable ? `${err.agent ?? "-"} 복구 가능 오류` : "실행 중단 오류",
          err.message,
        );
        break;
      }
      default:
        break;
    }
  }

  /** SSE 외 파생 알림(임계 초과 등)의 중복 발송 방지 키 집합 */
  const alertKeys = new Set<string>();

  /**
   * SSE 이벤트가 아닌 파생 조건(리스크 추이 임계 초과 등)으로 알림을 발송한다.
   * 같은 dedupeKey로는 세션당 1회만 발송한다.
   *
   * @param severity 알림 심각도
   * @param title 알림 제목
   * @param detail 보조 설명
   * @param dedupeKey 중복 발송 방지 키 (예: 임계 초과 구간의 시간 키)
   */
  function pushAlert(
    severity: NotificationSeverity,
    title: string,
    detail: string,
    dedupeKey: string,
  ): void {
    if (alertKeys.has(dedupeKey)) return;
    alertKeys.add(dedupeKey);
    const now = new Date();
    const ts =
      `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-` +
      `${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:` +
      `${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
    pushItem(severity, title, detail, ts);
    pushToast(severity, title, detail);
  }

  /**
   * 알림센터 패널을 토글한다. 열 때 모든 항목을 읽음 처리한다.
   */
  function togglePanel(): void {
    panelOpen.value = !panelOpen.value;
    if (panelOpen.value) {
      items.value = items.value.map((item) => ({ ...item, read: true }));
    }
  }

  /**
   * 알림센터 패널을 닫는다.
   */
  function closePanel(): void {
    panelOpen.value = false;
  }

  /**
   * 특정 승인 건을 중앙 모달 큐 선두로 올린다 (알림센터의 "검토" 버튼).
   *
   * @param actionId 검토할 action_id
   */
  function openApprovalModal(actionId: string): void {
    modalQueue.value = [actionId, ...modalQueue.value.filter((queued) => queued !== actionId)];
    panelOpen.value = false;
  }

  /**
   * 승인 모달 큐 전체를 보류한다 — 대기 건마다 모달이 연속으로 뜨지 않게 한 번에 닫는다.
   * 건들은 PENDING으로 남아 재조정 제안 큐·알림센터의 승인/검토 버튼으로 처리할 수 있다.
   */
  function deferApproval(): void {
    modalQueue.value = [];
  }

  /**
   * 승인/거절 API 호출 공통 처리 — submitting 표시, 실패 시 errorMessage 노출.
   *
   * @param actionId 대상 action_id
   * @param path API 경로 접미사 ("accept" | "reject")
   * @param body 요청 payload
   * @param resolved 성공 시 전이할 승인 상태
   */
  async function submitDecision(
    actionId: string,
    path: "accept" | "reject",
    body: Record<string, string>,
    resolved: PendingApproval["status"],
  ): Promise<void> {
    const approval = approvals.value.find((entry) => entry.actionId === actionId);
    if (approval === undefined || approval.status !== "PENDING" || approval.submitting) return;
    approval.submitting = true;
    approval.errorMessage = null;
    try {
      const response = await fetch(`/api/actions/${actionId}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
        approval.submitting = false;
        approval.errorMessage = detail?.detail ?? `HTTP ${response.status}`;
        return;
      }
      // 서버가 SSE action_accepted/rejected도 발행하지만, 연결 끊김 대비 즉시 반영한다 (멱등)
      resolveApproval(actionId, resolved);
    } catch (requestError) {
      approval.submitting = false;
      approval.errorMessage =
        requestError instanceof Error ? requestError.message : String(requestError);
    }
  }

  /**
   * 재조정 액션을 승인한다 (POST /api/actions/{id}/accept).
   *
   * @param actionId 승인할 action_id
   */
  async function acceptAction(actionId: string): Promise<void> {
    await submitDecision(
      actionId,
      "accept",
      { supervisor_id: SUPERVISOR_ID, comment: "dashboard에서 승인" },
      "ACCEPTED",
    );
  }

  /**
   * 재조정 액션을 거절한다 (POST /api/actions/{id}/reject).
   *
   * @param actionId 거절할 action_id
   * @param reason api-spec 1-4 reject_reason 허용값
   * @param comment 보조 코멘트 (빈 문자열 허용)
   */
  async function rejectAction(
    actionId: string,
    reason: RejectReason,
    comment: string,
  ): Promise<void> {
    await submitDecision(
      actionId,
      "reject",
      { supervisor_id: SUPERVISOR_ID, reject_reason: reason, comment },
      "REJECTED",
    );
  }

  return {
    items,
    toasts,
    approvals,
    proposals,
    unreadCount,
    pendingApprovalCount,
    panelOpen,
    modalApproval,
    ingest,
    pushAlert,
    togglePanel,
    closePanel,
    openApprovalModal,
    deferApproval,
    acceptAction,
    rejectAction,
    dismissToast,
  };
}
