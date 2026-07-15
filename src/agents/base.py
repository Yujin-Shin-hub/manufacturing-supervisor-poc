"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: Worker 공통 인터페이스 — run(asof, query) -> AgentResult
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 4)
  - 2026-07-06: 단계 4 Worker 공통 반환 타입과 asof 정규화 helper 추가
  - 2026-07-06: 단계 4 LLM 서술 생성 helper와 실패 fallback 추가
  - 2026-07-06: Worker별 system prompt를 받을 수 있도록 narrate 인자 확장
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.llm import complete_json
from src.schemas import AgentName, AgentResult, WorkerNarrative


WORKER_PROMPT_GUARDRAILS = (
    "반드시 제공된 tool_context 안의 사실과 숫자만 사용하세요. "
    "새로운 schedule_id, machine_id, risk_score, 시간, 수량을 만들지 마세요. "
    "evidence table은 재작성하지 말고 summary와 alerts 문구만 생성하세요. "
    "응답은 유효한 JSON만 반환하세요."
)


class BaseWorker(ABC):
    """역할별 Worker 공통 인터페이스."""

    name: AgentName = "field_status"

    @abstractmethod
    def run(self, asof: str, query: str | None = None) -> AgentResult:
        """AgentResult 를 반환. Worker 는 서로를 직접 호출하지 않는다."""
        raise NotImplementedError

    def _asof_text(self, asof: str) -> str:
        """사용자 표시용 기준시각 문자열을 정규화한다."""
        return pd.to_datetime(asof).strftime("%Y-%m-%d %H:%M")

    def _narrate(
        self,
        *,
        prompt: str,
        fallback_summary: str,
        fallback_alerts: list[str],
        system_prompt: str,
        provider: str | None = None,
    ) -> WorkerNarrative:
        """LLM으로 서술을 만들고 실패하면 결정적 fallback을 반환한다."""
        try:
            return complete_json(
                prompt,
                WorkerNarrative,
                provider=provider,
                system_prompt=f"{system_prompt} {WORKER_PROMPT_GUARDRAILS}",
            )
        except Exception:
            return WorkerNarrative(
                summary=fallback_summary,
                alerts=fallback_alerts,
            )
