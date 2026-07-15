"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: 납기 위험 계획 식별 및 delay_risk 기준 리스크 조회.
변경 이력:
  - 2026-07-06: 단계 0.5 스켈레톤 생성
  - 2026-07-06: 단계 1 지연 위험 조회/정렬 구현
  - 2026-07-06: 단계 1 리스크 기준을 엑셀 시나리오 5단계 흐름에 맞춤
"""

from __future__ import annotations

import pandas as pd

from src.tools.loader import load_delay_risk, load_schedule, load_work_status

DELAYED_STATUS = "\uc9c0\uc5f0"
WAITING_STATUS = "\ub300\uae30"
HIGH_RISK_LEVELS = {"HIGH", "CRITICAL"}
DUE_WINDOW_DAYS = 3


def score_delay_risk(asof: str) -> pd.DataFrame:
    """Return due-risk schedules joined with existing delay_risk values.

    This function does not invent a new risk score. It follows the scenario rule:
    identify schedules that are delayed or due within D+3, then confirm
    HIGH/CRITICAL rows in delay_risk and sort by priority/risk_score.
    """
    asof_ts = pd.to_datetime(asof)
    due_limit = asof_ts.normalize() + pd.Timedelta(days=DUE_WINDOW_DAYS)

    schedule = load_schedule().copy()
    work_status = load_work_status().copy()
    delay_risk = load_delay_risk().copy()

    schedule["due_date_ts"] = pd.to_datetime(schedule["due_date"])
    due_risk_mask = (schedule["status"] == DELAYED_STATUS) | (
        schedule["due_date_ts"] <= due_limit
    )
    schedule = schedule[due_risk_mask].copy()

    df = (
        schedule.merge(delay_risk, on="schedule_id", how="left")
        .merge(work_status, on="schedule_id", how="left", suffixes=("", "_work"))
        .copy()
    )
    df = df[df["risk_level"].isin(HIGH_RISK_LEVELS)].copy()

    df["days_to_due"] = (df["due_date_ts"] - asof_ts.normalize()).dt.days
    df["due_risk_reason"] = df.apply(_due_risk_reason, axis=1)
    df["asof"] = asof_ts

    columns = [
        "schedule_id",
        "product",
        "priority",
        "due_date",
        "days_to_due",
        "status",
        "process_step",
        "assigned_machine",
        "risk_id",
        "risk_score",
        "risk_level",
        "delay_probability",
        "estimated_delay_hr",
        "impact_scope",
        "risk_factor",
        "machine_status",
        "current_load",
        "due_risk_reason",
        "asof",
    ]
    return df[columns].sort_values(
        ["priority", "risk_score", "due_date", "schedule_id"],
        ascending=[True, False, True, True],
    )


def _due_risk_reason(row: pd.Series) -> str:
    reasons = []
    if row["status"] == DELAYED_STATUS:
        reasons.append("status=delayed")
    if int(row["days_to_due"]) <= DUE_WINDOW_DAYS:
        reasons.append("due_within_d3")
    return ",".join(reasons)
