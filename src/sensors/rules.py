"""
작성자 : 신유진
작성일 : 2026-07-14
작성 목적: MQTT 센서 payload 검증과 deterministic threshold rule 판정
변경 이력:
  - 2026-07-14: 단계 10 sensor_update/sensor_alert 규칙 엔진 구현
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from src.schemas import StrictModel


SensorType = Literal["temperature", "vibration", "throughput"]


class SensorPayload(StrictModel):
    """MQTT topic payload — docs/sensor-stream.md의 JSON 계약."""

    ts: str = Field(min_length=1)
    line: str = Field(min_length=1)
    sensor: SensorType
    value: float
    unit: str = Field(min_length=1)


class SensorAlert(StrictModel):
    """규칙 엔진이 발생시키는 센서 이상 알림."""

    line: str
    sensor: SensorType
    rule: str
    values: list[float] = Field(min_length=3)
    unit: str


# 데모용 공정 임계치. 실제 예지보전 모델이 아니라 step10 실시간 스트림 가시화 기준이다.
THRESHOLDS: dict[SensorType, tuple[float | None, float | None]] = {
    "temperature": (60.0, 80.0),
    "vibration": (0.5, 2.8),
    "throughput": (35.0, None),
}
CONSECUTIVE_BREACHES = 3
WINDOW_SECONDS = 60


class SensorRuleEngine:
    """동일 라인·센서의 최근 임계 초과 연속성을 관리한다."""

    def __init__(self) -> None:
        self._breaches: dict[tuple[str, SensorType], deque[SensorPayload]] = defaultdict(deque)

    def record(self, payload: SensorPayload) -> SensorAlert | None:
        """payload를 기록하고 alert 발생 여부를 반환한다."""
        key = (payload.line, payload.sensor)
        bucket = self._breaches[key]
        current_ts = _parse_ts(payload.ts)

        if not _is_breach(payload):
            bucket.clear()
            return None

        bucket.append(payload)
        while bucket and current_ts - _parse_ts(bucket[0].ts) > timedelta(seconds=WINDOW_SECONDS):
            bucket.popleft()

        if len(bucket) < CONSECUTIVE_BREACHES:
            return None

        recent = list(bucket)[-CONSECUTIVE_BREACHES:]
        bucket.clear()
        return SensorAlert(
            line=payload.line,
            sensor=payload.sensor,
            rule="3연속 초과",
            values=[round(item.value, 2) for item in recent],
            unit=payload.unit,
        )


def _is_breach(payload: SensorPayload) -> bool:
    lower, upper = THRESHOLDS[payload.sensor]
    if lower is not None and payload.value < lower:
        return True
    if upper is not None and payload.value > upper:
        return True
    return False


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)
