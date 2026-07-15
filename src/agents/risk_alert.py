"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: risk_alert Worker — HIGH/CRITICAL 위험 알림
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 4)
  - 2026-07-06: 단계 4 score_delay_risk 기반 HIGH/CRITICAL AgentResult 구현
  - 2026-07-06: 단계 4 LLM 서술 생성 연결 및 fallback 유지
  - 2026-07-06: risk_alert 전용 system prompt 분리
"""

from __future__ import annotations

import pandas as pd

from src.schemas import AgentResult
from src.tools.formatting import df_to_markdown
from src.tools.risk import score_delay_risk

from .base import BaseWorker


RISK_ALERT_SYSTEM_PROMPT = (
    "당신은 risk_alert Worker입니다. "
    "HIGH/CRITICAL 위험 작업을 우선순위 있게 알리고, Supervisor가 즉시 봐야 할 리스크만 짧게 강조하세요. "
    "같은 표현을 반복하지 말고, 최대 3개의 서로 다른 리스크만 제시하세요. "
    "각 alert는 schedule_id, process_step, risk_level, 원인 1개를 포함하고, "
    "예상 지연 분석이나 대체 설비 추천은 다른 Worker 책임이므로 확장해서 말하지 마세요."
)


class RiskAlertWorker(BaseWorker):
    """HIGH/CRITICAL 위험 알림."""

    name = "risk_alert"

    def run(self, asof: str, query: str | None = None) -> AgentResult:
        """HIGH/CRITICAL 위험 작업 알림 AgentResult를 만든다."""
        risks = score_delay_risk(asof)
        critical_count = int((risks["risk_level"] == "CRITICAL").sum())
        high_count = int((risks["risk_level"] == "HIGH").sum())

        evidence = risks[
            [
                "schedule_id",
                "product",
                "priority",
                "due_date",
                "process_step",
                "assigned_machine",
                "risk_score",
                "risk_level",
                "risk_factor",
                "machine_status",
            ]
        ].head(12)

        alerts = self._build_alerts(risks)

        fallback_summary = (
            f"{self._asof_text(asof)} 기준 HIGH/CRITICAL 위험은 "
            f"총 {len(risks)}건입니다. CRITICAL {critical_count}건, HIGH {high_count}건입니다."
        )
        narrative = self._narrate(
            prompt=(
                "risk_alert Worker 서술을 생성하세요.\n"
                f"사용자 질문: {query or '(리포트 모드)'}\n"
                "tool_context:\n"
                f"- asof: {self._asof_text(asof)}\n"
                f"- total_high_critical: {len(risks)}\n"
                f"- critical_count: {critical_count}\n"
                f"- high_count: {high_count}\n"
                f"- alert_candidates: {alerts}\n"
                "- alert_style: 최대 3개, 중복 표현 금지, schedule_id별로 서로 다른 작업만 선택\n"
                "JSON fields: summary, alerts"
            ),
            fallback_summary=fallback_summary,
            fallback_alerts=alerts,
            system_prompt=RISK_ALERT_SYSTEM_PROMPT,
        )

        return AgentResult(
            agent=self.name,
            summary=narrative.summary,
            evidence_tables={"risk": df_to_markdown(evidence)},
            alerts=narrative.alerts,
            tool_calls_used=["score_delay_risk", "df_to_markdown", "complete_json"],
        )

    def _build_alerts(self, risks: pd.DataFrame) -> list[str]:
        """중복을 줄인 위험 알림 목록을 만든다.

        Args:
            risks: score_delay_risk 결과 DataFrame.

        Returns:
            서로 다른 schedule_id를 우선으로 최대 3개만 추린 알림 목록.
        """
        alerts: list[str] = []
        seen_schedules: set[str] = set()
        for row in risks.itertuples(index=False):
            if row.schedule_id in seen_schedules:
                continue
            seen_schedules.add(row.schedule_id)
            alerts.append(
                f"{row.schedule_id} {row.process_step} {row.risk_level} 위험: "
                f"risk_score={row.risk_score}, 원인={row.risk_factor}"
            )
            if len(alerts) >= 3:
                break
        return alerts
