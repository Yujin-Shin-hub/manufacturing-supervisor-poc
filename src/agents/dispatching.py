"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: dispatching Worker — 대체 설비·작업 순서 추천
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 4)
  - 2026-07-06: 단계 4 reschedule action/설비 후보 기반 AgentResult 구현
  - 2026-07-06: 단계 4 LLM 서술 생성 연결 및 fallback 유지
  - 2026-07-06: dispatching 전용 system prompt 분리
"""

from __future__ import annotations

import pandas as pd

from src.schemas import AgentResult
from src.tools.dispatching import build_reschedule_actions, find_machine_candidates
from src.tools.formatting import df_to_markdown

from .base import BaseWorker


DISPATCHING_SYSTEM_PROMPT = (
    "당신은 dispatching Worker입니다. "
    "재조정 액션, 대체 설비 후보, 작업 순서 변경 근거를 Supervisor가 승인 판단할 수 있게 요약하세요. "
    "대체 설비는 tool_context의 후보와 액션에 있는 항목만 말하고, 새로운 설비나 sequence를 만들지 마세요."
)


class DispatchingWorker(BaseWorker):
    """대체 설비·작업 순서 추천."""

    name = "dispatching"

    def run(self, asof: str, query: str | None = None) -> AgentResult:
        """재조정 액션과 설비 후보 근거를 담은 AgentResult를 만든다."""
        actions = build_reschedule_actions(asof)
        candidate_frames = []
        for process_step in actions["process_step"].drop_duplicates().tolist():
            candidates = find_machine_candidates(str(process_step)).copy()
            candidates.insert(0, "source_process_step", process_step)
            candidate_frames.append(candidates)

        candidates_df = (
            pd.concat(candidate_frames, ignore_index=True)
            if candidate_frames
            else pd.DataFrame()
        )

        action_evidence = actions[
            [
                "action_id",
                "schedule_id",
                "risk_id",
                "original_machine",
                "alternative_machine",
                "new_sequence",
                "action_type",
                "impact",
                "efficiency_gain",
                "expected_delay_reduction_hr",
                "expected_remaining_delay_hr",
                "historical_acceptance_rate",
                "historical_sample_count",
                "historical_avg_efficiency_gain",
                "quality_risk_count",
                "quality_risk_rate",
                "policy_score",
                "policy_decision_reason",
                "expected_effect",
                "quality_history_note",
                "process_step",
                "risk_level",
                "estimated_delay_hr",
                "delay_probability",
            ]
        ].head(12) if not actions.empty else actions

        candidate_columns = [
            "source_process_step",
            "machine_id",
            "qualified_yn",
            "preferred_rank",
            "setup_time_min",
            "machine_status",
            "current_load",
            "available_yn",
        ]
        candidate_evidence = (
            candidates_df[candidate_columns].head(12)
            if not candidates_df.empty
            else candidates_df
        )

        alerts = [
            (
                f"{row.schedule_id}는 {row.original_machine}에서 "
                f"{row.alternative_machine}로 설비대체를 권고합니다 "
                f"(new_sequence={row.new_sequence}, impact={row.impact}, "
                f"기대효과={row.expected_effect})."
            )
            for row in actions.head(8).itertuples(index=False)
        ]

        fallback_summary = (
            f"{self._asof_text(asof)} 기준 재조정 제안 {len(actions)}건을 생성했습니다. "
            "대체 설비는 qualified_yn=Y, 가동, available_yn=Y 후보로 제한했습니다."
        )
        narrative = self._narrate(
            prompt=(
                "dispatching Worker 서술을 생성하세요.\n"
                f"사용자 질문: {query or '(리포트 모드)'}\n"
                "tool_context:\n"
                f"- asof: {self._asof_text(asof)}\n"
                f"- action_count: {len(actions)}\n"
                "- candidate_rule: qualified_yn=Y, machine_status=가동, available_yn=Y, current_load<0.5\n"
                f"- alert_candidates: {alerts}\n"
                "JSON fields: summary, alerts"
            ),
            fallback_summary=fallback_summary,
            fallback_alerts=alerts,
            system_prompt=DISPATCHING_SYSTEM_PROMPT,
        )

        return AgentResult(
            agent=self.name,
            summary=narrative.summary,
            evidence_tables={
                "reschedule_actions": df_to_markdown(action_evidence),
                "machine_candidates": df_to_markdown(candidate_evidence),
            },
            alerts=narrative.alerts,
            tool_calls_used=[
                "build_reschedule_actions",
                "find_machine_candidates",
                "df_to_markdown",
                "complete_json",
            ],
        )
