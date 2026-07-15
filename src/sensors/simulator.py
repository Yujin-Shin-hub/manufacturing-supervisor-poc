"""
작성자 : 신유진
작성일 : 2026-07-14
작성 목적: Mosquitto로 가상 라인 센서값을 publish하는 별도 프로세스 시뮬레이터
변경 이력:
  - 2026-07-14: 단계 10 센서 랜덤워크와 이상 주입 CLI 구현
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime
from typing import Literal

import paho.mqtt.client as mqtt

from src.sensors.rules import SensorType


Anomaly = Literal["temp-drift", "vib-spike", "throughput-drop"]
LINES = [f"Line-{index}" for index in range(1, 7)]
BASE_VALUES: dict[SensorType, float] = {
    "temperature": 70.0,
    "vibration": 1.4,
    "throughput": 58.0,
}
UNITS: dict[SensorType, str] = {
    "temperature": "C",
    "vibration": "mm/s",
    "throughput": "ea/min",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish virtual fab sensor data to MQTT.")
    parser.add_argument("--anomaly", choices=["temp-drift", "vib-spike", "throughput-drop"])
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    args = parser.parse_args()

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()
    try:
        publish_loop(client, anomaly=args.anomaly, interval_sec=args.interval_sec)
    finally:
        client.loop_stop()
        client.disconnect()


def publish_loop(
    client: mqtt.Client,
    *,
    anomaly: Anomaly | None,
    interval_sec: float,
) -> None:
    """6개 라인 x 3종 센서값을 계속 publish한다."""
    tick = 0
    values = {
        (line, sensor): BASE_VALUES[sensor]
        for line in LINES
        for sensor in BASE_VALUES
    }
    while True:
        tick += 1
        for line in LINES:
            for sensor in BASE_VALUES:
                values[(line, sensor)] = _next_value(
                    line=line,
                    sensor=sensor,
                    current=values[(line, sensor)],
                    anomaly=anomaly,
                    tick=tick,
                )
                payload = {
                    "ts": datetime.now().replace(microsecond=0).isoformat(),
                    "line": line,
                    "sensor": sensor,
                    "value": round(values[(line, sensor)], 2),
                    "unit": UNITS[sensor],
                }
                client.publish(
                    f"factory/{line.lower()}/sensor/{sensor}",
                    json.dumps(payload, ensure_ascii=False),
                    qos=0,
                    retain=False,
                )
        time.sleep(interval_sec)


def _next_value(
    *,
    line: str,
    sensor: SensorType,
    current: float,
    anomaly: Anomaly | None,
    tick: int,
) -> float:
    if anomaly == "temp-drift" and line == "Line-2" and sensor == "temperature":
        return min(92.0, current + 0.35)
    if anomaly == "vib-spike" and line == "Line-5" and sensor == "vibration":
        return 3.6 if tick % 6 in {0, 1, 2} else max(1.2, current - 0.2)
    if anomaly == "throughput-drop" and line == "Line-3" and sensor == "throughput":
        return max(24.0, current - 0.7)

    drift = random.uniform(-0.4, 0.4)
    if sensor == "temperature":
        return min(78.5, max(61.5, current + drift))
    if sensor == "vibration":
        return min(2.5, max(0.7, current + drift * 0.08))
    return min(68.0, max(42.0, current + drift * 1.5))


if __name__ == "__main__":
    main()
