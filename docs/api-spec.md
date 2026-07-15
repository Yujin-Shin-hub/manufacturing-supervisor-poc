# api-spec.md — REST·SSE API 명세

```
작성자 : 신유진
작성 목적 : 대시보드·CLI가 사용하는 API 계약 정의. 서버(단계 7)·대시보드(단계 8) 구현 기준 문서
필드 원칙 : 데이터 조회 API는 data/*.csv에 실존하는 컬럼만 사용한다.
           승인/거절·재추천 같은 workflow 필드는 이 문서에 정의된 payload에서만 추가할 수 있다.
```

## 0. 공통

- Base URL: `http://localhost:8000`
- 프론트 개발 모드에서는 Vite dev 서버(5173)가 `/run`·`/events`·`/api`·`/health`를
  8000으로 proxy한다 — CORS 미들웨어를 추가하지 않는다 (경로·계약은 동일)
- 모든 응답 JSON은 UTF-8. 시각 문자열 포맷은 데이터 원본과 동일하게
  `YYYY-MM-DD HH:MM`(분 단위), 날짜는 `YYYY-MM-DD`
- 식별자 표기는 원본 그대로: `schedule_id`(SCH-0001), `machine_id`(ETCH-102),
  `risk_id`(RSK-0001), `action_id`(ACT-0001), `po_id`(LOT20260415-001)
- 에러는 FastAPI 표준 `{"detail": "<사유>"}`

## 1. REST 엔드포인트

### 1-1. 시스템

| 메서드/경로 | 역할 | 응답 |
|---|---|---|
| `GET /` | `frontend/dist` 정적 서빙 (Vue 3 빌드 산출물) | text/html |
| `GET /health` | 상태 확인 | `{"status": "ok"}` |

### 1-2. `POST /run` — Supervisor 실행 트리거

요청:

```json
{"mode": "ask", "asof": "2026-04-15 10:00", "query": "ETCH-105 멈췄는데 어디로 돌려?", "llm_provider": "auto"}
```

| 필드 | 타입 | 규칙 |
|---|---|---|
| mode | str | `"ask"` 또는 `"report"` (`"auto"`는 단계 11에서 센서 트리거 전용으로 추가 예약) |
| asof | str | 기준시각. 생략 시 서버가 데이터 내 최신 `work_event_log.event_time` 기준으로 결정 |
| query | str? | mode="ask"일 때 필수, "report"일 때 무시 |
| llm_provider | str? | `"auto"` \| `"qwen"` \| `"openai"`. 생략 시 환경변수 `LLM_PROVIDER`, 그것도 없으면 `"auto"` |

응답: `202 {"status": "started"}` / 이미 실행 중이면 `409 {"detail": "run in progress"}`
(실행 결과는 REST가 아니라 SSE로 전달된다 — 2장)

### 1-2-1. LLM provider 선택

provider 선택은 실행 단위로 가능하지만 API key는 절대 요청으로 받지 않는다.
키와 모델명은 서버의 `.env`에서만 읽는다.

