"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: field_status Worker — 공정군 작업·설비 상태 요약
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 4)
  - 2026-07-06: 단계 4 load_schedule/load_work_status 기반 AgentResult 구현
  - 2026-07-06: 단계 4 LLM 서술 생성 연결 및 fallback 유지
  - 2026-07-06: field_status 전용 system prompt 분리
"""

from __future__ import annotations

import pandas as pd

from src.schemas import AgentResult
from src.tools.formatting import df_to_markdown
from src.tools.loader import load_schedule, load_work_status

from .base import BaseWorker


FIELD_STATUS_SYSTEM_PROMPT = (
    "당신은 field_status Worker입니다. "
    "공정군의 현재 스케줄 상태, 설비 상태, 부하 이상을 현장 Supervisor가 바로 읽을 수 있게 요약하세요. "
    "위험 판단이나 대체 설비 추천은 하지 말고, 현재 상태와 확인이 필요한 항목만 말하세요."
)


class FieldStatusWorker(BaseWorker):
    """공정군 작업·설비 상태 요약."""

    name = "field_status"

    def run(self, asof: str, query: str | None = None) -> AgentResult:
        """schedule/work_status를 결합해 현장 상태 AgentResult를 만든다."""
        schedule = load_schedule()
        work_status = load_work_status()
        status = schedule.merge(work_status, on="schedule_id", how="left")
        status["is_delayed"] = status["status"] == "지연"
        status["is_stopped"] = status["machine_status"] == "정지"
        status["load_value"] = pd.to_numeric(status["current_load"], errors="coerce")
        status = status.sort_values(
            ["is_delayed", "is_stopped", "load_value", "priority", "due_date"],
            ascending=[False, False, False, True, True],
        ).reset_index(drop=True)

        total = len(status)
        delayed = int((status["status"] == "지연").sum())
        stopped = int((status["machine_status"] == "정지").sum())
        high_load = int(status["load_value"].ge(0.8).sum())

        evidence = status[
            [
                "schedule_id",
                "product",
                "priority",
                "due_date",
                "status",
                "process_step",
                "assigned_machine",
                "machine_status",
                "current_load",
                "operator",
            ]
        ].head(12)

        alerts = [
            (
                f"{row.schedule_id} {row.process_step} 작업은 "
                f"{row.assigned_machine} 설비 상태가 {row.machine_status}, "
                f"스케줄 상태가 {row.status}입니다."
            )
            for row in status[
                (status["status"] == "지연") | (status["machine_status"] == "정지")
            ].head(5).itertuples(index=False)
        ]

        fallback_summary = (
            f"{self._asof_text(asof)} 기준 {total}개 스케줄 중 "
            f"지연 {delayed}건, 설비 정지 {stopped}건, 부하 0.8 이상 {high_load}건입니다."
        )
        narrative = self._narrate(
            prompt=(
                "field_status Worker 서술을 생성하세요.\n"
                f"사용자 질문: {query or '(리포트 모드)'}\n"
                "tool_context:\n"
                f"- asof: {self._asof_text(asof)}\n"
                f"- total_schedules: {total}\n"
                f"- delayed_count: {delayed}\n"
                f"- stopped_machine_count: {stopped}\n"
                f"- high_load_count: {high_load}\n"
                f"- alert_candidates: {alerts}\n"
                "JSON fields: summary, alerts"
            ),
            fallback_summary=fallback_summary,
            fallback_alerts=alerts,
            system_prompt=FIELD_STATUS_SYSTEM_PROMPT,
        )

        return AgentResult(
            agent=self.name,
            summary=narrative.summary,
            evidence_tables={"field_status": df_to_markdown(evidence)},
            alerts=narrative.alerts,
            tool_calls_used=[
                "load_schedule",
                "load_work_status",
                "df_to_markdown",
                "complete_json",
            ],
        )
