"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: dispatching 계산. 설비 후보 탐색과 재조정 액션 생성.
변경 이력:
  - 2026-07-06: 단계 0.5 스켈레톤 생성
  - 2026-07-06: 단계 1 설비 후보/재조정 액션 구현
  - 2026-07-06: 단계 1 후보 기준을 qualified + 가동 + 부하 0.5 미만으로 정렬
"""

from __future__ import annotations

import pandas as pd

from src.tools.loader import load_delay_risk, load_machine_process_map, load_reschedule_action
from src.tools.risk import score_delay_risk

RUNNING_STATUS = "\uac00\ub3d9"
ACTION_TYPE_MACHINE_REPLACE = "\uc124\ube44\ub300\uccb4"
HIGH_IMPACT = "\ub192\uc74c"
NORMAL_IMPACT = "\ubcf4\ud1b5"
MAX_CANDIDATE_LOAD = 0.5
HISTORY_MIN_SAMPLE = 1
QUALITY_RISK_PATTERNS = ("Particle", "defect", "Recipe qualification", "quality", "spec")


def find_machine_candidates(process_step: str) -> pd.DataFrame:
    """Return qualified and currently available machine candidates."""
    if not process_step or not str(process_step).strip():
        raise ValueError("process_step is required")

    machine_map = load_machine_process_map()
    candidates = machine_map[
        (machine_map["process_step"] == process_step)
        & (machine_map["qualified_yn"] == "Y")
        & (machine_map["machine_status"] == RUNNING_STATUS)
        & (machine_map["available_yn"] == "Y")
        & (machine_map["current_load"] < MAX_CANDIDATE_LOAD)
    ].copy()

    return candidates.sort_values(
        ["current_load", "preferred_rank", "setup_time_min", "machine_id"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)


def build_reschedule_actions(asof: str) -> pd.DataFrame:
    """Create proposed rescheduling actions for scenario HIGH/CRITICAL risks."""
    risks = score_delay_risk(asof)
    action_history = load_reschedule_action()
    risk_history = load_delay_risk()
    actions: list[dict[str, object]] = []

    for original_sequence, row in enumerate(risks.itertuples(index=False), start=1):
        candidates = find_machine_candidates(row.process_step)
        alternatives = candidates[candidates["machine_id"] != row.assigned_machine]
        if alternatives.empty:
            continue

        ranked = _rank_candidates_with_history(
            alternatives=alternatives,
            original_load=float(row.current_load),
            action_history=action_history,
            risk_history=risk_history,
        )
        selected = ranked.iloc[0]
        gain = max(0.0, float(row.current_load) - float(selected["current_load"]))
        expected_delay_reduction_hr = round(float(row.estimated_delay_hr) * gain, 1)
        expected_remaining_delay_hr = round(
            max(0.0, float(row.estimated_delay_hr) - expected_delay_reduction_hr),
            1,
        )
        impact = HIGH_IMPACT if row.risk_level == "CRITICAL" else NORMAL_IMPACT
        actions.append(
            {
                "action_id": f"GEN-{len(actions) + 1:04d}",
                "schedule_id": row.schedule_id,
                "risk_id": row.risk_id,
                "original_machine": row.assigned_machine,
                "alternative_machine": selected["machine_id"],
                "new_sequence": len(actions) + 1,
                "original_sequence": original_sequence,
                "action_type": ACTION_TYPE_MACHINE_REPLACE,
                "impact": impact,
                "efficiency_gain": round(gain, 2),
                "expected_delay_reduction_hr": expected_delay_reduction_hr,
                "expected_remaining_delay_hr": expected_remaining_delay_hr,
                "historical_acceptance_rate": _nullable_round(
                    selected["historical_acceptance_rate"],
                    2,
                ),
                "historical_sample_count": int(selected["historical_sample_count"]),
                "historical_avg_efficiency_gain": _nullable_round(
                    selected["historical_avg_efficiency_gain"],
                    2,
                ),
                "quality_risk_count": int(selected["quality_risk_count"]),
                "quality_risk_rate": _nullable_round(selected["quality_risk_rate"], 2),
                "policy_score": round(float(selected["policy_score"]), 1),
                "policy_decision_reason": _policy_reason(selected),
                "expected_effect": (
                    f"예상 지연 {float(row.estimated_delay_hr):.1f}h 중 "
                    f"{expected_delay_reduction_hr:.1f}h 완화, "
                    f"부하 {gain:.2f}p 감소, "
                    f"이력 승인률 {_format_rate(selected['historical_acceptance_rate'])}"
                ),
                "quality_history_note": _quality_note(selected),
                "applied_yn": "N",
                "action_time": pd.to_datetime(asof),
                "process_step": row.process_step,
                "risk_level": row.risk_level,
                "risk_score": row.risk_score,
                "delay_probability": row.delay_probability,
                "estimated_delay_hr": row.estimated_delay_hr,
            }
        )

    return pd.DataFrame(actions)


def _rank_candidates_with_history(
    *,
    alternatives: pd.DataFrame,
    original_load: float,
    action_history: pd.DataFrame,
    risk_history: pd.DataFrame,
) -> pd.DataFrame:
    """Rank machine candidates using current feasibility and historical outcomes."""
    ranked = alternatives.copy()
    metrics = [
        _candidate_policy_metrics(
            machine_id=str(row.machine_id),
            current_load=float(row.current_load),
            setup_time_min=int(row.setup_time_min),
            original_load=original_load,
            action_history=action_history,
            risk_history=risk_history,
        )
        for row in ranked.itertuples(index=False)
    ]
    policy = pd.DataFrame(metrics)
    ranked = pd.concat([ranked.reset_index(drop=True), policy], axis=1)
    return ranked.sort_values(
        [
            "policy_score",
            "historical_acceptance_score",
            "quality_risk_rate",
            "current_load",
            "preferred_rank",
            "setup_time_min",
            "machine_id",
        ],
        ascending=[False, False, True, True, True, True, True],
    ).reset_index(drop=True)


def _candidate_policy_metrics(
    *,
    machine_id: str,
    current_load: float,
    setup_time_min: int,
    original_load: float,
    action_history: pd.DataFrame,
    risk_history: pd.DataFrame,
) -> dict[str, object]:
    """Build deterministic history-policy metrics for one candidate machine.

    This is the policy layer behind dispatching. It does not use LLM output.
    It combines current load relief, historical acceptance, historical efficiency
    gain, quality-related risk history, and setup time into one score.
    """
    history = (
        action_history[action_history["alternative_machine"] == machine_id].copy()
        if "alternative_machine" in action_history.columns
        else pd.DataFrame()
    )
    sample_count = int(len(history))
    accepted_count = int((history["applied_yn"] == "Y").sum()) if sample_count else 0
    acceptance_rate = accepted_count / sample_count if sample_count else None
    acceptance_score = acceptance_rate if acceptance_rate is not None else 0.5

    avg_efficiency_gain = (
        float(history["efficiency_gain"].mean())
        if sample_count and "efficiency_gain" in history.columns
        else None
    )
    efficiency_score = max(0.0, min(1.0, avg_efficiency_gain if avg_efficiency_gain is not None else 0.0))

    machine_risks = (
        risk_history[risk_history["machine_id"] == machine_id].copy()
        if "machine_id" in risk_history.columns
        else pd.DataFrame()
    )
    quality_mask = (
        machine_risks["risk_factor"].astype(str).str.contains(
            "|".join(QUALITY_RISK_PATTERNS),
            case=False,
            regex=True,
        )
        if not machine_risks.empty and "risk_factor" in machine_risks.columns
        else pd.Series(dtype=bool)
    )
    quality_risk_count = int(quality_mask.sum()) if not quality_mask.empty else 0
    risk_sample_count = int(len(machine_risks))
    quality_risk_rate = quality_risk_count / risk_sample_count if risk_sample_count else 0.0
    quality_score = max(0.0, 1.0 - quality_risk_rate)

    load_relief = max(0.0, original_load - current_load)
    load_score = max(0.0, min(1.0, load_relief))
    setup_score = max(0.0, 1.0 - min(setup_time_min / 60.0, 1.0))
    current_load_score = max(0.0, min(1.0, 1.0 - current_load))
    policy_score = 100 * (
        0.30 * load_score
        + 0.25 * acceptance_score
        + 0.15 * quality_score
        + 0.15 * current_load_score
        + 0.10 * setup_score
        + 0.05 * efficiency_score
    )
    return {
        "historical_acceptance_rate": acceptance_rate,
        "historical_acceptance_score": acceptance_score,
        "historical_sample_count": sample_count,
        "historical_avg_efficiency_gain": avg_efficiency_gain,
        "quality_risk_count": quality_risk_count,
        "quality_risk_rate": quality_risk_rate,
        "policy_score": policy_score,
    }


def _nullable_round(value: object, digits: int) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _format_rate(value: object) -> str:
    if value is None or pd.isna(value):
        return "이력 없음"
    return f"{float(value) * 100:.0f}%"


def _quality_note(selected: pd.Series) -> str:
    count = int(selected["quality_risk_count"])
    rate = float(selected["quality_risk_rate"])
    if count == 0:
        return "후보 설비의 품질성 risk 이력 없음"
    return f"후보 설비 품질성 risk 이력 {count}건(rate={rate:.2f})"


def _policy_reason(selected: pd.Series) -> str:
    return (
        f"policy_score={float(selected['policy_score']):.1f}; "
        f"current_load={float(selected['current_load']):.2f}; "
        f"acceptance={_format_rate(selected['historical_acceptance_rate'])}; "
        f"quality_risk_rate={float(selected['quality_risk_rate']):.2f}; "
        f"setup_time_min={int(selected['setup_time_min'])}"
    )
