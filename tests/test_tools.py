"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: tools 계층 회귀 테스트. LLM 없이 순수 Python/pytest로 검증한다.
변경 이력:
  - 2026-07-06: 단계 0.5 스켈레톤 생성
  - 2026-07-06: 단계 1 loader/risk/dispatching 테스트 작성
  - 2026-07-06: 단계 1 엑셀 시나리오 기준 테스트로 정렬
"""

from src.tools.dispatching import build_reschedule_actions, find_machine_candidates
from src.tools.formatting import df_to_markdown
from src.tools.loader import (
    load_delay_risk,
    load_machine_process_map,
    load_reschedule_action,
    load_schedule,
    load_work_status,
)
from src.tools.risk import score_delay_risk


def test_canonical_csv_loaders() -> None:
    assert len(load_schedule()) == 100
    assert len(load_work_status()) == 100
    assert len(load_delay_risk()) == 100
    assert len(load_reschedule_action()) == 53
    assert len(load_machine_process_map()) == 12


def test_find_machine_candidates_filters_by_process_qualification_and_capacity() -> None:
    candidates = find_machine_candidates("ETCH_VIA")

    assert not candidates.empty
    assert set(candidates["process_step"]) == {"ETCH_VIA"}
    assert set(candidates["qualified_yn"]) == {"Y"}
    assert set(candidates["machine_status"]) == {"가동"}
    assert set(candidates["available_yn"]) == {"Y"}
    assert candidates["current_load"].lt(0.5).all()
    assert candidates.iloc[0]["machine_id"] == "ETCH-102"


def test_score_delay_risk_uses_existing_delay_risk_and_due_rules() -> None:
    risks = score_delay_risk("2026-04-15 14:00")

    assert not risks.empty
    assert set(risks["risk_level"]).issubset({"HIGH", "CRITICAL"})
    assert risks.iloc[0]["priority"] <= risks.iloc[-1]["priority"]

    sch_0003 = risks[risks["schedule_id"] == "SCH-0003"].iloc[0]
    assert sch_0003["risk_level"] == "CRITICAL"
    assert sch_0003["risk_score"] == 100.0
    assert "status=delayed" in sch_0003["due_risk_reason"]


def test_build_reschedule_actions_recommends_available_alternative_machine() -> None:
    actions = build_reschedule_actions("2026-04-15 14:00")

    assert not actions.empty
    sch_0003 = actions[actions["schedule_id"] == "SCH-0003"].iloc[0]
    assert sch_0003["original_machine"] == "ETCH-105"
    assert sch_0003["alternative_machine"] in {"ETCH-102", "ETCH-104"}
    assert sch_0003["original_machine"] != sch_0003["alternative_machine"]
    assert sch_0003["action_type"] == "설비대체"
    assert sch_0003["applied_yn"] == "N"
    assert sch_0003["expected_delay_reduction_hr"] >= 0
    assert sch_0003["expected_remaining_delay_hr"] >= 0
    assert "예상 지연" in sch_0003["expected_effect"]
    assert "policy_score" in actions.columns
    assert "historical_acceptance_rate" in actions.columns


def test_df_to_markdown() -> None:
    markdown = df_to_markdown(load_schedule().head(1))

    assert "| schedule_id" in markdown
    assert "SCH-0001" in markdown
