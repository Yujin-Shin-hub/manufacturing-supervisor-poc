"""
작성자: 신유진
작성일: 2026-07-14
작성 목적: 단계 10 MQTT 센서 스트림 규칙 엔진과 SSE 이벤트 발행 검증
변경 이력:
  - 2026-07-14: sensor_update, sensor_alert 단위 테스트 추가
"""

from __future__ import annotations

import json

from src.events import EventBus
from src.sensors.rules import SensorPayload, SensorRuleEngine
from src.sensors.subscriber import handle_sensor_payload


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
