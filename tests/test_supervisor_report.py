"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: 단계 5 report Worker + Supervisor 조립 테스트
변경 이력:
  - 2026-07-06: ReportWorker, Supervisor report/ask, partial failure, CLI 출력 검증 추가
  - 2026-07-14: 리포트 A안 계약 반영 — 스냅샷 표 한글 헤더·key_actions 구조화 데이터·
                key_actions 마커 검증으로 갱신
"""

from __future__ import annotations

import pytest

from src import main, router
from src.agents.report import ReportWorker
from src.schemas import AgentResult, Report, RoutingDecision
from src.supervisor import Supervisor


ASOF = "2026-04-15 14:00"


@pytest.fixture(autouse=True)
def disable_worker_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supervisor 조립 테스트가 실제 LLM/API 네트워크를 호출하지 않게 한다."""

    def raise_llm_error(*args, **kwargs):
        raise RuntimeError("LLM disabled in supervisor tests")

    monkeypatch.setattr("src.agents.base.complete_json", raise_llm_error)


def _result(agent: str, table_name: str = "evidence") -> AgentResult:
    if table_name == "reschedule_actions":
        table = (
            "| schedule_id | original_machine | alternative_machine | risk_level | "
            "expected_delay_reduction_hr | expected_remaining_delay_hr | "
            "historical_acceptance_rate | expected_effect |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| SCH-0003 | ETCH-105 | ETCH-102 | CRITICAL | 2.9 | 5.2 | 0.75 | 예상 지연 8.1h 중 2.9h 완화 |"
        )
    else:
        table = "| schedule_id | risk_score |\n| --- | --- |\n| SCH-0003 | 100.0 |"
    return AgentResult.model_validate(
        {
            "agent": agent,
            "summary": f"{agent} summary",
            "evidence_tables": {table_name: table},
            "alerts": [f"{agent} alert"],
            "tool_calls_used": ["test_tool"],
        }
    )


def test_report_worker_builds_markdown_from_agent_results() -> None:
    report = ReportWorker().run(
        ASOF,
        sections=[
            _result("field_status"),
            _result("risk_alert", "risk"),
            _result("dispatching", "reschedule_actions"),
        ],
    )

    assert isinstance(report, Report)
    assert report.title == "제조 Supervisor 운영 리포트"
    assert "핵심 추천 액션" in report.report_markdown
    # 표 헤더 한글화 (2026-07-14) — 데이터 필드명은 유지, 표기만 한글 라벨
    assert "| 지연 완화(h) |" in report.report_markdown
    assert "expected_delay_reduction_hr" not in report.report_markdown
    # 드로어 고정 컴포넌트 대체용 마커 + 구조화 key_actions (api-spec 2-1 run_end)
    assert "<!-- key_actions:start -->" in report.report_markdown
    assert "<!-- key_actions:end -->" in report.report_markdown
    assert report.key_actions_total == 1
    key_action = report.key_actions[0]
    assert key_action.rank == 1
    assert key_action.schedule_id == "SCH-0003"
    assert key_action.alternative_machine == "ETCH-102"
    assert key_action.expected_delay_reduction_hr == 2.9
    assert key_action.historical_acceptance_rate == 0.75
    assert "## 현장 가동 현황 (`field_status`)" in report.report_markdown
    assert "## 리스크 알림 (`risk_alert`)" in report.report_markdown
    assert "### 근거 표: risk" in report.report_markdown
    assert "리스크 점수" in report.report_markdown
    assert "SCH-0003" in report.report_markdown


def test_supervisor_report_mode_runs_workers_in_fixed_order(monkeypatch) -> None:
    calls: list[str] = []
    supervisor = Supervisor()

    class FakeWorker:
        def __init__(self, agent: str) -> None:
            self.agent = agent

        def run(self, asof: str, query: str | None = None) -> AgentResult:
            calls.append(self.agent)
            assert asof == ASOF
            assert query is None
            return _result(self.agent)

    for agent_name in supervisor._workers:
        supervisor._workers[agent_name] = FakeWorker(agent_name)

    report = supervisor.run("report", ASOF)

    assert calls == ["field_status", "risk_alert", "delay_pred", "dispatching", "scheduling_policy"]
    assert [section.agent for section in report.sections] == [*calls, "supervisor_validation"]
    assert "## 설비 재배정 제안 (`dispatching`)" in report.report_markdown
    assert "## 이력 기반 스케줄링 정책 검증 (`scheduling_policy`)" in report.report_markdown
    assert "## Supervisor 최종 검증 (`supervisor_validation`)" in report.report_markdown


def test_supervisor_ask_mode_uses_router_targets(monkeypatch) -> None:
    def fake_route(query: str, *, provider: str | None = None) -> RoutingDecision:
        assert query == "위험 작업 찾고 대체 설비도 추천해줘"
        assert provider == "qwen"
        return RoutingDecision(
            target_agents=["risk_alert", "dispatching"],
            execution_order="sequential",
            reason="위험과 재배정 동시 확인",
        )

    monkeypatch.setattr(router, "route", fake_route)
    report = Supervisor().run(
        "ask",
        ASOF,
        query="위험 작업 찾고 대체 설비도 추천해줘",
        llm_provider="qwen",
    )

    assert [section.agent for section in report.sections] == [
        "risk_alert",
        "dispatching",
        "scheduling_policy",
        "supervisor_validation",
    ]
    assert "- 요청: 위험 작업 찾고 대체 설비도 추천해줘" in report.report_markdown


def test_supervisor_partial_failure_keeps_report_running() -> None:
    supervisor = Supervisor()

    class FailingWorker:
        def run(self, asof: str, query: str | None = None) -> AgentResult:
            raise RuntimeError("boom")

    supervisor._workers["risk_alert"] = FailingWorker()

    report = supervisor.run("report", ASOF)

    failed = [section for section in report.sections if section.agent == "risk_alert"][0]
    assert "수집 실패" in failed.summary
    assert failed.evidence_tables == {"error": "수집 실패"}
    assert "## 설비 재배정 제안 (`dispatching`)" in report.report_markdown


def test_supervisor_ask_requires_query() -> None:
    with pytest.raises(ValueError, match="query is required"):
        Supervisor().run("ask", ASOF)


def test_main_report_prints_markdown(capsys) -> None:
    main.main(["--mode", "report", "--asof", ASOF])

    output = capsys.readouterr().out
    assert "# 제조 Supervisor 운영 리포트" in output
    assert "## 현장 가동 현황 (`field_status`)" in output
    assert "### 근거 표:" in output
