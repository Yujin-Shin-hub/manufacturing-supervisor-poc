"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: 데이터 접근 계층. 모든 CSV/DB 읽기는 여기만 거친다.
변경 이력:
  - 2026-07-06: 단계 0.5 스켈레톤 생성
  - 2026-07-06: 단계 1 canonical CSV 로딩 함수 구현
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

CANONICAL_FILES = {
    "schedule_master": "schedule_master.csv",
    "work_status": "work_status.csv",
    "delay_risk": "delay_risk.csv",
    "reschedule_action": "reschedule_action.csv",
    "machine_process_map": "machine_process_map.csv",
}


def _load_csv(name: str) -> pd.DataFrame:
    """Load a canonical CSV from DATA_DIR."""
    if name not in CANONICAL_FILES:
        raise ValueError(f"unknown canonical dataset: {name}")

    path = DATA_DIR / CANONICAL_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"canonical dataset not found: {path}")
    return pd.read_csv(path)


def load_schedule() -> pd.DataFrame:
    """Load schedule_master.csv."""
    return _load_csv("schedule_master")


def load_work_status() -> pd.DataFrame:
    """Load work_status.csv."""
    return _load_csv("work_status")


def load_delay_risk() -> pd.DataFrame:
    """Load delay_risk.csv."""
    return _load_csv("delay_risk")


def load_reschedule_action() -> pd.DataFrame:
    """Load reschedule_action.csv."""
    return _load_csv("reschedule_action")


def load_machine_process_map() -> pd.DataFrame:
    """Load machine_process_map.csv."""
    return _load_csv("machine_process_map")
