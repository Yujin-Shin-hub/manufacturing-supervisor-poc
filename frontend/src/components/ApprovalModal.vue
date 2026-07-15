<!--
작성자  : 신유진
작성일  : 2026-07-07
작성 목적: 승인 필요(HITL) 중앙 모달 — CRITICAL/HIGH 재조정 액션의 승인·거절(사유 필수)·보류
변경 이력:
  - 2026-07-07: 단계 8 알림 시스템 최초 작성
-->
<script setup lang="ts">
import { ref, watch } from "vue";

import {
  REJECT_REASONS,
  REJECT_REASON_LABEL,
  type PendingApproval,
  type RejectReason,
} from "../types/notifications";

const props = defineProps<{
  approval: PendingApproval | null;
}>();

const emit = defineEmits<{
  accept: [actionId: string];
  reject: [actionId: string, reason: RejectReason, comment: string];
  defer: [];
}>();

const rejectMode = ref(false);
const rejectReason = ref<RejectReason>("machine_reserved");
const rejectComment = ref("");

watch(
  () => props.approval?.actionId,
  () => {
    rejectMode.value = false;
    rejectReason.value = "machine_reserved";
    rejectComment.value = "";
  },
);

/**
 * 거절 확정 — 선택된 사유·코멘트로 reject 이벤트를 올린다.
 */
function confirmReject(): void {
  if (props.approval === null) return;
  emit("reject", props.approval.actionId, rejectReason.value, rejectComment.value.trim());
}

function formatHours(value: number | null): string {
  return value === null ? "근거 없음" : `${value.toFixed(1)}h`;
}

function formatRate(value: number | null): string {
  return value === null ? "이력 없음" : `${Math.round(value * 100)}%`;
}

function formatScore(value: number | null): string {
  return value === null ? "-" : value.toFixed(1);
}
</script>

