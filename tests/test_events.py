"""
작성자: 신유진
작성일: 2026-07-06
작성 목적: 단계 6 EventBus 및 Supervisor 이벤트 발행 검증
변경 이력:
  - 2026-07-06: EventBus buffer/replay, Supervisor report 이벤트 순서 테스트 추가
"""

from __future__ import annotations

import pytest

from src.events import EventBus
from src.schemas import AgentResult
from src.supervisor import Supervisor


ASOF = "2026-04-15 14:00"


def _result(agent: str) -> AgentResult:
    return AgentResult.model_validate(
        {
            "agent": agent,
            "summary": f"{agent} summary",
            "evidence_tables": {"evidence": "| schedule_id |\n| --- |\n| SCH-0003 |"},
            "alerts": [],
            "tool_calls_used": ["test_tool"],
        }
    )


def test_event_bus_publishes_buffers_and_replays() -> None:
    bus = EventBus()
    received = []

    bus.subscribe(received.append)
    first = bus.publish("run_start", mode="report", asof=ASOF, query=None)
    second = bus.publish("run_end", status="done", report_markdown="# report\n")

    assert [event.seq for event in received] == [1, 2]
    assert [event.seq for event in bus.events] == [1, 2]
    assert first.data["seq"] == 1
    assert second.data["status"] == "done"

    replayed = []
    bus.subscribe(replayed.append, replay_after_seq=1)

    assert [event.event for event in replayed] == ["run_end"]


def test_supervisor_report_mode_emits_ordered_events(monkeypatch: pytest.MonkeyPatch) -> None:
    bus = EventBus()
    supervisor = Supervisor(event_bus=bus)

    class FakeWorker:
        def __init__(self, agent: str) -> None:
            self.agent = agent

        def run(self, asof: str, query: str | None = None) -> AgentResult:
            return _result(self.agent)

    for agent_name in supervisor._workers:
        supervisor._workers[agent_name] = FakeWorker(agent_name)

    report = supervisor.run("report", ASOF)

    assert report.report_markdown
    assert [event.seq for event in bus.events] == list(range(1, len(bus.events) + 1))
    assert bus.events[0].event == "run_start"
    assert bus.events[1].event == "routing_decision"
    assert bus.events[-1].event == "run_end"
    assert bus.events[-1].data["status"] == "done"
    assert [
        event.data["agent"]
        for event in bus.events
        if event.event == "agent_start"
    ] == [
        "field_status",
        "risk_alert",
        "delay_pred",
        "dispatching",
        "scheduling_policy",
        "supervisor_validation",
        "report",
    ]
