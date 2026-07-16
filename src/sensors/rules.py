"""
작성자 : 신유진
작성일 : 2026-07-14
작성 목적: MQTT 센서 payload 검증과 deterministic threshold rule 판정
변경 이력:
  - 2026-07-14: 단계 10 sensor_update/sensor_alert 규칙 엔진 구현
  - 2026-07-16: 단계 11 자동 트리거 쿨다운(AutoTriggerCooldown)과 고정 query 템플릿 추가
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


# 자동 트리거 쿨다운 — 라인당 5분 (docs/sensor-stream.md).
# 지속 이상 시 rule이 ~3초마다 sensor_alert를 재발행하므로, 쿨다운 없이는
# 같은 이상으로 Supervisor 파이프라인이 반복 실행되는 루프가 생긴다.
AUTO_TRIGGER_COOLDOWN_SECONDS = 300

# 자동 실행 query는 고정 템플릿 — 트리거 판정과 문구 생성 모두 코드가 담당한다 (절대 규칙 2).
AUTO_QUERY_TEMPLATES: dict[SensorType, str] = {
    "temperature": "{line} 온도 이상. 지연 위험과 재배치 필요성 평가",
    "vibration": "{line} 진동 이상. 지연 위험과 재배치 필요성 평가",
    "throughput": "{line} 처리량 급감. 지연 위험과 재배치 필요성 평가",
}


def build_auto_query(line: str, sensor: SensorType) -> str:
    """sensor_alert로부터 자동 실행에 사용할 고정 템플릿 query를 만든다.

    Args:
        line: 알림이 발생한 라인 식별자 (예: "Line-2").
        sensor: 알림이 발생한 센서 종류.

    Returns:
        라우팅에 전달할 고정 템플릿 query 문자열.
    """
    return AUTO_QUERY_TEMPLATES[sensor].format(line=line)


class AutoTriggerCooldown:
    """라인당 자동 트리거 쿨다운을 관리한다.

    allow가 True를 반환하는 순간 해당 라인의 트리거 시각을 기록한다 —
    수동 실행 중 폐기된 트리거는 allow를 통과하지 않으므로 쿨다운을 소모하지 않는다.
    """

    def __init__(self, cooldown_seconds: int = AUTO_TRIGGER_COOLDOWN_SECONDS) -> None:
        """쿨다운 간격과 라인별 마지막 트리거 시각 저장소를 초기화한다.

        Args:
            cooldown_seconds: 같은 라인의 재트리거를 막을 시간(초).

        Returns:
            None.
        """
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._last_triggered: dict[str, datetime] = {}

    def allow(self, line: str, now: datetime | None = None) -> bool:
        """해당 라인의 자동 트리거 허용 여부를 판정하고, 허용 시 트리거 시각을 기록한다.

        Args:
            line: 판정 대상 라인 식별자.
            now: 판정 기준 시각. None이면 현재 시각 (테스트 주입용).

        Returns:
            쿨다운이 지나 트리거를 허용하면 True, 쿨다운 중이면 False.
        """
        current = now or datetime.now()
        last = self._last_triggered.get(line)
        if last is not None and current - last < self._cooldown:
            return False
        self._last_triggered[line] = current
        return True


def _is_breach(payload: SensorPayload) -> bool:
    lower, upper = THRESHOLDS[payload.sensor]
    if lower is not None and payload.value < lower:
        return True
    if upper is not None and payload.value > upper:
        return True
    return False


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)
