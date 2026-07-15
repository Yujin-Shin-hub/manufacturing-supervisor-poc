"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: report Worker — Supervisor 운영 리포트 조립
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 5)
  - 2026-07-06: 단계 5 AgentResult 목록을 근거 표 포함 Report markdown으로 조립
  - 2026-07-07: 단계 8 리포트 가독성 개선 — HTML 액션 카드를 markdown 표로 교체,
                요약 절 신설, 섹션 제목을 관리자용 한글 제목으로 변경 (수치 계산 변경 없음)
  - 2026-07-14: 대시보드 리포트 A안 — 핵심 추천 액션을 KeyAction 구조화 데이터로도 추출
                (드로어 고정 컴포넌트용, markdown 스냅샷 절은 마커 주석으로 감쌈),
                근거 표·스냅샷 표 헤더 한글화 (COLUMN_LABELS 단일 소스, 수치 계산 변경 없음)
"""

from __future__ import annotations

from src.schemas import AgentResult, KeyAction, Report

from .base import BaseWorker


# 관리자용 섹션 제목 (agent 키는 괄호로 병기해 이벤트·큐와 대조 가능하게 유지)
SECTION_TITLES: dict[str, str] = {
    "field_status": "현장 가동 현황",
    "risk_alert": "리스크 알림",
    "delay_pred": "지연 예측",
    "dispatching": "설비 재배정 제안",
    "scheduling_policy": "이력 기반 스케줄링 정책 검증",
    "supervisor_validation": "Supervisor 최종 검증",
}

# 핵심 추천 액션 표에 싣는 최대 행 수
ACTION_SNAPSHOT_ROWS = 5

# 드로어가 markdown 스냅샷 절을 고정 컴포넌트로 대체할 때 쓰는 마커 (marked 렌더 시 보이지 않음)
KEY_ACTIONS_MARKER_START = "<!-- key_actions:start -->"
KEY_ACTIONS_MARKER_END = "<!-- key_actions:end -->"

# 리포트 표시용 한글 헤더 — 원본 CSV/tool 컬럼명 매핑의 단일 소스 (api-spec 2-1).
# 수치·데이터는 그대로 두고 표 헤더 표기만 바꾼다. 매핑에 없는 컬럼은 원본명을 유지한다.
COLUMN_LABELS: dict[str, str] = {
    "schedule_id": "스케줄",
    "product": "제품",
    "priority": "우선순위",
    "due_date": "납기일",
    "days_to_due": "납기까지(일)",
    "status": "상태",
    "process_step": "공정",
    "assigned_machine": "배정 설비",
    "machine_status": "설비 상태",
    "current_load": "부하",
    "operator": "작업자",
    "risk_id": "리스크 ID",
    "risk_score": "리스크 점수",
    "risk_level": "위험 등급",
    "risk_factor": "위험 요인",
    "delay_probability": "지연 확률",
    "estimated_delay_hr": "예상 지연(h)",
    "impact_scope": "영향 범위",
    "due_risk_reason": "납기 위험 사유",
    "detection_time": "감지 시각",
    "action_id": "액션 ID",
    "original_machine": "원 설비",
    "alternative_machine": "대체 설비",
    "new_sequence": "새 순번",
    "action_type": "조치 유형",
    "impact": "영향",
    "efficiency_gain": "효율 개선",
    "expected_delay_reduction_hr": "지연 완화(h)",
    "expected_remaining_delay_hr": "잔여 지연(h)",
    "historical_acceptance_rate": "이력 승인률",
    "historical_sample_count": "이력 표본 수",
    "historical_avg_efficiency_gain": "이력 평균 효율 개선",
    "quality_risk_count": "품질 리스크 건수",
    "quality_risk_rate": "품질 리스크 비율",
    "policy_score": "정책 점수",
    "policy_decision_reason": "정책 판단 근거",
    "expected_effect": "기대효과",
    "quality_history_note": "품질 이력 비고",
    "source_process_step": "대상 공정",
    "machine_id": "설비 ID",
    "qualified_yn": "자격(Y/N)",
    "preferred_rank": "선호 순위",
    "setup_time_min": "셋업 시간(분)",
    "available_yn": "가용(Y/N)",
    "check": "검증 항목",
    "message": "메시지",
}


class ReportWorker(BaseWorker):
    """운영 리포트 조립."""

    name = "report"

    def run(
        self,
        asof: str,
        query: str | None = None,
        sections: list[AgentResult] | None = None,
    ) -> Report:
        """Worker 결과를 중복 계산 없이 최종 리포트로 조립한다.

        Args:
            asof: 리포트 기준시각 문자열.
            query: ask mode에서 들어온 사용자 질문. report mode에서는 None.
            sections: Supervisor가 순차 실행한 Worker 결과 목록.

        Returns:
            조립된 최종 Report 객체.
        """
        worker_sections = sections or []
        title = "제조 Supervisor 운영 리포트"
        report_markdown = self._build_markdown(
            title=title,
            asof=self._asof_text(asof),
            query=query,
            sections=worker_sections,
        )
        key_actions, key_actions_total = self._build_key_actions(worker_sections)
        return Report(
            title=title,
            asof=self._asof_text(asof),
            sections=worker_sections,
            report_markdown=report_markdown,
            key_actions=key_actions,
            key_actions_total=key_actions_total,
        )

    def _build_markdown(
        self,
        *,
        title: str,
        asof: str,
        query: str | None,
        sections: list[AgentResult],
    ) -> str:
        """AgentResult 섹션과 evidence table을 markdown으로 이어 붙인다.

        Args:
            title: 리포트 제목.
            asof: 기준시각 문자열.
            query: 사용자 질문 또는 None.
            sections: Worker 결과 목록.

        Returns:
            HTML 액션 스냅샷과 Worker 섹션을 포함한 markdown 문자열.
        """
        lines = [
            f"# {title}",
            "",
            f"- 기준시각: {asof}",
        ]
        if query:
            lines.append(f"- 요청: {query}")
        lines.append("")

        summary = self._build_summary(sections)
        if summary:
            lines.extend(summary)
            lines.append("")

        action_snapshot = self._build_action_snapshot(sections)
        if action_snapshot:
            # 마커로 감싸 대시보드 드로어가 이 절만 고정 컴포넌트로 대체할 수 있게 한다
            lines.append(KEY_ACTIONS_MARKER_START)
            lines.extend(action_snapshot)
            lines.append(KEY_ACTIONS_MARKER_END)
            lines.append("")

        for section in sections:
            lines.extend(self._section_markdown(section))
            lines.append("")

        if not sections:
            lines.extend(["## 수집 결과", "", "수집된 Worker 결과가 없습니다.", ""])

        return "\n".join(lines).strip() + "\n"

    def _build_summary(self, sections: list[AgentResult]) -> list[str]:
        """Worker별 한 줄 요약을 모아 관리자용 요약 절을 만든다.

        Args:
            sections: Supervisor가 수집한 Worker 결과 목록.

        Returns:
            요약 절 markdown 라인 목록. Worker 결과가 없으면 빈 리스트.
        """
        if not sections:
            return []
        lines = ["## 요약", ""]
        for section in sections:
            role = SECTION_TITLES.get(section.agent, section.agent)
            lines.append(f"- **{role}** — {section.summary}")
        return lines

    def _section_markdown(self, result: AgentResult) -> list[str]:
        """Worker 결과를 markdown 섹션으로 변환한다.

        Args:
            result: 개별 Worker 실행 결과.

        Returns:
            섹션 제목, 요약, 알림, 근거 표를 포함한 markdown 라인 목록.
        """
        role = SECTION_TITLES.get(result.agent, result.agent)
        lines = [
            f"## {role} (`{result.agent}`)",
            "",
            result.summary,
        ]
        if result.alerts:
            lines.extend(["", "### 주요 알림"])
            lines.extend(f"- {alert}" for alert in result.alerts)

        for table_name, markdown in result.evidence_tables.items():
            lines.extend(["", f"### 근거 표: {table_name}", self._translate_headers(markdown)])

        return lines

    def _translate_headers(self, table: str) -> str:
        """markdown 표의 헤더 행만 COLUMN_LABELS 기준 한글 라벨로 바꾼다.

        데이터 행과 수치는 그대로 두며, 매핑에 없는 컬럼명은 원본을 유지한다.

        Args:
            table: df_to_markdown 형식의 markdown table 문자열.

        Returns:
            헤더가 한글화된 markdown table 문자열. 표 형식이 아니면 원문 그대로.
        """
        lines = table.splitlines()
        if not lines or not lines[0].strip().startswith("|"):
            return table
        headers = [cell.strip() for cell in lines[0].strip().strip("|").split("|")]
        translated = [COLUMN_LABELS.get(header, header) for header in headers]
        lines[0] = "| " + " | ".join(translated) + " |"
        return "\n".join(lines)

    def _build_action_snapshot(self, sections: list[AgentResult]) -> list[str]:
        """dispatching 결과의 상위 추천 액션을 markdown 표로 요약한다.

        HTML을 쓰지 않아 대시보드 드로어·CLI·README 어디서나 동일하게 렌더링된다.
        헤더는 한글 라벨로 표기한다 (원본 컬럼명 매핑은 COLUMN_LABELS, api-spec 2-1 동시 갱신).

        Args:
            sections: Supervisor가 수집한 Worker 결과 목록.

        Returns:
            report 상단에 넣을 액션 스냅샷 라인 목록. dispatching 결과가 없으면 빈 리스트.
        """
        dispatching = next((section for section in sections if section.agent == "dispatching"), None)
        if dispatching is None:
            return []

        markdown = dispatching.evidence_tables.get("reschedule_actions")
        if not markdown:
            return []

        rows = self._markdown_rows(markdown)
        if not rows:
            return []

        lines = [
            "## 핵심 추천 액션 (승인 필요 순)",
            "",
            "| # | 스케줄 | 원 설비 | 대체 설비 | 위험 등급 | 지연 완화(h) | 잔여 지연(h) | 이력 승인률 | 정책 점수 | 기대효과 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for index, row in enumerate(rows[:ACTION_SNAPSHOT_ROWS], start=1):
            lines.append(
                f"| {index} "
                f"| {row.get('schedule_id', '-')} "
                f"| {row.get('original_machine', '-')} "
                f"| **{row.get('alternative_machine', '-')}** "
                f"| {row.get('risk_level', '-')} "
                f"| {row.get('expected_delay_reduction_hr', '-')} "
                f"| {row.get('expected_remaining_delay_hr', '-')} "
                f"| {row.get('historical_acceptance_rate', '-')} "
                f"| {row.get('policy_score', '-')} "
                f"| {row.get('expected_effect', '-')} |"
            )
        if len(rows) > ACTION_SNAPSHOT_ROWS:
            lines.extend(
                [
                    "",
                    f"전체 {len(rows)}건 중 상위 {ACTION_SNAPSHOT_ROWS}건입니다. "
                    "전체 목록은 아래 설비 재배정 제안 절의 근거 표를 참고하세요.",
                ]
            )
        return lines

    def _build_key_actions(self, sections: list[AgentResult]) -> tuple[list[KeyAction], int]:
        """dispatching 근거 표에서 상위 추천 액션을 구조화 KeyAction 목록으로 추출한다.

        markdown 스냅샷 표와 같은 원천(reschedule_actions 근거 표)·같은 상위 N 규칙을 쓴다.
        수치는 tool 산출값 문자열을 타입 변환만 하며, 변환 실패 시 None으로 둔다
        (수치를 새로 만들지 않는다).

        Args:
            sections: Supervisor가 수집한 Worker 결과 목록.

        Returns:
            (상위 KeyAction 목록, 전체 추천 건수) 튜플. dispatching 결과가 없으면 ([], 0).
        """
        dispatching = next((section for section in sections if section.agent == "dispatching"), None)
        if dispatching is None:
            return [], 0

        markdown = dispatching.evidence_tables.get("reschedule_actions")
        if not markdown:
            return [], 0

        rows = self._markdown_rows(markdown)
        key_actions = [
            KeyAction(
                rank=index,
                action_id=row.get("action_id") or None,
                schedule_id=row.get("schedule_id") or "-",
                original_machine=row.get("original_machine") or None,
                alternative_machine=row.get("alternative_machine") or None,
                risk_level=row.get("risk_level") or None,
                impact=row.get("impact") or None,
                estimated_delay_hr=_parse_float(row.get("estimated_delay_hr")),
                expected_delay_reduction_hr=_parse_float(row.get("expected_delay_reduction_hr")),
                expected_remaining_delay_hr=_parse_float(row.get("expected_remaining_delay_hr")),
                historical_acceptance_rate=_parse_float(row.get("historical_acceptance_rate")),
                historical_sample_count=_parse_int(row.get("historical_sample_count")),
                policy_score=_parse_float(row.get("policy_score")),
                expected_effect=row.get("expected_effect") or None,
                quality_history_note=row.get("quality_history_note") or None,
            )
            for index, row in enumerate(rows[:ACTION_SNAPSHOT_ROWS], start=1)
        ]
        return key_actions, len(rows)

    def _markdown_rows(self, table: str) -> list[dict[str, str]]:
        """df_to_markdown 형식의 표를 행 목록으로 변환한다.

        Args:
            table: markdown table 문자열.

        Returns:
            헤더를 키로 사용하는 row dict 목록.
        """
        lines = [line.strip() for line in table.splitlines() if line.strip()]
        if len(lines) < 3 or not lines[0].startswith("|"):
            return []

        headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
        rows: list[dict[str, str]] = []
        for line in lines[2:]:
            values = [cell.strip() for cell in line.strip("|").split("|")]
            if len(values) != len(headers):
                continue
            rows.append(dict(zip(headers, values, strict=True)))
        return rows


def _parse_float(value: str | None) -> float | None:
    """근거 표에서 읽은 수치 문자열을 float으로 변환한다. 변환 불가하면 None."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    """근거 표에서 읽은 정수 문자열을 int로 변환한다. 변환 불가하면 None."""
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None
