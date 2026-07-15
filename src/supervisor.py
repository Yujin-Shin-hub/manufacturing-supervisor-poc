"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: Supervisor 조율 로직으로 라우팅 호출, Worker 순차 실행, 결과 취합을 담당한다.
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 - 스텁 생성 (구현은 단계 5)
  - 2026-07-06: 단계 5 report/ask 모드 Worker 순차 실행 및 partial failure 구현
  - 2026-07-06: 단계 6 EventBus 실행 이벤트 발행 연결
  - 2026-07-07: 단계 7 SSE 스펙용 tool_call/action_proposed/approval_required 이벤트 보강
  - 2026-07-07: 단계 8 재조정 제안 큐용 action_proposed 필드 확장
                (original_machine·impact·efficiency_gain, api-spec 2-1)
  - 2026-07-14: 대시보드 리포트 A안 — run_end에 key_actions/key_actions_total 필드 추가
                (드로어 고정 컴포넌트용 구조화 데이터, api-spec 2-1 동시 갱신)
"""

from __future__ import annotations

from src import router
from src.agents import (
    DelayPredWorker,
    DispatchingWorker,
    FieldStatusWorker,
    ReportWorker,
    RiskAlertWorker,
    SchedulingPolicyWorker,
    SupervisorValidation,
)
from src.agents.base import BaseWorker
from src.events import EventBus, EventName
from src.schemas import AgentResult, Report, WorkerAgentName


REPORT_WORKER_ORDER: list[WorkerAgentName] = [
    "field_status",
    "risk_alert",
    "delay_pred",
    "dispatching",
    "scheduling_policy",
]
SSE_TOOL_NAMES = {
    "score_delay_risk",
    "find_machine_candidates",
    "build_reschedule_actions",
    "summarize_status",
    "df_to_markdown",
}


class Supervisor:
    """요청 접수, 라우팅, Worker 조율, 결과 취합을 담당한다."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """EventBus와 Worker 인스턴스를 준비한다.

        Args:
            event_bus: 실행 이벤트를 발행할 EventBus. None이면 이벤트 발행 없이 동작한다.

        Returns:
            None.
        """
        self._event_bus: EventBus | None = event_bus
        self._workers: dict[WorkerAgentName, BaseWorker] = {
            "field_status": FieldStatusWorker(),
            "risk_alert": RiskAlertWorker(),
            "delay_pred": DelayPredWorker(),
            "dispatching": DispatchingWorker(),
            "scheduling_policy": SchedulingPolicyWorker(),
        }
        self._validator: SupervisorValidation = SupervisorValidation()
        self._report_worker: ReportWorker = ReportWorker()

    def run(
        self,
        mode: str,
        asof: str,
        query: str | None = None,
        llm_provider: str | None = None,
    ) -> Report:
        """실행 모드에 맞는 Worker를 순차 실행하고 최종 Report를 반환한다.

        Args:
            mode: 실행 모드. `"report"` 또는 `"ask"`만 허용한다.
            asof: 데이터 조회와 리포트 생성 기준시각 문자열.
            query: ask mode에서 라우팅에 사용할 사용자 질문. report mode에서는 None.
            llm_provider: 라우팅 LLM provider 선택값. `"auto"`, `"qwen"`, `"openai"` 중 하나.

        Returns:
            Worker 결과를 취합한 최종 Report.

        Raises:
            ValueError: mode가 허용값이 아니거나 ask mode에서 query가 비어 있을 때.
            Exception: report Worker 실행 실패처럼 복구 불가능한 오류가 발생할 때.
        """
        if self._event_bus:
            self._event_bus.reset()

        normalized_mode = mode.strip().lower()
        self._publish("run_start", mode=normalized_mode, asof=asof, query=query)

        if normalized_mode == "report":
            target_agents = REPORT_WORKER_ORDER
            report_query = None
            self._publish(
                "routing_decision",
                target_agents=target_agents,
                execution_order="sequential",
                reason="report mode fixed worker order",
            )
        elif normalized_mode == "ask":
            if not query or not query.strip():
                self._publish(
                    "error",
                    agent=None,
                    message="query is required when mode='ask'",
                    recoverable=False,
                )
                self._publish(
                    "run_end",
                    status="failed",
                    report_markdown=None,
                    key_actions=None,
                    key_actions_total=None,
                )
                raise ValueError("query is required when mode='ask'")
            decision = router.route(query, provider=llm_provider)
            target_agents = self._with_policy_agent(list(decision.target_agents))
            report_query = query
            self._publish(
                "routing_decision",
                target_agents=target_agents,
                execution_order=decision.execution_order,
                reason=decision.reason,
            )
        else:
            self._publish(
                "error",
                agent=None,
                message="mode must be one of: report, ask",
                recoverable=False,
            )
            self._publish(
                "run_end",
                status="failed",
                report_markdown=None,
                key_actions=None,
                key_actions_total=None,
            )
            raise ValueError("mode must be one of: report, ask")

        results = [
            self._run_worker(agent_name, asof=asof, query=report_query)
            for agent_name in target_agents
        ]
        validation = self._run_supervisor_validation(results)
        report_sections = [*results, validation]

        try:
            self._publish("agent_start", agent="report")
            report = self._report_worker.run(
                asof=asof,
                query=report_query,
                sections=report_sections,
            )
            self._publish("agent_end", agent="report", summary=report.title, alerts=[])
            self._publish(
                "run_end",
                status="done",
                report_markdown=report.report_markdown,
                key_actions=[action.model_dump() for action in report.key_actions],
                key_actions_total=report.key_actions_total,
            )
            return report
        except Exception as exc:
            self._publish(
                "error",
                agent="report",
                message=str(exc),
                recoverable=False,
            )
            self._publish(
                "run_end",
                status="failed",
                report_markdown=None,
                key_actions=None,
                key_actions_total=None,
            )
            raise

    def _run_worker(
        self,
        agent_name: WorkerAgentName,
        *,
        asof: str,
        query: str | None,
    ) -> AgentResult:
        """개별 Worker를 실행하고 실패 시 수집 실패 AgentResult로 대체한다.

        Args:
            agent_name: 실행할 Worker 이름.
            asof: Worker 데이터 조회 기준시각 문자열.
            query: ask mode 사용자 질문. report mode에서는 None.

        Returns:
            Worker가 생성한 AgentResult. Worker가 실패하면 수집 실패를 나타내는 AgentResult.
        """
        try:
            self._publish("agent_start", agent=agent_name)
            result = self._workers[agent_name].run(asof=asof, query=query)
            self._publish_tool_calls(result)
            self._publish(
                "agent_end",
                agent=agent_name,
                summary=result.summary,
                alerts=result.alerts,
            )
            if agent_name == "dispatching":
                self._publish_dispatching_actions(result)
            return result
        except Exception as exc:
            self._publish(
                "error",
                agent=agent_name,
                message=str(exc),
                recoverable=True,
            )
            return AgentResult(
                agent=agent_name,
                summary=f"수집 실패: {agent_name} Worker 실행 중 오류가 발생했습니다.",
                evidence_tables={"error": "수집 실패"},
                alerts=[f"{agent_name}: {exc}"],
                tool_calls_used=[],
            )

    def _with_policy_agent(self, target_agents: list[WorkerAgentName]) -> list[WorkerAgentName]:
        """dispatching 요청이면 scheduling_policy를 바로 뒤에 자동 삽입한다."""
        if "dispatching" not in target_agents or "scheduling_policy" in target_agents:
            return target_agents
        result: list[WorkerAgentName] = []
        for agent_name in target_agents:
            result.append(agent_name)
            if agent_name == "dispatching":
                result.append("scheduling_policy")
        return result

    def _run_supervisor_validation(self, results: list[AgentResult]) -> AgentResult:
        """report 직전 Supervisor 검증 단계를 수행한다."""
        try:
            self._publish("agent_start", agent="supervisor_validation")
            validation = self._validator.run(results)
            self._publish(
                "agent_end",
                agent="supervisor_validation",
                summary=validation.summary,
                alerts=validation.alerts,
            )
            return validation
        except Exception as exc:
            self._publish(
                "error",
                agent="supervisor_validation",
                message=str(exc),
                recoverable=True,
            )
            return AgentResult(
                agent="supervisor_validation",
                summary=f"Supervisor 검증 실패: {exc}",
                evidence_tables={"validation_checks": "| check | status | message |\n| --- | --- | --- |\n| supervisor_validation | WARN | validation failed |"},
                alerts=[str(exc)],
                tool_calls_used=[],
            )

    def _publish(self, event: EventName, **payload: object) -> None:
        """EventBus가 주입된 경우에만 실행 이벤트를 발행한다.

        Args:
            event: api-spec에 정의된 이벤트 이름.
            **payload: 이벤트 data에 포함할 payload 필드.

        Returns:
            None.
        """
        if self._event_bus:
            self._event_bus.publish(event, **payload)

    def _publish_tool_calls(self, result: AgentResult) -> None:
        """AgentResult의 tool 사용 내역 중 SSE 스펙에 허용된 tool_call만 발행한다.

        Args:
            result: Worker 실행 결과. `tool_calls_used`와 evidence table을 참조한다.

        Returns:
            None.
        """
        for tool_name in result.tool_calls_used:
            if tool_name not in SSE_TOOL_NAMES:
                continue
            self._publish(
                "tool_call",
                agent=result.agent,
                tool=tool_name,
                rows=self._estimate_evidence_rows(result),
            )

    def _publish_dispatching_actions(self, result: AgentResult) -> None:
        """dispatching 결과의 reschedule action 표를 action 이벤트로 발행한다.

        Args:
            result: dispatching Worker의 AgentResult.

        Returns:
            None.
        """
        table = result.evidence_tables.get("reschedule_actions")
        if not table or table == "_No rows_":
            return

        rows = self._markdown_rows(table)
        for row in rows:
            action_id = row.get("action_id")
            schedule_id = row.get("schedule_id")
            risk_level = row.get("risk_level")
            alternative_machine = row.get("alternative_machine")
            if not action_id or not schedule_id or not risk_level:
                continue

            approval_required = risk_level in {"HIGH", "CRITICAL"}
            self._publish(
                "action_proposed",
                action_id=action_id,
                schedule_id=schedule_id,
                risk_level=risk_level,
                original_machine=row.get("original_machine"),
                alternative_machine=alternative_machine,
                impact=row.get("impact"),
                efficiency_gain=_parse_float(row.get("efficiency_gain")),
                expected_delay_reduction_hr=_parse_float(row.get("expected_delay_reduction_hr")),
                expected_remaining_delay_hr=_parse_float(row.get("expected_remaining_delay_hr")),
                historical_acceptance_rate=_parse_float(row.get("historical_acceptance_rate")),
                historical_sample_count=_parse_int(row.get("historical_sample_count")),
                historical_avg_efficiency_gain=_parse_float(row.get("historical_avg_efficiency_gain")),
                quality_risk_count=_parse_int(row.get("quality_risk_count")),
                quality_risk_rate=_parse_float(row.get("quality_risk_rate")),
                policy_score=_parse_float(row.get("policy_score")),
                policy_decision_reason=row.get("policy_decision_reason"),
                expected_effect=row.get("expected_effect"),
                quality_history_note=row.get("quality_history_note"),
                approval_required=approval_required,
            )
            if approval_required:
                self._publish(
                    "approval_required",
                    action_id=action_id,
                    schedule_id=schedule_id,
                    risk_level=risk_level,
                    required_response="accept_or_reject",
                )

    def _estimate_evidence_rows(self, result: AgentResult) -> int:
        """AgentResult의 markdown evidence table 중 최대 data row 수를 계산한다.

        Args:
            result: row 수를 추정할 Worker AgentResult.

        Returns:
            evidence table이 가진 최대 data row 수. evidence가 없으면 0.
        """
        if not result.evidence_tables:
            return 0
        return max(
            (len(self._markdown_rows(table)) for table in result.evidence_tables.values()),
            default=0,
        )

    def _markdown_rows(self, table: str) -> list[dict[str, str]]:
        """df_to_markdown 산출 표를 이벤트 payload 계산용 row dict로 변환한다.

        Args:
            table: `df_to_markdown`이 생성한 markdown table 문자열.

        Returns:
            header를 key로 사용하는 row dict 목록. table 형식이 아니면 빈 리스트.
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
    """markdown 근거 표에서 읽은 수치 문자열을 float으로 변환한다.

    Args:
        value: 근거 표 셀 문자열. 없거나 숫자가 아니면 None 처리한다.

    Returns:
        변환된 float 값. 변환 불가하면 None (수치를 임의로 만들지 않는다).
    """
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    """markdown 근거 표에서 읽은 정수 문자열을 int로 변환한다."""
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None