| llm_provider | 의미 | 필요 환경변수 |
|---|---|---|
| `auto` | Qwen을 먼저 호출하고 실패 시 OpenAI로 fallback | Qwen env + 선택적으로 OpenAI env |
| `qwen` | Qwen/OpenAI-compatible endpoint만 사용 | `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL_NAME` |
| `openai` | OpenAI API만 사용 | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL_NAME` |

`auto`에서 Qwen 호출이 실패하고 OpenAI fallback이 성공하면 SSE `llm_provider_selected` 이벤트를 발행한다.
fallback이 불가능하면 해당 Agent는 recoverable error로 종료하고 Supervisor는 가능한 partial result를 계속 조립한다.

### 1-3. 데이터 조회 (대시보드 초기 로드·근거 확인용, 읽기 전용)

응답 필드는 **해당 CSV의 컬럼 그대로** 반환한다 (부록 A가 유일한 필드 사전).
공통 형태: `{"asof": "...", "rows": [ {<CSV 컬럼 그대로>}, ... ]}`

| 메서드/경로 | 원본 테이블 | 쿼리 파라미터 (모두 선택) |
|---|---|---|
| `GET /api/schedules` | schedule_master | `status`, `process_step` |
| `GET /api/work-status` | work_status | `machine_id`, `schedule_id` |
| `GET /api/risks` | delay_risk | `risk_level`, `schedule_id` |
| `GET /api/machines` | machine_process_map | `process_step`, `available_yn`, `qualified_yn` |
| `GET /api/actions` | reschedule_action | `applied_yn`, `schedule_id` |
| `GET /api/risk-summary` | score_delay_risk(asof) 집계 | `asof` (생략 시 서버 기본 기준시각) |

- 쿼리 파라미터는 전부 원본 컬럼명과 동일한 이름·값으로만 필터한다
- `GET /api/risk-summary`는 원본 테이블 조회가 아니라 **risk_alert Worker와 동일한
  `score_delay_risk(asof)` tool 결과의 건수 집계**다 —
  응답: `{"asof": ..., "total": int, "critical": int, "high": int}`.
  대시보드 KPI "CRITICAL 리스크"가 리포트의 리스크 알림과 같은 숫자를 쓰게 하기 위한
  엔드포인트 (2026-07-14 추가, 수치 정합 원칙)
- 정렬 기본값: schedules는 `priority` 오름차순, risks는 `risk_score` 내림차순,
  actions는 `action_time` 내림차순 (모두 실존 컬럼 기준)
- 그 외 테이블(production_plan, work_event_log, historical_ct, delay_history,
  line_assignment, line_master, operator_master, process_master, real_time_production)은
  tool 내부 계산용으로만 쓰고 **API로 노출하지 않는다** (스코프 가드)

### 1-4. 재조정 액션 승인/거절/재추천

이 절의 엔드포인트는 `reschedule_action.csv` 원본 조회가 아니라 supervisor 의사결정 workflow다.

구현 상태 (2026-07-07, 단계 8 대시보드 HITL):

- **승인/거절 구현됨** — run 중 발행된 `action_proposed`를 서버 in-memory `ActionRegistry`가 수집하고,
  `accept`/`reject` 처리 시 SSE `action_accepted`/`action_rejected`를 발행한다.
  이력 저장 없음(스코프 가드) — 새 `run_start` 시 이전 PENDING 제안은 EXPIRED로 만료되어 409를 반환한다.
- **재추천(repropose)·에스컬레이션(escalate)은 계약만 정의된 상태**다. 따라서 현재
  거절 응답의 `reproposal_available`은 항상 `false`다.

#### 액션 상태

`applied_yn='N'`은 "거절"이 아니라 **아직 승인되지 않은 제안**이다. UI/API에서는 아래 상태로 해석한다.

| action_status | 의미 |
|---|---|
| `PENDING` | 액션이 제안됐고 아직 응답 없음 (`applied_yn='N'`) |
| `ACCEPTED` | supervisor가 승인함 (`applied_yn='Y'`) |
| `REJECTED` | 제안을 거절함. 원본 CSV에는 즉시 반영하지 않고 workflow 이벤트로 기록 |
| `REPROPOSED` | 거절 후 조건을 바꿔 다음 후보를 재추천함 |
| `ESCALATED` | 후보 없음, 반복 거절, 납기 초과 등으로 supervisor 수동 확인 필요 |
| `EXPIRED` | 기준시각 또는 현장 상태 변화로 제안이 더 이상 유효하지 않음 |

#### 승인

`POST /api/actions/{action_id}/accept`

요청:

```json
{
  "supervisor_id": "SUP-001",
  "comment": "ETCH-102 투입 가능 확인"
}
```

응답:

```json
{
  "action_id": "ACT-0001",
  "schedule_id": "SCH-0003",
  "action_status": "ACCEPTED",
  "applied_yn": "Y",
  "decision_time": "2026-04-15 14:05"
}
```

#### 거절

`POST /api/actions/{action_id}/reject`

요청:

```json
{
  "supervisor_id": "SUP-001",
  "reject_reason": "setup_time_too_long",
  "comment": "납기 우선이라 setup time 더 짧은 설비 필요"
}
```

`reject_reason` 허용값:

| reject_reason | 의미 |
|---|---|
| `machine_reserved` | 후보 설비가 이미 예약됨 |
| `operator_unavailable` | 작업자/교대 인력 부족 |
| `recipe_not_ready` | recipe 또는 qualification 준비 미완료 |
| `quality_risk` | 품질/공정 리스크 우려 |
| `setup_time_too_long` | setup 시간이 길어 납기 대응에 부적합 |
| `priority_changed` | 납기/고객/생산 priority가 변경됨 |
| `manual_override` | 현장 판단으로 수동 override |
| `other` | 기타 |

응답:

```json
{
  "action_id": "ACT-0001",
  "schedule_id": "SCH-0003",
  "action_status": "REJECTED",
  "reject_reason": "setup_time_too_long",
  "reproposal_available": true
}
```

#### 재추천

`POST /api/actions/{action_id}/repropose`

supervisor가 거절 후 빠르게 조건을 조정하기 위한 API다. 가중치는 0~1 범위이며 합계는 1.0을 권장한다.
서버는 합계가 1.0이 아니면 정규화할 수 있고, 정규화 여부를 응답의 `policy_normalized`로 알린다.

요청:

```json
{
  "supervisor_id": "SUP-001",
  "reject_reason": "setup_time_too_long",
  "weights": {
    "due_priority": 0.35,
    "risk_score": 0.25,
    "current_load": 0.20,
    "setup_time": 0.15,
    "preferred_rank": 0.05
  },
  "constraints": {
    "max_current_load": 0.6,
    "require_available": true,
    "exclude_machines": ["ETCH-102"]
  }
}
```

응답:

```json
{
  "previous_action_id": "ACT-0001",
  "action_status": "REPROPOSED",
  "policy_normalized": false,
  "candidate": {
    "machine_id": "ETCH-104",
    "candidate_rank": 1,
    "why_recommended": [
      "process_step=ETCH_VIA 처리 가능",
      "qualified_yn=Y",
      "machine_status=가동",
      "current_load=0.44 <= max_current_load=0.60",
      "setup_time_min=23"
    ],
    "score_breakdown": {
      "due_priority": 0.35,
      "risk_score": 0.25,
      "current_load": 0.20,
      "setup_time": 0.15,
      "preferred_rank": 0.05
    }
  }
}
```

### 1-5. 에스컬레이션

에스컬레이션은 자동 재추천으로 바로 처리하기 어렵거나, 거절 이후에도 위험이 남아
supervisor가 수동으로 확인해야 하는 상태다.

`POST /api/actions/{action_id}/escalate`

요청:

```json
{
  "supervisor_id": "SUP-001",
  "escalation_reason": "no_candidate_after_reject",
  "comment": "CRITICAL인데 대체 설비 후보 없음"
}
```

`escalation_reason` 허용값:

| escalation_reason | 조건 |
|---|---|
| `no_candidate_after_reject` | CRITICAL 액션이 거절됐고 다음 후보가 없음 |
| `repeated_rejection` | CRITICAL 액션이 2회 이상 거절됨 |
| `due_overrun` | 납기 초과 상태에서 승인 대기 지속 |
| `quality_risk` | 품질 리스크 사유로 거절됨 |
| `manual_override` | 현장 수동 override로 자동 추천을 중단해야 함 |
| `risk_score_extreme` | `risk_score >= 95` |

응답:

```json
{
  "action_id": "ACT-0001",
  "schedule_id": "SCH-0003",
  "action_status": "ESCALATED",
  "escalation_required": true,
  "escalation_level": "supervisor_manual_review",
  "escalation_reason": "no_candidate_after_reject"
}
```

## 2. SSE — `GET /events`

- `Content-Type: text/event-stream`
- 프레임 형식: `id`(seq, 1부터 단조 증가) + `event`(타입명) + `data`(JSON 한 줄)

```
id: 3
event: agent_start
data: {"seq": 3, "ts": "2026-04-15 10:00:02", "agent": "dispatching"}
```

- 모든 `data`에 공통 필드 `seq`(int)·`ts`(str) 포함. 발행 주체는 항상 코드(EventBus)다
- 연결 직후: 실행 중인 run이 있으면 해당 run의 **버퍼 전체를 seq 순으로 재전송**
  (Last-Event-ID 헤더가 있으면 그 이후만). 실행 중이 아니면 무이벤트 대기
- 버퍼는 현재/직전 run 1건만 메모리 유지 (이력 저장 없음 — 스코프 가드)

### 2-1. 이벤트 타입 정의

`agent` 값은 다음 일곱 개만 허용: `field_status` | `risk_alert` | `delay_pred` | `dispatching` | `scheduling_policy` | `supervisor_validation` | `report`

| event | data 필드 | 발행 시점 |
|---|---|---|
| `run_start` | `mode`, `asof`, `query`(ask만) | POST /run 수리 직후 |
| `llm_provider_selected` | `requested_provider`, `active_provider`, `fallback_used`, `model_name` | LLM 호출 provider가 확정됐을 때 |
| `routing_decision` | `target_agents`(agent 배열), `execution_order`("sequential"), `reason` | Routing Agent 응답 검증 통과 후 |
| `agent_start` | `agent` | Worker 실행 직전 |
| `tool_call` | `agent`, `tool`, `rows`(반환 DataFrame 행수, int) | tool 반환 직후 |
| `agent_end` | `agent`, `summary`, `alerts`(str 배열) | AgentResult 검증 통과 후 |
| `action_proposed` | `action_id`, `schedule_id`, `risk_level`, `original_machine`, `alternative_machine`, `impact`, `efficiency_gain`(float\|null), `expected_delay_reduction_hr`(float\|null), `expected_remaining_delay_hr`(float\|null), `historical_acceptance_rate`(float\|null), `historical_sample_count`(int\|null), `historical_avg_efficiency_gain`(float\|null), `quality_risk_count`(int\|null), `quality_risk_rate`(float\|null), `policy_score`(float\|null), `policy_decision_reason`(str\|null), `expected_effect`(str\|null), `quality_history_note`(str\|null), `approval_required` | 재조정 액션 제안 생성 시 |
| `approval_required` | `action_id`, `schedule_id`, `risk_level`, `required_response` | CRITICAL/HIGH 액션에 supervisor 응답이 필요할 때 |
| `action_accepted` | `action_id`, `schedule_id`, `supervisor_id` | 승인 API 처리 후 |
| `action_rejected` | `action_id`, `schedule_id`, `reject_reason`, `reproposal_available` | 거절 API 처리 후 |
| `action_reproposed` | `previous_action_id`, `schedule_id`, `alternative_machine`, `candidate_rank` | 재추천 API 처리 후 |
| `action_escalated` | `action_id`, `schedule_id`, `escalation_level`, `escalation_reason` | 에스컬레이션 발생 시 |
| `sensor_update` | `line`, `sensor`, `value`(float), `unit`, `observed_ts` | MQTT `factory/#` payload 검증 후 |
| `sensor_alert` | `line`, `sensor`, `rule`, `values`(float 배열), `unit` | 동일 라인·센서가 60초 내 3회 연속 임계 초과 시 |
| `error` | `agent`(특정 불가 시 null), `message`, `recoverable`(bool) | 예외 발생 시 |
| `run_end` | `status`("done"\|"failed"), `report_markdown`(report 성공 시, 아니면 null), `key_actions`(KeyAction 배열\|null), `key_actions_total`(int\|null) | run 종료 시 항상 1회 |

