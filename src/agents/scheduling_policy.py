"""
작성자  : 신유진
작성일  : 2026-07-14
작성 목적: scheduling_policy Worker — 과거 재조정 이력 기반 추천 정책 검증·기대효과 산출
변경 이력:
  - 2026-07-14: dispatching 추천 이후 policy_score·기대효과·이력 승인률 검증 Worker 추가
"""

from __future__ import annotations

from src.schemas import AgentResult
from src.tools.dispatching import build_reschedule_actions
from src.tools.formatting import df_to_markdown

from .base import BaseWorker


class SchedulingPolicyWorker(BaseWorker):
    """과거 재조정 이력과 현재 위험도를 합쳐 추천 정책을 검증한다."""

    name = "scheduling_policy"

    def run(self, asof: str, query: str | None = None) -> AgentResult:
        """policy_score와 기대효과가 포함된 재조정 추천 검증 결과를 반환한다."""
        actions = build_reschedule_actions(asof)
        if actions.empty:
            return AgentResult(
                agent=self.name,
                summary="재조정 정책 검증 대상 액션이 없습니다.",
                evidence_tables={"policy_review": "_No rows_"},
                alerts=[],
                tool_calls_used=["build_reschedule_actions", "df_to_markdown"],
            )

        policy_columns = [
            "schedule_id",
            "original_machine",
            "alternative_machine",
            "risk_level",
            "risk_score",
            "estimated_delay_hr",
            "expected_delay_reduction_hr",
            "expected_remaining_delay_hr",
            "efficiency_gain",
            "historical_acceptance_rate",
            "historical_sample_count",
            "historical_avg_efficiency_gain",
            "quality_risk_count",
            "quality_risk_rate",
            "policy_score",
            "policy_decision_reason",
            "expected_effect",
            "quality_history_note",
        ]
        evidence = actions[policy_columns].head(12)
        top = actions.iloc[0]
        alerts = [
            (
                f"{row.schedule_id}: {row.alternative_machine} 추천 기대효과 "
                f"{row.expected_delay_reduction_hr:.1f}h 완화, "
                f"policy_score={row.policy_score:.1f}, "
                f"이력 승인률={_rate_text(row.historical_acceptance_rate)}"
            )
            for row in actions.head(5).itertuples(index=False)
        ]
        summary = (
            f"{self._asof_text(asof)} 기준 {len(actions)}건의 재조정 추천을 정책 검증했습니다. "
            f"최우선 {top.schedule_id}는 예상 지연 {top.expected_delay_reduction_hr:.1f}h 완화, "
            f"잔여 지연 {top.expected_remaining_delay_hr:.1f}h, "
            f"policy_score {top.policy_score:.1f}입니다."
        )
        return AgentResult(
            agent=self.name,
            summary=summary,
            evidence_tables={"policy_review": df_to_markdown(evidence)},
            alerts=alerts,
            tool_calls_used=["build_reschedule_actions", "df_to_markdown"],
        )


def _rate_text(value: object) -> str:
    """승인률 표시용 문자열을 반환한다."""
    if value is None:
        return "이력 없음"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "이력 없음"
