"""
작성자 : 신유진
작성일 : 2026-07-14
작성 목적: Mosquitto MQTT 센서 topic 구독 후 EventBus로 sensor_update/sensor_alert 발행
변경 이력:
  - 2026-07-14: 단계 10 paho-mqtt subscriber 구현
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.events import EventBus
from src.sensors.rules import SensorPayload, SensorRuleEngine


MQTT_TOPIC = "factory/#"


def handle_sensor_payload(
    raw_payload: bytes,
    *,
    event_bus: EventBus,
    rules: SensorRuleEngine,
) -> SensorPayload:
    """MQTT payload 1건을 검증하고 SSE 이벤트로 발행한다."""
    payload = SensorPayload.model_validate(json.loads(raw_payload.decode("utf-8")))
    event_bus.publish(
        "sensor_update",
        line=payload.line,
        sensor=payload.sensor,
        value=payload.value,
        unit=payload.unit,
        observed_ts=payload.ts,
    )
    alert = rules.record(payload)
    if alert is not None:
        event_bus.publish(
            "sensor_alert",
            line=alert.line,
            sensor=alert.sensor,
            rule=alert.rule,
            values=alert.values,
            unit=alert.unit,
        )
    return payload


class MqttSensorSubscriber:
    """Mosquitto broker의 `factory/#` topic을 구독하는 얇은 wrapper."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        host: str | None = None,
        port: int | None = None,
        rules: SensorRuleEngine | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.host = host or os.getenv("MQTT_HOST", "localhost")
        self.port = port or int(os.getenv("MQTT_PORT", "1883"))
        self.rules = rules or SensorRuleEngine()
        import paho.mqtt.client as mqtt

        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except (AttributeError, TypeError):
            self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self) -> None:
        """비동기 MQTT loop를 시작한다. broker 미기동 시 paho가 재연결을 시도한다."""
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()

    def stop(self) -> None:
        """MQTT loop를 중단한다."""
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        if reason_code == 0:
            client.subscribe(MQTT_TOPIC, qos=0)

    def _on_message(
        self,
        client: Any,
        userdata: Any,
        message: Any,
    ) -> None:
        try:
            handle_sensor_payload(message.payload, event_bus=self.event_bus, rules=self.rules)
        except Exception as exc:
            self.event_bus.publish(
                "error",
                agent=None,
                message=f"invalid sensor payload on {message.topic}: {exc}",
                recoverable=True,
            )


def mqtt_enabled() -> bool:
    """서버 시작 시 MQTT subscriber를 켤지 결정한다."""
    return os.getenv("MQTT_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