- `action_proposed`의 `original_machine`·`impact`·`efficiency_gain`은 dispatching 근거 표
  (`build_reschedule_actions` 결과)에서 그대로 가져온다 — 대시보드 "재조정 제안" 큐가
  전환 방향(원설비→대체설비)을 표시하기 위한 필드 (2026-07-07 추가).
  `efficiency_gain`은 근거 표 파싱이 실패하면 null (수치를 프론트가 만들지 않는다)
- `expected_delay_reduction_hr`, `expected_remaining_delay_hr`, `historical_acceptance_rate`,
  `historical_sample_count`, `historical_avg_efficiency_gain`, `quality_risk_count`,
  `quality_risk_rate`, `policy_score`, `policy_decision_reason`, `expected_effect`,
  `quality_history_note`는 `scheduling_policy` 기준으로 계산된 기대효과·이력 검증 필드다.
  이 값은 deterministic tool 결과에서만 오며, 중앙 승인 모달과 리포트 상단 추천 표가 같은 값을 사용한다.
- `tool` 값은 src/tools에 실존하는 함수명만: `score_delay_risk`, `find_machine_candidates`,
  `build_reschedule_actions`, `summarize_status`, `df_to_markdown` (추가 시 이 문서 갱신)
- `run_end.key_actions`는 리포트 상단 "핵심 추천 액션"의 구조화 데이터다 (2026-07-14 추가,
  드로어 고정 컴포넌트용). dispatching 근거 표(reschedule_actions)의 상위 5건을 코드가
  타입 변환만 해서 담는다 — 필드: `rank`, `action_id`, `schedule_id`, `original_machine`,
  `alternative_machine`, `risk_level`, `impact`, `estimated_delay_hr`,
  `expected_delay_reduction_hr`, `expected_remaining_delay_hr`, `historical_acceptance_rate`,
  `historical_sample_count`, `policy_score`, `expected_effect`, `quality_history_note`
  (수치 파싱 실패 시 null — 프론트가 수치를 만들지 않는다).
  `report_markdown`의 같은 절은 `<!-- key_actions:start/end -->` 마커로 감싸며,
  드로어는 key_actions가 있으면 그 절을 고정 컴포넌트로 대체한다 (CLI·README는 표 그대로)
