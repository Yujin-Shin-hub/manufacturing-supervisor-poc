"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: delay_pred Worker — 지연 위험·예상 지연 판단
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 4)
  - 2026-07-06: 단계 4 score_delay_risk 결과 기반 예상 지연 AgentResult 구현
  - 2026-07-06: 단계 4 LLM 서술 생성 연결 및 fallback 유지
  - 2026-07-06: delay_pred 전용 system prompt 분리
"""

from __future__ import annotations

from src.schemas import AgentResult
from src.tools.formatting import df_to_markdown
from src.tools.risk import score_delay_risk

from .base import BaseWorker


DELAY_PRED_SYSTEM_PROMPT = (
    "당신은 delay_pred Worker입니다. "
    "지연 확률, 예상 지연 시간, 납기 근접 사유를 중심으로 지연 영향을 해석하세요. "
    "설비 대체안이나 작업 순서 재조정은 제안하지 말고 지연 판단에만 집중하세요."
)


class DelayPredWorker(BaseWorker):
    """지연 위험·예상 지연 판단."""

    name = "delay_pred"

    def run(self, asof: str, query: str | None = None) -> AgentResult:
        """예상 지연 시간과 지연 확률 중심의 AgentResult를 만든다."""
        risks = score_delay_risk(asof).sort_values(
            ["estimated_delay_hr", "delay_probability", "risk_score"],
            ascending=[False, False, False],
        )
        max_delay = 0.0 if risks.empty else float(risks.iloc[0]["estimated_delay_hr"])
        max_probability = 0.0 if risks.empty else float(risks.iloc[0]["delay_probability"])

        evidence = risks[
            [
                "schedule_id",
                "priority",
                "due_date",
                "days_to_due",
                "process_step",
                "risk_level",
                "delay_probability",
                "estimated_delay_hr",
                "impact_scope",
                "due_risk_reason",
            ]
        ].head(12)

        alerts = [
            (
                f"{row.schedule_id}는 예상 지연 {row.estimated_delay_hr}시간, "
                f"지연 확률 {row.delay_probability}로 {row.risk_level}입니다."
            )
            for row in risks.head(8).itertuples(index=False)
        ]

        fallback_summary = (
            f"{self._asof_text(asof)} 기준 지연 위험 {len(risks)}건 중 "
            f"최대 예상 지연은 {max_delay}시간, 최대 지연 확률은 {max_probability}입니다."
        )
        narrative = self._narrate(
            prompt=(
                "delay_pred Worker 서술을 생성하세요.\n"
                f"사용자 질문: {query or '(리포트 모드)'}\n"
                "tool_context:\n"
                f"- asof: {self._asof_text(asof)}\n"
                f"- risk_count: {len(risks)}\n"
                f"- max_estimated_delay_hr: {max_delay}\n"
                f"- max_delay_probability: {max_probability}\n"
                f"- alert_candidates: {alerts}\n"
                "JSON fields: summary, alerts"
            ),
            fallback_summary=fallback_summary,
            fallback_alerts=alerts,
            system_prompt=DELAY_PRED_SYSTEM_PROMPT,
        )

        return AgentResult(
            agent=self.name,
            summary=narrative.summary,
            evidence_tables={"delay_prediction": df_to_markdown(evidence)},
            alerts=narrative.alerts,
            tool_calls_used=["score_delay_risk", "df_to_markdown", "complete_json"],
        )
