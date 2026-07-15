"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: pydantic 스키마 — RoutingDecision, AgentResult, Report 등 에이전트 간 계약
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성
  - 2026-07-06: 단계 2 RoutingDecision, AgentResult, Report 검증 스키마 구현
  - 2026-07-06: 단계 4 Worker LLM 서술용 WorkerNarrative 스키마 추가
  - 2026-07-14: 대시보드 리포트 A안 — 핵심 추천 액션 구조화 KeyAction 스키마 추가,
                Report에 key_actions/key_actions_total 필드 추가 (api-spec 2-1 run_end 동시 갱신)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


AgentName = Literal[
    "field_status",
    "risk_alert",
    "delay_pred",
    "dispatching",
    "scheduling_policy",
    "supervisor_validation",
    "report",
]

WorkerAgentName = Literal[
    "field_status",
    "risk_alert",
    "delay_pred",
    "dispatching",
    "scheduling_policy",
]

ExecutionOrder = Literal["sequential"]


class StrictModel(BaseModel):
    """공통 pydantic 설정."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RoutingDecision(StrictModel):
    """Routing Agent가 선택한 Worker 목록과 실행 순서."""

    target_agents: list[WorkerAgentName] = Field(min_length=1)
    execution_order: ExecutionOrder = "sequential"
    reason: str = Field(min_length=1)

    @field_validator("target_agents")
    @classmethod
    def reject_duplicate_agents(
        cls, target_agents: list[WorkerAgentName]
    ) -> list[WorkerAgentName]:
        if len(target_agents) != len(set(target_agents)):
            raise ValueError("target_agents must not contain duplicates")
        return target_agents


class AgentResult(StrictModel):
    """Worker Agent 공통 산출물."""

    agent: AgentName
    summary: str = Field(min_length=1)
    evidence_tables: dict[str, str] = Field(default_factory=dict)
    alerts: list[str] = Field(default_factory=list)
    tool_calls_used: list[str] = Field(default_factory=list)

    @field_validator("evidence_tables")
    @classmethod
    def reject_empty_evidence_keys(
        cls, evidence_tables: dict[str, str]
    ) -> dict[str, str]:
        for key, value in evidence_tables.items():
            if not key.strip():
                raise ValueError("evidence_tables keys must be non-empty")
            if not value.strip():
                raise ValueError("evidence_tables values must be non-empty")
        return evidence_tables


class WorkerNarrative(StrictModel):
    """Worker가 tool 결과를 바탕으로 생성하는 서술 문구."""

    summary: str = Field(min_length=1)
    alerts: list[str] = Field(default_factory=list)


class KeyAction(StrictModel):
    """리포트 상단 핵심 추천 액션 1건 — dispatching 근거 표에서 코드가 추출한 구조화 데이터.

    모든 수치는 tool 산출값을 그대로 옮긴 것이며 (파싱 실패 시 None),
    대시보드 드로어의 고정 컴포넌트와 markdown 스냅샷 표가 같은 원천을 사용한다.
    """

    rank: int = Field(ge=1)
    action_id: str | None = None
    schedule_id: str = Field(min_length=1)
    original_machine: str | None = None
    alternative_machine: str | None = None
    risk_level: str | None = None
    impact: str | None = None
    estimated_delay_hr: float | None = None
    expected_delay_reduction_hr: float | None = None
    expected_remaining_delay_hr: float | None = None
    historical_acceptance_rate: float | None = None
    historical_sample_count: int | None = None
    policy_score: float | None = None
    expected_effect: str | None = None
    quality_history_note: str | None = None


class Report(StrictModel):
    """Supervisor 최종 리포트 산출물."""

    title: str = Field(min_length=1)
    asof: str = Field(min_length=1)
    sections: list[AgentResult] = Field(default_factory=list)
    report_markdown: str = Field(min_length=1)
    key_actions: list[KeyAction] = Field(default_factory=list)
    key_actions_total: int = Field(default=0, ge=0)