- `report_markdown` 안의 근거 표 **데이터·수치는 원본 그대로**, **헤더 표기만 한글 라벨**을
  사용한다 (2026-07-14 변경 — 관리자용 리포트 가독성). 원본 컬럼명↔한글 라벨 매핑의
  단일 소스는 `src/agents/report.py`의 `COLUMN_LABELS`이며, API 응답(1-3)과 이벤트 payload
  필드명은 여전히 원본 CSV 컬럼명을 유지한다 (부록 A가 필드 사전)
- 기존 설계의 `report_done`은 `run_end`로 통합 — 실패로 끝나도 대시보드가
  종료를 알 수 있도록 "종료는 항상 run_end 1회" 규칙이 더 안전하다
- `sensor_update`/`sensor_alert`는 단계 10 MQTT 센서 스트림 이벤트다. payload 검증과 임계치 판정은
  `src/sensors/rules.py` 코드가 수행하며 LLM은 관여하지 않는다. `auto_run_triggered`는 단계 11
  자동 Supervisor 트리거에서 별도 추가한다.

### 2-2. 상태 정의 (대시보드 아키텍처 뷰의 유일한 기준)

**Run 상태** (전역 1개):

```
IDLE ──run_start──► RUNNING ──run_end(done)──► DONE
                       └──────run_end(failed)─► FAILED
```

