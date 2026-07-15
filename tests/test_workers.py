"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: 단계 4 Worker 4종 단독 실행 및 AgentResult 계약 테스트
변경 이력:
  - 2026-07-06: field_status/risk_alert/delay_pred/dispatching Worker 테스트 추가
  - 2026-07-06: Worker LLM 서술 호출을 monkeypatch로 검증
  - 2026-07-06: Worker별 system prompt 전달 검증 추가
"""

from __future__ import annotations

from src.agents import (
    DelayPredWorker,
    DispatchingWorker,
    FieldStatusWorker,
    RiskAlertWorker,
)
from src.schemas import WorkerNarrative
from src.schemas import AgentResult


ASOF = "2026-04-15 14:00"


def _assert_agent_result(result: AgentResult, agent: str) -> None:
    assert result.agent == agent
    assert result.summary
    assert result.evidence_tables
    assert result.tool_calls_used


def _patch_worker_llm(monkeypatch) -> list[str]:
    prompts: list[str] = []
    system_prompts: list[str] = []

    def fake_complete_json(prompt, schema, **kwargs):
        prompts.append(prompt)
        system_prompts.append(kwargs["system_prompt"])
        assert schema is WorkerNarrative
        assert "tool_context" in prompt
        assert "Worker입니다" in kwargs["system_prompt"]
        assert "tool_context 안의 사실과 숫자만 사용" in kwargs["system_prompt"]
        return WorkerNarrative(
            summary="LLM summary",
            alerts=["LLM alert"],
        )

    monkeypatch.setattr("src.agents.base.complete_json", fake_complete_json)
    return prompts, system_prompts


def test_field_status_worker_returns_status_evidence_and_alerts(monkeypatch) -> None:
    prompts, system_prompts = _patch_worker_llm(monkeypatch)

    result = FieldStatusWorker().run(ASOF)

    _assert_agent_result(result, "field_status")
    assert result.summary == "LLM summary"
    assert result.alerts == ["LLM alert"]
    assert "field_status" in result.evidence_tables
    assert "SCH-0003" in result.evidence_tables["field_status"]
    assert "field_status Worker" in prompts[0]
    assert "field_status Worker" in system_prompts[0]


def test_risk_alert_worker_returns_high_critical_alerts(monkeypatch) -> None:
    prompts, system_prompts = _patch_worker_llm(monkeypatch)

    result = RiskAlertWorker().run(ASOF)

    _assert_agent_result(result, "risk_alert")
    assert result.summary == "LLM summary"
    assert result.alerts == ["LLM alert"]
    assert "risk" in result.evidence_tables
    assert "CRITICAL" in result.evidence_tables["risk"]
    assert "alert_style: 최대 3개" in prompts[0]
    assert "risk_score=" in prompts[0]
    assert "risk_alert Worker" in system_prompts[0]


def test_delay_pred_worker_returns_delay_prediction_evidence(monkeypatch) -> None:
    _, system_prompts = _patch_worker_llm(monkeypatch)

    result = DelayPredWorker().run(ASOF)

    _assert_agent_result(result, "delay_pred")
    assert result.summary == "LLM summary"
    assert result.alerts == ["LLM alert"]
    assert "delay_prediction" in result.evidence_tables
    assert "estimated_delay_hr" in result.evidence_tables["delay_prediction"]
    assert "delay_pred Worker" in system_prompts[0]


def test_dispatching_worker_returns_actions_and_machine_candidates(monkeypatch) -> None:
    _, system_prompts = _patch_worker_llm(monkeypatch)

    result = DispatchingWorker().run(ASOF)

    _assert_agent_result(result, "dispatching")
    assert result.summary == "LLM summary"
    assert result.alerts == ["LLM alert"]
    assert "reschedule_actions" in result.evidence_tables
    assert "machine_candidates" in result.evidence_tables
    assert "ETCH-102" in result.evidence_tables["machine_candidates"]
    assert "dispatching Worker" in system_prompts[0]


def test_worker_uses_fallback_when_llm_fails(monkeypatch) -> None:
    def raise_llm_error(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("src.agents.base.complete_json", raise_llm_error)

    result = RiskAlertWorker().run(ASOF)

    assert "HIGH/CRITICAL" in result.summary
    assert len(result.alerts) <= 3
    assert all("risk_score=" in alert for alert in result.alerts)
