"""
작성자: 전유진
작성일: 2026-07-14
작성 목적: 단계 9 README 갱신 및 결과물 커밋 산출물 검증
변경 이력:
  - 2026-07-14: 단계 9 증거 파일과 README 링크 계약 테스트 추가
  - 2026-07-15: README 개편으로 단계 번호 표(`| 9 |`)가 사라져 해당 단언 제거 —
                증거 파일 링크·완료 표기 검증은 유지
  - 2026-07-16: README 재개편으로 "완료" 표기도 제거됨 — 문구 의존 단언을 빼고
                증거 파일 링크 계약만 검증한다 (README 문안은 자유롭게 바뀌는 영역)
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_links_stage9_dashboard_report_drawer_and_artifacts() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/dashboard-run-replay.gif" not in readme
    assert "reports/dashboard-stage9-report-drawer.png" in readme
    assert "reports/stage9_report_report_mode.md" in readme
    assert "reports/stage9_report_ask_dispatching.md" in readme


def test_stage9_report_examples_preserve_api_spec_columns() -> None:
    expected_columns = {
        "schedule_id",
        "risk_score",
        "risk_level",
        "original_machine",
        "alternative_machine",
        "efficiency_gain",
    }

    for path in [
        ROOT / "reports" / "stage9_report_report_mode.md",
        ROOT / "reports" / "stage9_report_ask_dispatching.md",
    ]:
        content = path.read_text(encoding="utf-8")
        assert "SCH-" in content
        assert expected_columns.issubset(set(content.split()))


def test_stage9_dashboard_visual_artifacts_exist() -> None:
    screenshot_path = ROOT / "reports" / "dashboard-stage9-report-drawer.png"

    assert screenshot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert screenshot_path.stat().st_size > 100_000