**노드 상태** (Routing + Worker/검증/report 노드, 각각 독립):

```
PENDING ──agent_start──► RUNNING ──agent_end──► DONE
                            └──error(agent=자신)──► FAILED
(routing_decision.target_agents에 없는 Worker) ──► SKIPPED
```

| 이벤트 수신 | 상태 전이 |
|---|---|
| `run_start` | Run: IDLE→RUNNING. 모든 노드 PENDING으로 리셋 |
| `routing_decision` | Routing 노드 DONE. `target_agents` 미포함 Worker는 SKIPPED |
| `agent_start` | 해당 Worker PENDING→RUNNING |
| `agent_end` | 해당 Worker RUNNING→DONE |
| `error(recoverable=true)` | 해당 Worker FAILED, Run은 RUNNING 유지 (partial failure 허용) |
| `error(recoverable=false)` | 해당 Worker FAILED, 이후 `run_end(failed)`가 뒤따른다 |
| `run_end` | Run: RUNNING→DONE/FAILED. RUNNING으로 남은 노드가 있으면 FAILED 처리 |

**순서 보장** (서버 책임):

1. `seq`는 run 내에서 단조 증가하며 빠짐이 없다
2. `run_start`가 항상 첫 이벤트, `run_end`가 항상 마지막 이벤트
3. `routing_decision`은 모든 `agent_start`보다 앞선다
4. 한 Worker의 `agent_start` → `tool_call`* → `agent_end`는 연속 구간이다
   (execution_order가 sequential이므로 Worker 간 이벤트가 섞이지 않는다)
