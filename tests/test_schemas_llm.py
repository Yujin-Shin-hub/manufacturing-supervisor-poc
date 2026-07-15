"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: 단계 2 schemas.py 및 llm.py JSON 검증 래퍼 테스트
변경 이력:
  - 2026-07-06: 단계 2 RoutingDecision, AgentResult, LLM provider/복구 테스트 추가
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src import llm
from src.schemas import AgentResult, RoutingDecision


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def create(self, **kwargs) -> FakeResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake LLM responses left")
        return FakeResponse(self.responses.pop(0))


class FakeChat:
    def __init__(self, responses: list[str]) -> None:
        self.completions = FakeCompletions(responses)


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.chat = FakeChat(responses)


def test_routing_decision_validates_agent_names_and_duplicates() -> None:
    decision = RoutingDecision.model_validate(
        {
            "target_agents": ["risk_alert", "dispatching"],
            "execution_order": "sequential",
            "reason": "위험 작업의 대체 설비를 묻고 있음",
        }
    )

    assert decision.target_agents == ["risk_alert", "dispatching"]

    with pytest.raises(ValidationError):
        RoutingDecision.model_validate(
            {
                "target_agents": ["risk_alert", "risk_alert"],
                "execution_order": "sequential",
                "reason": "중복 에이전트",
            }
        )


def test_agent_result_validates_common_worker_contract() -> None:
    result = AgentResult.model_validate(
        {
            "agent": "dispatching",
            "summary": "SCH-0003은 ETCH-102 대체 배정을 권고합니다.",
            "evidence_tables": {"actions": "| schedule_id |"},
            "alerts": ["SCH-0003 CRITICAL"],
            "tool_calls_used": ["build_reschedule_actions"],
        }
    )

    assert result.agent == "dispatching"

    with pytest.raises(ValidationError):
        AgentResult.model_validate(
            {
                "agent": "unknown",
                "summary": "허용되지 않은 agent",
            }
        )


def test_complete_json_uses_json_object_temperature_zero_and_validates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeClient(
        [
            (
                '{"target_agents":["field_status"],'
                '"execution_order":"sequential","reason":"상태 질문"}'
            )
        ]
    )

    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_BASE_URL", "http://test.local/v1")
    monkeypatch.setenv("QWEN_MODEL_NAME", "qwen-test")
    monkeypatch.setattr(llm, "_client", lambda config: fake_client)

    result = llm.complete_json("route this", RoutingDecision)

    assert result.target_agents == ["field_status"]
    call = fake_client.chat.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["temperature"] == 0
    assert call["model"] == "qwen-test"


def test_complete_json_retries_once_after_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeClient(
        [
            '{"target_agents":["unknown"],"execution_order":"sequential","reason":"x"}',
            (
                '{"target_agents":["risk_alert"],'
                '"execution_order":"sequential","reason":"위험 질문"}'
            ),
        ]
    )

    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_BASE_URL", "http://test.local/v1")
    monkeypatch.setenv("QWEN_MODEL_NAME", "qwen-test")
    monkeypatch.setattr(llm, "_client", lambda config: fake_client)

    result = llm.complete_json("route this", RoutingDecision)

    assert result.target_agents == ["risk_alert"]
    assert len(fake_client.chat.completions.calls) == 2
    repair_message = fake_client.chat.completions.calls[1]["messages"][1]["content"]
    assert "failed validation" in repair_message


def test_auto_provider_falls_back_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeClient(
        [
            (
                '{"target_agents":["dispatching"],'
                '"execution_order":"sequential","reason":"대체 설비 질문"}'
            )
        ]
    )

    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("QWEN_API_KEY", "")
    monkeypatch.setenv("QWEN_BASE_URL", "")
    monkeypatch.setenv("QWEN_MODEL_NAME", "")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://test.local/v1")
    monkeypatch.setenv("OPENAI_MODEL_NAME", "openai-test")
    monkeypatch.setattr(llm, "_client", lambda config: fake_client)

    completion = llm.complete_json_result("route this", RoutingDecision)

    assert completion.active_provider == "openai"
    assert completion.fallback_used is True
    assert completion.model_name == "openai-test"
    assert completion.result.target_agents == ["dispatching"]
