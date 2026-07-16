"""
작성자: 신유진
작성일: 2026-07-14
작성 목적: 단계 10 MQTT 센서 스트림 규칙 엔진과 SSE 이벤트 발행 검증
변경 이력:
  - 2026-07-14: sensor_update, sensor_alert 단위 테스트 추가
  - 2026-07-16: 단계 11 자동 트리거 테스트 추가 — 쿨다운, mode "auto", 수동 실행 중 폐기
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

import pytest

from src import router, server
from src.events import EventBus
from src.schemas import AgentResult, RoutingDecision
from src.sensors.rules import (
    AutoTriggerCooldown,
    SensorPayload,
    SensorRuleEngine,
    build_auto_query,
)
from src.sensors.subscriber import handle_sensor_payload
from src.supervisor import Supervisor


def _payload(value: float, ts: str = "2026-04-15T10:00:00") -> SensorPayload:
    return SensorPayload.model_validate(
        {
            "ts": ts,
            "line": "Line-2",
            "sensor": "temperature",
            "value": value,
            "unit": "C",
        }
    )


def test_sensor_rule_requires_three_consecutive_threshold_breaches() -> None:
    engine = SensorRuleEngine()

    assert engine.record(_payload(84.0, "2026-04-15T10:00:00")) is None
    assert engine.record(_payload(86.0, "2026-04-15T10:00:20")) is None
    alert = engine.record(_payload(88.0, "2026-04-15T10:00:40"))

    assert alert is not None
    assert alert.line == "Line-2"
    assert alert.sensor == "temperature"
    assert alert.rule == "3연속 초과"
    assert alert.values == [84.0, 86.0, 88.0]


def test_sensor_rule_resets_when_value_returns_to_normal() -> None:
    engine = SensorRuleEngine()

    assert engine.record(_payload(84.0, "2026-04-15T10:00:00")) is None
    assert engine.record(_payload(74.0, "2026-04-15T10:00:20")) is None
    assert engine.record(_payload(86.0, "2026-04-15T10:00:40")) is None
    assert engine.record(_payload(88.0, "2026-04-15T10:01:00")) is None


def test_handle_sensor_payload_publishes_update_and_alert_events() -> None:
    bus = EventBus()
    engine = SensorRuleEngine()

    for index, value in enumerate([84.0, 86.0, 88.0]):
        handle_sensor_payload(
            json.dumps(
                {
                    "ts": f"2026-04-15T10:00:{index * 20:02d}",
                    "line": "Line-2",
                    "sensor": "temperature",
                    "value": value,
                    "unit": "C",
                }
            ).encode("utf-8"),
            event_bus=bus,
            rules=engine,
        )

    assert [event.event for event in bus.events] == [
        "sensor_update",
        "sensor_update",
        "sensor_update",
        "sensor_alert",
    ]
    assert bus.events[-1].data["line"] == "Line-2"
    assert bus.events[-1].data["values"] == [84.0, 86.0, 88.0]


# ---------------------------------------------------------------------------
# 단계 11 — 센서 이상 → Supervisor 자동 트리거
# ---------------------------------------------------------------------------


def test_auto_trigger_cooldown_blocks_same_line_for_five_minutes() -> None:
    cooldown = AutoTriggerCooldown()
    t0 = datetime(2026, 4, 15, 10, 0, 0)

    assert cooldown.allow("Line-2", t0) is True
    assert cooldown.allow("Line-2", t0 + timedelta(seconds=299)) is False
    # 쿨다운은 라인별 독립이다
    assert cooldown.allow("Line-5", t0 + timedelta(seconds=10)) is True
    assert cooldown.allow("Line-2", t0 + timedelta(seconds=300)) is True


def test_build_auto_query_uses_fixed_template() -> None:
    assert build_auto_query("Line-2", "temperature") == (
        "Line-2 온도 이상. 지연 위험과 재배치 필요성 평가"
    )
    assert build_auto_query("Line-3", "throughput") == (
        "Line-3 처리량 급감. 지연 위험과 재배치 필요성 평가"
    )


def _fake_agent_result(agent: str) -> AgentResult:
    return AgentResult.model_validate(
        {
            "agent": agent,
            "summary": f"{agent} summary",
            "evidence_tables": {
                "evidence": "| schedule_id | risk_score |\n| --- | --- |\n| SCH-0003 | 100.0 |"
            },
            "alerts": [],
            "tool_calls_used": [],
        }
    )


def test_supervisor_auto_mode_routes_query_and_publishes_run_start_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_query = "Line-2 온도 이상. 지연 위험과 재배치 필요성 평가"

    def fake_route(query: str, *, provider: str | None = None) -> RoutingDecision:
        assert query == auto_query
        return RoutingDecision(
            target_agents=["risk_alert", "dispatching"],
            execution_order="sequential",
            reason="센서 이상 평가",
        )

    monkeypatch.setattr(router, "route", fake_route)

    def raise_llm_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("LLM disabled in sensor stream tests")

    monkeypatch.setattr("src.agents.base.complete_json", raise_llm_error)

    class FakeWorker:
        def __init__(self, agent: str) -> None:
            self.agent = agent

        def run(self, asof: str, query: str | None = None) -> AgentResult:
            return _fake_agent_result(self.agent)

    bus = EventBus()
    supervisor = Supervisor(event_bus=bus)
    for agent_name in supervisor._workers:
        supervisor._workers[agent_name] = FakeWorker(agent_name)

    supervisor.run("auto", "2026-04-15 14:00", query=auto_query)

    run_start = bus.events[0]
    assert run_start.event == "run_start"
    assert run_start.data["mode"] == "auto"
    assert run_start.data["query"] == auto_query
    assert bus.events[-1].event == "run_end"
    assert bus.events[-1].data["status"] == "done"


class _RecordingSupervisor:
    """server._maybe_auto_run 검증용 — Supervisor 호출 인자만 기록한다."""

    calls: list[tuple[str, str | None]] = []

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus

    def run(
        self,
        mode: str,
        asof: str,
        query: str | None = None,
        llm_provider: str | None = None,
    ) -> None:
        _RecordingSupervisor.calls.append((mode, query))


@pytest.fixture()
def auto_run_env(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingSupervisor]:
    """server 전역 상태를 테스트별로 격리하고 Supervisor 실행을 기록으로 대체한다."""
    _RecordingSupervisor.calls = []
    monkeypatch.setattr(server, "Supervisor", _RecordingSupervisor)
    monkeypatch.setattr(server, "auto_trigger_cooldown", AutoTriggerCooldown())
    monkeypatch.setattr(server, "run_state", server.RunState())
    monkeypatch.setattr(server, "event_bus", EventBus())
    return _RecordingSupervisor


def test_maybe_auto_run_executes_supervisor_in_auto_mode(
    auto_run_env: type[_RecordingSupervisor],
) -> None:
    asyncio.run(server._maybe_auto_run(line="Line-2", sensor="temperature"))

    assert auto_run_env.calls == [
        ("auto", "Line-2 온도 이상. 지연 위험과 재배치 필요성 평가")
    ]
    triggered = [e for e in server.event_bus.events if e.event == "auto_run_triggered"]
    assert len(triggered) == 1
    assert triggered[0].data["cause"] == "sensor_alert"
    assert triggered[0].data["line"] == "Line-2"
    assert server.run_state.running is False


def test_maybe_auto_run_discards_trigger_while_run_in_progress(
    auto_run_env: type[_RecordingSupervisor],
) -> None:
    server.run_state.running = True

    asyncio.run(server._maybe_auto_run(line="Line-2", sensor="temperature"))

    assert auto_run_env.calls == []
    assert [e.event for e in server.event_bus.events] == []
    # 폐기된 트리거는 쿨다운을 소모하지 않는다 — run 종료 후 재트리거 가능해야 한다
    server.run_state.running = False
    asyncio.run(server._maybe_auto_run(line="Line-2", sensor="temperature"))
    assert len(auto_run_env.calls) == 1


def test_maybe_auto_run_respects_line_cooldown(
    auto_run_env: type[_RecordingSupervisor],
) -> None:
    asyncio.run(server._maybe_auto_run(line="Line-2", sensor="temperature"))
    asyncio.run(server._maybe_auto_run(line="Line-2", sensor="temperature"))

    assert len(auto_run_env.calls) == 1