5. 대시보드는 위 보장을 신뢰하되, 상태 전이표에 없는 순서가 오면
   해당 이벤트를 무시하고 콘솔 경고만 남긴다 (화면 깨짐 방지)

## 3. 수치 타입·정밀도 정의

원칙: **자릿수는 데이터가 결정하고, 스키마는 자르지 않는다.**
직렬화(JSON)·내부 계산에서는 반올림하지 않고, 반올림은 표시 계층(df_to_markdown, 대시보드)에서만 1회 수행한다.
반도체 계측(CD·막두께 등) 데이터라면 소수점 3자리 이상이 필수지만, 이 데이터셋은
스케줄링·디스패칭 계열이라 실측 최대 정밀도는 2자리다. 단, 향후 계측성 필드 추가에
대비해 스키마는 자릿수 상한을 강제하지 않는다 (표시 자릿수만 고정).

### 3-1. float 필드 (실측 정밀도 기준)

| 필드 | 실측 정밀도 | 의미 해상도 | 값 범위 검증 | 표시 자릿수 |
|---|---|---|---|---|
| std_ct_sec, ct_sec_per_unit | 2dp | 10ms 단위 CT | > 0 | 2 |
| risk_score | 1dp | 점수(0~100) | 0 ≤ x ≤ 100 | 1 |
| delay_probability | 2dp | 확률(비율) | 0 ≤ x ≤ 1 | 2 |
| estimated_delay_hr, avg_process_hr, estimated_duration_hr | 1dp | 6분 단위 | ≥ 0 | 1 |
| current_load, utilization_rate, efficiency_gain | 2dp | 비율 | 0 ≤ x ≤ 1 | 2 |
| progress_pct | 1dp | 퍼센트 | 0 ≤ x ≤ 100 | 1 |

### 3-2. int 필드

quantity, target_qty, cumulative_qty, qty, priority, delay_min, severity,
resolution_time_min, setup_time_min, preferred_rank, new_sequence, original_sequence,
step_order, min_buffer_sec, max_wip, station_count, daily_capacity_unit,
defect_count, output_count — 모두 int, 음수 금지(priority·severity 등 순번형은 ≥ 1).

### 3-3. 처리 규칙

