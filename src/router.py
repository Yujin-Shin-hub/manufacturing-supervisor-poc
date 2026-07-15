"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: Routing Agent - LLM 1회 호출로 대상 Worker 결정 + 스키마 검증
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 시 스텁 생성
  - 2026-07-06: 단계 3 Routing Agent 구현, field_status fallback 추가
  - 2026-07-06: 라우팅 prompt 본문을 한국어로 정리
"""

from __future__ import annotations

from src.llm import complete_json
from src.schemas import RoutingDecision


ROUTER_SYSTEM_PROMPT = (
    "당신은 제조 현장 Supervisor PoC의 라우팅 에이전트입니다. "
    "요청을 분석해 실행해야 할 Worker agent만 선택하세요. "
    "응답은 요청된 스키마와 일치하는 유효한 JSON만 반환하세요. "
    "카탈로그에 없는 Worker agent를 만들지 마세요. "
    "숫자, 일정, 설비, tool 결과를 추정하거나 창작하지 마세요. "
    "execution_order는 항상 'sequential'을 사용하세요."
)

AGENT_CATALOG = """
Worker 카탈로그:
- field_status: 현재 공정, 스케줄, 작업, Lot, 설비, 현장 상태를 조회하거나 요약한다.
- risk_alert: HIGH/CRITICAL 위험 작업, 긴급 리스크, 위험 스케줄 목록을 확인한다.
- delay_pred: 지연 가능성, 예상 지연 영향, 지연 사유를 판단한다.
- dispatching: 대체 설비, 재스케줄링, 작업 순서 재조정, dispatch 추천을 수행한다.
- scheduling_policy: dispatching 추천을 과거 승인/적용 이력, 기대 지연 완화, 품질성 risk 이력으로 검증한다.

라우팅 규칙:
- 리포트 요청은 field_status, risk_alert, delay_pred, dispatching, scheduling_policy 순서로 라우팅한다.
- 복수 의도가 있으면 위 카탈로그 순서에 맞춰 여러 Worker를 포함할 수 있다.
- 기대효과, 과거 이력, 승인률, 품질 영향까지 묻는 재조정 요청은 dispatching 뒤에 scheduling_policy를 포함한다.
- 모호하거나 지원하지 않는 요청은 field_status로 라우팅하고 reason에 fallback임을 명시한다.
"""

ROUTER_USER_TEMPLATE = """
아래 사용자 요청을 처리하는 데 필요한 최소 Worker agent로 라우팅하세요.

{agent_catalog}

사용자 요청:
{query}

다음 JSON 필드를 반환하세요:
- target_agents: Worker agent 이름 목록
- execution_order: "sequential"
- reason: 선택한 라우팅 사유를 짧은 한국어 문장으로 작성
"""

FALLBACK_REASON = "라우팅 입력이 비었거나 실패하여 field_status로 기본 라우팅했습니다."


def _fallback_decision(reason: str = FALLBACK_REASON) -> RoutingDecision:
    return RoutingDecision(
        target_agents=["field_status"],
        execution_order="sequential",
        reason=reason,
    )


def _build_prompt(query: str) -> str:
    return ROUTER_USER_TEMPLATE.format(
        agent_catalog=AGENT_CATALOG.strip(),
        query=query.strip(),
    )


def route(query: str, *, provider: str | None = None) -> RoutingDecision:
    """사용자 요청을 실행할 Worker 목록으로 라우팅한다."""
    normalized_query = query.strip()
    if not normalized_query:
        return _fallback_decision("빈 요청이므로 field_status로 기본 라우팅했습니다.")

    try:
        return complete_json(
            _build_prompt(normalized_query),
            RoutingDecision,
            provider=provider,
            system_prompt=ROUTER_SYSTEM_PROMPT,
        )
    except Exception:
        return _fallback_decision()
