"""
작성자  : 신유진
작성일  : 2026-07-14
작성 목적: supervisor_validation — Worker 결과를 합쳐 리포트 전 추천 일관성 검증
변경 이력:
  - 2026-07-14: policy/dispatching/리스크 결과 교차 검증 섹션 추가
"""

from __future__ import annotations

from src.schemas import AgentResult


class SupervisorValidation:
    """리포트 생성 전 Supervisor 관점의 최종 검증을 수행한다."""

    name = "supervisor_validation"

    def run(self, sections: list[AgentResult]) -> AgentResult:
        """Worker 결과 간 핵심 근거가 연결됐는지 검증한다."""
        dispatching = _find_section(sections, "dispatching")
        policy = _find_section(sections, "scheduling_policy")
        risk = _find_section(sections, "risk_alert")

        checks: list[dict[str, str]] = []
        checks.append(_check("risk_alert", risk is not None, "HIGH/CRITICAL 위험 근거 존재"))
        checks.append(_check("dispatching", dispatching is not None, "재조정 추천 근거 존재"))
        checks.append(_check("scheduling_policy", policy is not None, "과거 이력 기반 policy 검증 존재"))

        if dispatching is not None and policy is not None:
            dispatch_rows = _markdown_rows(dispatching.evidence_tables.get("reschedule_actions", ""))
            policy_rows = _markdown_rows(policy.evidence_tables.get("policy_review", ""))
            dispatch_ids = {row.get("schedule_id") for row in dispatch_rows}
            policy_ids = {row.get("schedule_id") for row in policy_rows}
            checks.append(
                _check(
                    "dispatching_vs_policy",
                    bool(dispatch_ids & policy_ids),
                    "dispatching 추천과 policy 검증 schedule_id 교차 확인",
                )
            )
            checks.append(
                _check(
                    "expected_effect",
                    all(row.get("expected_effect") for row in policy_rows[:5]),
                    "상위 policy 추천에 기대효과 문구 포함",
                )
            )

        failed = [row for row in checks if row["status"] != "PASS"]
        summary = (
            "Supervisor 검증 통과: 리스크, 재조정 추천, policy 기대효과가 리포트 전 교차 확인됐습니다."
            if not failed
            else f"Supervisor 검증 경고: {len(failed)}개 항목 확인 필요."
        )
        alerts = [f"{row['check']}: {row['message']}" for row in failed]
        return AgentResult(
            agent=self.name,
            summary=summary,
            evidence_tables={"validation_checks": _markdown_table(checks)},
            alerts=alerts,
            tool_calls_used=[],
        )


def _find_section(sections: list[AgentResult], agent: str) -> AgentResult | None:
    return next((section for section in sections if section.agent == agent), None)


def _check(name: str, passed: bool, message: str) -> dict[str, str]:
    return {"check": name, "status": "PASS" if passed else "WARN", "message": message}


def _markdown_rows(table: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in table.splitlines() if line.strip()]
    if len(lines) < 3 or not lines[0].startswith("|"):
        return []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        values = [cell.strip() for cell in line.strip("|").split("|")]
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values, strict=True)))
    return rows


def _markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_No rows_"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(header, "") for header in headers) + " |")
    return "\n".join(lines)