1. pydantic 스키마는 `float` + 범위 제약(ge/le)만 걸고 소수점 자릿수 제약은 걸지 않는다
2. 내부 계산은 pandas float64 그대로 — 중간 반올림 금지 (누적 합산 오차 방지,
   round는 최종 표시 직전 1회만)
3. float 동등 비교(`==`) 금지 — 임계치 판정은 부등호만 사용
4. 비율(0~1)과 퍼센트(0~100)를 혼용하지 않는다 — 필드별 범위는 3-1 표가 기준이며,
   단위 변환은 표시 계층에서만 한다 (delay_probability를 %로 저장 금지)
5. Decimal 타입은 사용하지 않는다 — 금액·계측 필드가 없는 현재 데이터에서
   float64(유효자릿수 15~16자리)로 손실 가능성이 없기 때문. 계측 필드 도입 시 재검토

## 4. 검증 규칙

- 서버는 SSE 발행 전 pydantic으로 이벤트를 검증한다 (schemas.py, 단계 2)
- enum성 컬럼 값은 관측값 기준으로 loader에서 검증하되, 전체 값 집합은
  `data/README_dataset.txt`를 기준으로 한다 (예: `risk_level`, `applied_yn`,
  `qualified_yn`, `machine_status`). 스펙 문서에 값 목록을 중복 기재하지 않는다
- 이 문서와 구현이 어긋나면 **문서를 먼저 고치고 커밋에 명시**한다 (PoC 정직성)

## 5. 추천 판단 경계

재조정 추천의 선정은 LLM이 아니라 deterministic tool이 결정한다.

| 영역 | 담당 |
|---|---|
| 위험 계획 필터링 | `score_delay_risk` |
| 설비 후보 필터링/정렬 | `find_machine_candidates` |
| 재조정 액션 생성 | `build_reschedule_actions` |
| 재추천 조건 반영 | deterministic tool logic |
| 리스크/설비/순위 숫자 생성 또는 변경 | LLM 금지 |
| 사용자 질문 라우팅 | LLM 허용 |
| 추천 이유 설명, 알림 문구, 리포트 문장화 | LLM 허용 |

LLM은 `risk_score`, `priority`, `current_load`, `setup_time_min`, `preferred_rank`,
`candidate_rank` 같은 판단 근거 수치를 만들거나 수정할 수 없다.
LLM 응답은 tool 결과를 해석하고 사람이 이해할 수 있는 문장으로 설명하는 데만 사용한다.

### 5-1. LLM provider 보안/운영 규칙

- API key는 `.env`에서만 읽고, HTTP 요청 body/query/header로 받지 않는다.
- SSE 이벤트와 report에는 provider 이름과 model 이름만 노출하고 key/base_url은 노출하지 않는다.
- UI는 `auto`, `qwen`, `openai` 선택지만 제공한다. 직접 key 입력 UI는 만들지 않는다.
- OpenAI fallback은 설명/라우팅/리포트 LLM 호출에만 적용된다. deterministic tool 판단은 provider와 무관하다.
```

## 부록 A. API 노출 테이블 필드 사전 (CSV 헤더 원본 — 유일한 근거)

| 테이블 | 컬럼 (순서 포함, 원본 그대로) |
|---|---|
| schedule_master | schedule_id, product, priority, due_date, quantity, process_step, assigned_machine, estimated_duration_hr, status |
| work_status | status_id, schedule_id, machine_id, machine_status, current_load, operator, shift, start_time, utilization_rate, defect_count, output_count |
| delay_risk | risk_id, schedule_id, machine_id, risk_score, risk_level, risk_factor, delay_probability, estimated_delay_hr, impact_scope, detection_time |
| machine_process_map | process_step, process_name, machine_id, recipe_id, qualified_yn, preferred_rank, setup_time_min, avg_process_hr, machine_status, current_load, available_yn |
| reschedule_action | action_id, schedule_id, risk_id, original_machine, alternative_machine, new_sequence, original_sequence, action_type, impact, efficiency_gain, applied_yn, action_time |
