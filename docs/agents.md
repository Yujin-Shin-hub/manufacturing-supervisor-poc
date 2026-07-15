# agents.md — 에이전트 명세와 라우팅 규칙

```
작성자 : 신유진
작성 목적 : Worker Agent별 책임·입출력 계약·프롬프트 원칙 정의
```

## 공통 계약

모든 Worker는 동일한 인터페이스를 따른다.

- 입력: `asof: Timestamp`, `query: str | None` (리포트 모드면 None)
- 출력: `AgentResult` (pydantic)

```json
{
  "agent": "dispatching",
  "summary": "사람이 읽는 2~3문장 요약",
  "evidence_tables": {"risk": "<markdown table>", "machine_candidates": "<markdown table>"},
  "alerts": ["SCH-0003 ETCH_VIA 작업은 ETCH-105 정지 상태로 ETCH-102 대체 배정 권고"],
  "tool_calls_used": ["find_machine_candidates", "build_reschedule_actions"]
}
```

- `evidence_tables`의 표는 반드시 tool이 반환한 것을 그대로 넣는다. LLM이 표를 재작성하지 않는다.
- `summary`·`alerts` 문구만 LLM이 생성한다.

## Worker Agent 7종

| 에이전트 | 책임 | 사용 tool | 산출 핵심 |
|---|---|---|---|
| `field_status` | 공정군 내 작업·설비 상태 요약 | load_schedule, load_work_status | schedule별 현재 상태 표 |
| `risk_alert` | HIGH/CRITICAL 위험 작업 알림 | load_delay_risk | 위험 schedule 목록 + 알림 문구 |
| `delay_pred` | 지연 위험과 예상 지연 영향 판단 | score_delay_risk, load_delay_risk | risk_score, delay_probability, estimated_delay_hr |
| `dispatching` | 대체 설비와 작업 순서 재조정 추천 | find_machine_candidates, build_reschedule_actions | 대체 설비 후보 + reschedule_action |
| `scheduling_policy` | 과거 재조정 이력 기반 추천 검증 | build_reschedule_actions | policy_score, 기대 지연 완화, 이력 승인률, 품질성 risk 이력 |
| `supervisor_validation` | report 전 Worker 결과 교차 검증 | 내부 검증 로직 | 리스크·추천·policy 기대효과 일관성 검증 |
| `report` | 위 결과들을 Supervisor 운영 리포트로 조립 | formatting (표 변환만) | 근거 표 포함 최종 리포트 |

`scheduling_policy`는 LLM 판단이 아니라 deterministic policy layer다. `reschedule_action.csv`의 과거
적용률, 과거 `efficiency_gain`, 후보 설비의 품질성 risk 이력, 현재 부하·setup time을 조합해
`dispatching` 추천의 기대효과와 정책 점수를 검증한다.

`supervisor_validation`과 `report`는 다른 Worker의 `AgentResult`들을 입력으로 받는 특수 단계다.
`supervisor_validation`은 리포트 직전에 리스크·재조정 추천·policy 기대효과가 서로 연결되는지 검증하고,
`report`는 검증된 결과를 최종 markdown으로 조립한다.

## 라우팅 규칙 (Routing Agent 판단 기준)

| 요청 패턴 예시 | 라우팅 |
|---|---|
| "지금 공정군 상태 어때?", "SCH-0003 상태 보여줘" | field_status |
| "위험한 작업 있어?", "CRITICAL 리스크만 보여줘" | risk_alert |
| "이러다 납기 늦는 거 아냐?", "예상 지연 시간이 큰 건 뭐야?" | delay_pred |
| "어느 설비로 바꿀 수 있어?", "순서 다시 짜줘" | dispatching |
| "오늘 리포트 줘", `--mode report` 트리거 | field_status + risk_alert + delay_pred + dispatching + scheduling_policy → supervisor_validation → report |
| 판단 불가·모호 | field_status 폴백 (reason에 폴백 명시) |

복수 매칭 시 `execution_order: "sequential"`로 의존 순서를 지정한다
(예: dispatching 이후에는 scheduling_policy가 과거 이력 기반 기대효과를 검증하고, report 전에는 supervisor_validation이 전체 결과를 교차 검증).

## 프롬프트 작성 원칙

1. system prompt는 역할 1문단 + 금지사항(수치 창작 금지, 표 재작성 금지) + 출력 스키마 안내로 짧게 유지
2. backstory식 서사("당신은 20년차 슈퍼바이저...")는 쓰지 않는다 — 노이즈
3. 출력은 전부 structured output(`response_format: json_schema`)으로 강제한다
4. 표는 markdown 그대로 전달하고, 코드펜스(```)로 감싸지 않는다 (프로토타입에서 확인된 이슈)
5. 한국어로 응답하되 schedule_id, process_step, machine_id는 원문 유지
