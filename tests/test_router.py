"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: 단계 3 Routing Agent 프롬프트 조립, 라우팅 케이스, 실패 fallback 테스트
변경 이력:
  - 2026-07-06: 단계 3 라우터 테스트 추가
  - 2026-07-06: 한국어 라우팅 prompt 검증 문구 반영
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src import router
from src.schemas import RoutingDecision


def _decision(target_agents: list[str], reason: str = "테스트 라우팅") -> RoutingDecision:
    return RoutingDecision.model_validate(
        {
            "target_agents": target_agents,
            "execution_order": "sequential",
            "reason": reason,
        }
    )


@pytest.fixture
def captured_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []
    responses: Iterator[RoutingDecision] = iter(
        [
            _decision(["field_status"], "현장 상태 확인"),
            _decision(["risk_alert"], "위험 작업 확인"),
            _decision(["delay_pred"], "예상 지연 확인"),
            _decision(["dispatching"], "대체 설비 확인"),
            _decision(
                ["field_status", "risk_alert", "delay_pred", "dispatching"],
                "일일 리포트 생성",
            ),
            _decision(["risk_alert", "dispatching"], "위험과 재배정 동시 확인"),
        ]
    )

    def fake_complete_json(*args, **kwargs) -> RoutingDecision:
        calls.append({"args": args, "kwargs": kwargs})
        return next(responses)

    monkeypatch.setattr(router, "complete_json", fake_complete_json)
    return calls


def test_route_prompt_cases_from_agents_table(captured_calls: list[dict]) -> None:
    cases = [
        ("지금 공정구 상태 어때?", ["field_status"]),
        ("CRITICAL 리스크만 보여줘", ["risk_alert"]),
        ("예상 지연 시간이 큰 건 뭐야?", ["delay_pred"]),
        ("어느 설비로 바꿀 수 있어?", ["dispatching"]),
        (
            "오늘 리포트 줘",
            ["field_status", "risk_alert", "delay_pred", "dispatching"],
        ),
        ("위험 작업 찾고 대체 설비도 추천해줘", ["risk_alert", "dispatching"]),
    ]

    for query, expected_agents in cases:
        decision = router.route(query, provider="qwen")
        assert decision.target_agents == expected_agents
        assert decision.execution_order == "sequential"

    assert len(captured_calls) == 6
    first_call = captured_calls[0]
    assert first_call["args"][1] is RoutingDecision
    assert first_call["kwargs"]["provider"] == "qwen"
    assert first_call["kwargs"]["system_prompt"] == router.ROUTER_SYSTEM_PROMPT
    assert "Worker 카탈로그:" in first_call["args"][0]
    assert "지금 공정구 상태 어때?" in first_call["args"][0]


def test_route_empty_query_falls_back_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args, **kwargs) -> RoutingDecision:
        raise AssertionError("LLM should not be called for empty query")

    monkeypatch.setattr(router, "complete_json", fail_if_called)

    decision = router.route("   ")

    assert decision.target_agents == ["field_status"]
    assert "빈 요청" in decision.reason


def test_route_llm_empty_response_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_empty_response(*args, **kwargs) -> RoutingDecision:
        raise RuntimeError("LLM response content was empty")

    monkeypatch.setattr(router, "complete_json", raise_empty_response)

    decision = router.route("위험 작업 알려줘")

    assert decision.target_agents == ["field_status"]
    assert "실패" in decision.reason
