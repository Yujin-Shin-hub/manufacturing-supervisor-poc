"""
작성자: 신유진
작성일: 2026-07-07
작성 목적: 단계 7 FastAPI /health, /run 입력 검증, 읽기 전용 /api 조회 검증
변경 이력:
  - 2026-07-07: server endpoint smoke test 추가
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.server import app


client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_ask_requires_query() -> None:
    response = client.post(
        "/run",
        json={"mode": "ask", "asof": "2026-04-15 14:00"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "query is required when mode='ask'"


def test_api_schedules_filters_and_preserves_csv_columns() -> None:
    response = client.get("/api/schedules", params={"process_step": "ETCH_VIA"})

    assert response.status_code == 200
    body = response.json()
    assert body["asof"] == "2026-04-15 14:00"
    assert body["rows"]
    assert set(body["rows"][0]) == {
        "schedule_id",
        "product",
        "priority",
        "due_date",
        "quantity",
        "process_step",
        "assigned_machine",
        "estimated_duration_hr",
        "status",
    }
    assert {row["process_step"] for row in body["rows"]} == {"ETCH_VIA"}


def test_api_risks_sorts_by_risk_score_desc() -> None:
    response = client.get("/api/risks")

    assert response.status_code == 200
    scores = [row["risk_score"] for row in response.json()["rows"]]
    assert scores == sorted(scores, reverse=True)
