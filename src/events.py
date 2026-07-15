"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: EventBus 로 실행 이벤트를 발행하고 콘솔 로거와 SSE가 공동 구독할 수 있게 한다.
변경 이력:
  - 2026-07-06: 단계 6 EventBus publish/subscribe, buffer replay, CLI console logger 구현
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from src.schemas import StrictModel


EventName = Literal[
    "run_start",
    "llm_provider_selected",
    "routing_decision",
    "agent_start",
    "tool_call",
    "agent_end",
    "action_proposed",
    "approval_required",
    "action_accepted",
    "action_rejected",
    "action_reproposed",
    "action_escalated",
    "sensor_update",
    "sensor_alert",
    "error",
    "run_end",
]


class EventRecord(StrictModel):
    """SSE data 공통 필드(seq, ts)를 포함한 개별 이벤트."""

    event: EventName
    seq: int = Field(ge=1)
    ts: str = Field(min_length=1)
    data: dict[str, Any]

    @field_validator("data")
    @classmethod
    def require_common_data_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        if "seq" not in data or "ts" not in data:
            raise ValueError("event data must include seq and ts")
        return data


Subscriber = Callable[[EventRecord], None]


class EventBus:
    """실행 이벤트 발행/구독 허브."""

    def __init__(self) -> None:
        self._seq = 0
        self._buffer: list[EventRecord] = []
        self._subscribers: list[Subscriber] = []

    @property
    def events(self) -> list[EventRecord]:
        """현재/직전 run buffer를 seq 순서로 반환한다."""
        return list(self._buffer)

    def reset(self) -> None:
        """새 run을 시작할 때 버퍼와 seq를 초기화한다."""
        self._seq = 0
        self._buffer.clear()

    def subscribe(
        self,
        subscriber: Subscriber,
        *,
        replay_after_seq: int | None = None,
    ) -> Callable[[], None]:
        """subscriber를 등록하고 선택적으로 기존 buffer를 replay한다."""
        self._subscribers.append(subscriber)
        if replay_after_seq is not None:
            for event in self._buffer:
                if event.seq > replay_after_seq:
                    subscriber(event)

        def unsubscribe() -> None:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

        return unsubscribe

    def publish(self, event: EventName, **payload: Any) -> EventRecord:
        """API spec의 event name과 payload로 EventRecord를 만들고 구독자에게 전달한다."""
        self._seq += 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = {"seq": self._seq, "ts": ts, **payload}
        record = EventRecord(event=event, seq=self._seq, ts=ts, data=data)
        self._buffer.append(record)
        for subscriber in list(self._subscribers):
            subscriber(record)
        return record


class ConsoleEventLogger:
    """CLI에서 EventBus를 구독해 실행 과정을 콘솔로 출력한다."""

    def __call__(self, event: EventRecord) -> None:
        data = event.data
        if event.event == "run_start":
            query = f" query={data['query']}" if data.get("query") else ""
            print(
                f"[{event.seq:02d}] run_start "
                f"mode={data['mode']} asof={data['asof']}{query}"
            )
        elif event.event == "routing_decision":
            agents = ",".join(data["target_agents"])
            print(f"[{event.seq:02d}] routing_decision agents={agents}")
        elif event.event == "agent_start":
            print(f"[{event.seq:02d}] agent_start agent={data['agent']}")
        elif event.event == "agent_end":
            alerts = len(data.get("alerts", []))
            print(f"[{event.seq:02d}] agent_end agent={data['agent']} alerts={alerts}")
        elif event.event == "error":
            agent = data.get("agent") or "-"
            print(
                f"[{event.seq:02d}] error agent={agent} "
                f"recoverable={data['recoverable']} message={data['message']}"
            )
        elif event.event == "run_end":
            print(f"[{event.seq:02d}] run_end status={data['status']}")
        elif event.event == "sensor_update":
            print(
                f"[{event.seq:02d}] sensor_update "
                f"{data['line']} {data['sensor']}={data['value']}{data['unit']}"
            )
        elif event.event == "sensor_alert":
            print(
                f"[{event.seq:02d}] sensor_alert "
                f"{data['line']} {data['sensor']} rule={data['rule']}"
            )
        else:
            print(f"[{event.seq:02d}] {event.event}")