<template>
  <Transition name="modal">
    <div v-if="approval !== null" class="backdrop" role="dialog" aria-modal="true">
      <div class="modal">
        <header class="modal-head">
          <span class="risk-badge" :data-risk="approval.riskLevel">{{ approval.riskLevel }}</span>
          <h2 class="modal-title">재조정 액션 승인 필요</h2>
          <p class="modal-sub">supervisor 응답 전까지 이 액션은 적용되지 않습니다.</p>
        </header>

        <dl class="facts">
          <div class="fact">
            <dt>액션</dt>
            <dd class="mono">{{ approval.actionId }}</dd>
          </div>
          <div class="fact">
            <dt>스케줄</dt>
            <dd class="mono">{{ approval.scheduleId }}</dd>
          </div>
          <div v-if="approval.alternativeMachine !== null" class="fact fact-wide">
            <dt>설비 전환</dt>
            <dd class="mono transfer">
              <span v-if="approval.originalMachine !== null" class="from">{{
                approval.originalMachine
              }}</span>
              <span v-if="approval.originalMachine !== null" class="arrow" aria-label="에서">→</span>
              <span class="to">{{ approval.alternativeMachine }}</span>
            </dd>
          </div>
          <div class="fact fact-wide">
            <dt>요구 응답</dt>
            <dd>{{ approval.requiredResponse }}</dd>
          </div>
        </dl>

        <section class="effect-card" aria-label="기대효과">
          <div class="effect-head">
            <span>승인 시 기대효과</span>
            <strong>policy {{ formatScore(approval.policyScore) }}</strong>
          </div>
          <p class="effect-main">
            {{ approval.expectedEffect ?? "기대효과 근거가 없습니다." }}
          </p>
          <dl class="effect-metrics">
            <div>
              <dt>지연 완화</dt>
              <dd>{{ formatHours(approval.expectedDelayReductionHr) }}</dd>
            </div>
            <div>
              <dt>잔여 지연</dt>
              <dd>{{ formatHours(approval.expectedRemainingDelayHr) }}</dd>
            </div>
            <div>
              <dt>이력 승인률</dt>
              <dd>
                {{ formatRate(approval.historicalAcceptanceRate) }}
                <small v-if="approval.historicalSampleCount !== null">
                  n={{ approval.historicalSampleCount }}
                </small>
              </dd>
            </div>
          </dl>
          <p class="quality-note">{{ approval.qualityHistoryNote ?? "품질 이력 근거 없음" }}</p>
        </section>

        <p v-if="approval.errorMessage !== null" class="error-line">
          처리 실패: {{ approval.errorMessage }}
        </p>

        <div v-if="!rejectMode" class="actions">
          <button
            class="btn"
            :disabled="approval.submitting"
            @click="emit('accept', approval.actionId)"
          >
            {{ approval.submitting ? "처리 중…" : "승인" }}
          </button>
          <button class="btn btn--danger" :disabled="approval.submitting" @click="rejectMode = true">
            거절
          </button>
          <button class="btn btn--ghost defer" :disabled="approval.submitting" @click="emit('defer')">
            나중에 처리
          </button>
        </div>

        <div v-else class="reject-form">
          <label class="reject-field">
            <span>거절 사유</span>
            <select v-model="rejectReason" class="control">
              <option v-for="reason in REJECT_REASONS" :key="reason" :value="reason">
                {{ REJECT_REASON_LABEL[reason] }}
              </option>
            </select>
          </label>
          <label class="reject-field">
            <span>코멘트 (선택)</span>
            <input
              v-model="rejectComment"
              class="control"
              type="text"
              placeholder="예: 납기 우선이라 setup time 짧은 설비 필요"
            />
          </label>
          <div class="actions">
            <button class="btn btn--danger" :disabled="approval.submitting" @click="confirmReject">
              {{ approval.submitting ? "처리 중…" : "거절 확정" }}
            </button>
            <button class="btn btn--ghost" :disabled="approval.submitting" @click="rejectMode = false">
              뒤로
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(4, 8, 15, 0.72);
  backdrop-filter: blur(3px);
}
.modal {
  width: min(34rem, 100%);
  padding: 1.4rem 1.5rem 1.3rem;
  border: 1px solid var(--border-strong);
  border-top: 3px solid var(--status-critical);
  border-radius: 14px;
  background: var(--bg-panel);
  box-shadow: var(--shadow-float);
}
.modal-head {
  margin-bottom: 1rem;
}
.risk-badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 6px;
  background: var(--status-critical-soft);
  color: var(--status-critical-strong);
  font-size: 0.7rem;
  font-weight: 750;
  font-family: var(--font-mono);
  letter-spacing: 0.06em;
}
.risk-badge[data-risk="HIGH"] {
  background: var(--status-serious-soft);
  color: var(--status-serious);
}
.modal-title {
  margin: 0.55rem 0 0.2rem;
  font-size: 1.05rem;
  font-weight: 700;
}
.modal-sub {
  margin: 0;
  font-size: 0.78rem;
  color: var(--ink-dim);
}
.facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.55rem 1rem;
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-inset);
}
.effect-card {
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid color-mix(in srgb, var(--accent) 42%, var(--border));
  border-radius: 10px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--accent) 10%, var(--bg-inset)),
    var(--bg-inset)
  );
}
.effect-head {
  display: flex;
  justify-content: space-between;
  gap: 0.7rem;
  margin-bottom: 0.55rem;
  color: var(--ink);
  font-size: 0.78rem;
  font-weight: 750;
}
.effect-head strong {
  color: var(--accent-strong);
  font-family: var(--font-mono);
}
.effect-main {
  margin: 0 0 0.7rem;
  color: var(--ink);
  font-size: 0.86rem;
  line-height: 1.45;
}
.effect-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem;
  margin: 0;
}
.effect-metrics div {
  min-width: 0;
  padding: 0.5rem;
  border-radius: 8px;
  background: var(--bg-panel);
}
.effect-metrics dt {
  margin: 0 0 0.18rem;
  font-size: 0.66rem;
  color: var(--ink-dim);
}
.effect-metrics dd {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.86rem;
  color: var(--ink);
}
.effect-metrics small {
  color: var(--ink-dim);
}
.quality-note {
  margin: 0.65rem 0 0;
  font-size: 0.72rem;
  color: var(--ink-dim);
}
.fact-wide {
  grid-column: 1 / -1;
}
.fact dt {
  margin: 0 0 0.15rem;
  font-size: 0.68rem;
  letter-spacing: 0.05em;
  color: var(--ink-dim);
}
.fact dd {
  margin: 0;
  font-size: 0.85rem;
  color: var(--ink);
}
.mono {
  font-family: var(--font-mono);
}
.transfer .from {
  color: var(--ink-dim);
}
.transfer .arrow {
  margin: 0 0.35rem;
  color: var(--accent);
}
.transfer .to {
  font-weight: 750;
  color: var(--accent-strong);
}
.error-line {
  margin: 0 0 0.8rem;
  font-size: 0.78rem;
  color: var(--status-critical-strong);
}
.actions {
  display: flex;
  gap: 0.55rem;
}
.defer {
  margin-left: auto;
}
.reject-form {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}
.reject-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: var(--ink-sub);
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-active .modal,
.modal-leave-active .modal {
  transition: transform 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .modal {
  transform: translateY(0.6rem) scale(0.98);
}
@media (prefers-reduced-motion: reduce) {
  .modal-enter-active,
  .modal-leave-active,
  .modal-enter-active .modal,
  .modal-leave-active .modal {
    transition: none;
  }
}
</style>
