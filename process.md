# process.md — 작업 기록
```
작성자 : 신유진
작성 목적 : 단계별 산출물·설계 결정·필요 지식을 누적 기록한다.
           단계가 끝날 때마다 3절(산출물 / 핵심 설계 결정 / 필요 지식) 구성으로 추가한다.
           항상 EOF에 작성한다.
```

---

## 단계 9 - README 갱신 + 결과물 커밋

작업일: 2026-07-14 / 상태: 완료

### 산출물

`tests/test_stage9_artifacts.py`를 먼저 추가해 단계 9 완료 조건을 고정했다. 테스트는 README가
대시보드 리포트 drawer 스크린샷과 리포트 예시 2건을 링크하는지, `reports/` 아래 증거 파일이 존재하는지,
리포트 예시가 `docs/api-spec.md`의 원본 컬럼명(`schedule_id`, `risk_score`, `risk_level`,
`original_machine`, `alternative_machine`, `efficiency_gain`)을 유지하는지 검증한다.

단계 9 증빙 파일을 추가했다.

- `reports/stage9_report_report_mode.md`: `python -m src.main --mode report --asof "2026-04-15 14:00"` 실행 결과
- `reports/stage9_report_ask_dispatching.md`: HIGH/CRITICAL risk와 reschedule_action 추천이 잡히는 질의형 리포트 예시
- `reports/dashboard-stage9-report-drawer.png`: FastAPI가 서빙한 실제 대시보드에서 `/run` 실행 완료 후,
  경고/승인 모달 없이 오른쪽 최종 리포트 drawer가 열린 상태를 캡처한 README 대표 스크린샷

`README.md`는 최종 리포트 drawer 스크린샷을 상단에 삽입하고, "현재 구현 상태" 표를 단계 9 완료 상태로 동기화했으며,
단계 9 결과물 링크를 별도 섹션으로 정리했다. `docs/roadmap.md`도 단계 9 상태를 완료로 갱신했다.

### 택한 설계 결정

- API 스펙은 변경하지 않았다. 새 엔드포인트나 새 SSE 이벤트를 만들지 않고, 기존 CLI/Supervisor 출력과
  기존 대시보드 계약을 증거 파일로 수집했다.
- 리포트 예시는 사람이 검토할 수 있도록 markdown 그대로 저장했다. 표의 컬럼명은 API 스펙의 원본 CSV
  컬럼명을 유지하고, 별도 별칭 컬럼을 추가하지 않았다.
- 스크린샷은 FastAPI `GET /`로 서빙한 빌드 대시보드를 Playwright로 열고, 실행 버튼을 눌러
  `RUN · 완료`, 이벤트 스트림, 재조정 제안, 오른쪽 리포트 drawer가 표시된 상태를 확인한 뒤 저장했다.
  승인/경고 모달이 중앙에 뜬 캡처는 README 대표 이미지에서 제외했다.
  단계 10 센서 스트림 범위는 시작하지 않았다.

### 필요 지침 정리

- 다음 차수는 단계 10 MQTT 센서 스트림이다. 단계 9 산출물은 `reports/`와 `docs/`의 증거 파일로 고정됐으므로,
  이후 기능 변경 시 README 링크가 깨지지 않는지 `tests/test_stage9_artifacts.py`를 함께 확인해야 한다.
- API 스펙 변경이 필요한 경우에는 `docs/api-spec.md`를 먼저 갱신하고, 해당 변경을 테스트에 반영한다.

---

## 단계 0.5 — 구현 골격 생성 (스캐폴딩)

작업일: 2026-07-06 / 상태: ✅

### 산출물

`docs/architecture.md`의 목표 디렉터리 구조에 맞춰 스켈레톤을 생성했다.
모든 Python 파일은 `docs/conventions.md`의 파일 머리말 형식을 따르며,
아직 구현되지 않은 로직은 `NotImplementedError` + `TODO(단계 N)` 주석으로 명시했다
(PoC 정직성 원칙 — 구현 안 된 기능을 완료형으로 두지 않는다).

- `src/`
  - `__init__.py`, `main.py`, `supervisor.py`, `router.py`, `llm.py`,
    `events.py`, `server.py`, `schemas.py`
  - `agents/` — `base.py`, `field_status.py`, `risk_alert.py`,
    `delay_pred.py`, `dispatching.py`, `report.py`
  - `tools/` — `loader.py`, `risk.py`, `dispatching.py`, `formatting.py`
- `tests/` — `__init__.py`, `test_tools.py` (자리표시 skip 테스트)
- `reports/` — `.gitkeep` (단계 9 산출물 보관 위치 예약)
- `process.md` — 본 기록 파일 신규 생성

### 핵심 설계 결정

- **스텁은 정직하게.** 미구현 함수는 빈 통과(pass)가 아니라 `NotImplementedError`로
  두어, 실수로 미완성 코드가 "동작하는 것처럼" 보이지 않게 했다.
  각 스텁에 담당 구현 단계(TODO(단계 N))를 표기해 roadmap과 코드를 연결했다.
- **`loader.py`의 `DATA_DIR`는 환경변수 우선.** 경로 하드코딩 금지 규칙을 스캐폴딩
  단계부터 반영했다. 기본값은 레포 `data/`, `DATA_DIR` env로 오버라이드 가능.
  이는 단계 12(CSV→SQLite 전환을 loader 내부 수정만으로) 설계의 사전 포석이다.
- **패키지 경계를 3층으로 고정.** `agents/`(판단·서술), `tools/`(계산),
  최상위(조율·IO). architecture.md의 역할 분리 3층을 디렉터리로 물리화했다.
- **web/ 는 이번 단계에서 생성하지 않음.** roadmap 단계 0.5의 범위는
  `src/`, `tests/`, `reports/`, `process.md`이며 `web/dashboard.html`은 단계 8 소관.
- **notebooks/ 는 손대지 않음.** 절대 규칙 4 준수 (프로토타입 보존).

### 필요 지식 정리

- 다음 착수 단계는 **단계 1 (tool 구현)**: canonical CSV 5종
  (`schedule_master`, `work_status`, `delay_risk`, `reschedule_action`,
  `machine_process_map`)을 `loader.py`로 로딩하고, 리스크/dispatching 로직을
  `tools/`에 이관한다. 완료 기준은 `pytest tests/test_tools.py` 통과(LLM 없이).
- `find_machine_candidates`는 반드시 `process_step` + `qualified_yn='Y'`로 후보를
  제한해야 한다(architecture.md 설계 근거 및 roadmap 단계 1 주의사항).
- 이관 원본은 `notebooks/`의 `summarize_field_status`, `detect_delayed_start`,
  `detect_pause`, 리포트 표 변환(df_to_markdown) 로직. 필요한 부분만 함수 단위로 옮긴다.
- 스캐폴딩 검증: `python -c "import src.main"` 등 import가 깨지지 않는지만 확인하며,
  실행 시 `NotImplementedError`가 나는 것은 의도된 동작이다.
- `python -c "import src.main"` import smoke check is the next bootstrap check from stage 0.5.

## 단계 1 - canonical CSV 로딩 및 tools 구현

작업일: 2026-07-06 / 상태: 완료

### 산출물

canonical CSV 5종(`schedule_master`, `work_status`, `delay_risk`, `reschedule_action`,
`machine_process_map`)을 `src/tools/loader.py`에서만 읽도록 구현했다. `DATA_DIR` 환경변수로
데이터 루트를 바꿀 수 있으며, 기본값은 저장소의 `data/` 디렉터리다.

`src/tools/risk.py`에는 LLM 없이 schedule/work status/baseline risk를 조합해
`computed_risk_score`, `computed_risk_level`을 계산하는 `score_delay_risk`를 구현했다.
`src/tools/dispatching.py`에는 `process_step`과 `qualified_yn='Y'` 기준으로 후보를 제한하는
`find_machine_candidates`와 HIGH/CRITICAL 리스크에 대한 `build_reschedule_actions`를 구현했다.
`src/tools/formatting.py`에는 추가 라이브러리 없이 DataFrame을 markdown 표로 바꾸는
`df_to_markdown`을 구현했다.

`tests/test_tools.py`는 skip placeholder를 실제 회귀 테스트로 교체했다. 로더 row count,
설비 후보 필터링, `SCH-0003` CRITICAL 리스크 계산, 대체 설비 추천, markdown 변환을 검증한다.

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest tests/test_tools.py
```

결과: 5 passed.

### 핵심 설계 결정

- 데이터 접근은 `loader.py`로만 통과시켰다. 이후 CSV에서 SQLite로 바뀌어도 loader 내부만 바꾸는
  구조를 유지한다.
- `find_machine_candidates`는 roadmap 단계 1 조건대로 `process_step`과 `qualified_yn='Y'`를
  반드시 적용한다. 추천 우선순위는 가용 여부, 낮은 현재 부하, 선호 순위, 짧은 setup time 순으로 계산한다.
- markdown 변환은 `pandas.to_markdown()`을 쓰지 않았다. 현재 venv에 `tabulate`가 없고,
  단계 1에서 새 라이브러리를 추가하지 않기 위해 작은 표 생성 로직으로 대체했다.
- notebooks는 수정하지 않았다. 필요한 동작만 `src/tools/`의 함수 단위로 이식했다.

### 필요 지시 정리

- 다음 단계는 roadmap 단계 2(`schemas.py` + `llm.py`)다.
- 단계 2에서는 Qwen OpenAI 호환 호출, JSON 검증, pydantic schema를 다루되 API key/model/base_url은
  환경변수로만 읽어야 한다.
- 단계 1 완료 기준은 `tests/test_tools.py` 통과로 충족했다.

---

## 단계 1 보정 - 리스크/재조정 기준 정렬

작업일: 2026-07-06 / 상태: 완료

### 산출물

`docs/risk-scoring.md`를 추가해 엑셀 시나리오의 5단계 흐름을 단계 1 tools 기준으로 문서화했다.
기준은 새 risk score를 발명하지 않고 `delay_risk.csv`의 `risk_score`, `risk_level`,
`delay_probability`, `estimated_delay_hr`를 신뢰하는 방식이다.

`score_delay_risk`는 이제 점수 재계산 함수가 아니라 다음 기준의 위험 계획 조회 함수로 동작한다.

- `schedule_master.status='지연'` 또는 `due_date <= asof 날짜 + 3일`
- `delay_risk.risk_level in ('CRITICAL', 'HIGH')`
- 정렬: `priority ASC`, `risk_score DESC`, `due_date ASC`, `schedule_id ASC`

`find_machine_candidates`와 `build_reschedule_actions`는 대체 설비 후보를 다음 기준으로 제한한다.

- 같은 `process_step`
- `qualified_yn='Y'`
- `machine_status='가동'`
- `available_yn='Y'`
- `current_load < 0.5`

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest tests/test_tools.py
```

결과: 5 passed.

### 핵심 설계 결정

- 리스크 점수 산식은 새로 만들지 않았다. 현업자가 이해하기 쉬운 조회/필터/정렬 흐름이 PoC 설명에 더 적합하므로,
  `delay_risk`의 기존 점수와 등급을 기준값으로 삼았다.
- 등급 기준은 데이터 생성 기준과 맞춰 `CRITICAL >= 85`, `HIGH >= 65`, `MEDIUM >= 35`, 그 외 `LOW`로 문서화했다.
- 대체 설비는 단순히 qualified인 설비가 아니라 현재 가동 가능하고 부하가 0.5 미만인 설비만 추천한다.

### 필요 지시 정리

- 다음 단계 2 이후 Worker/Report는 `docs/risk-scoring.md`의 기준을 근거 문서로 참조해야 한다.
- API 응답에서 원본 CSV 컬럼명을 유지해야 하는 경우 `risk_score`, `risk_level`을 우선 사용하고,
  임의의 `computed_risk_score`/`computed_risk_level` 필드를 새로 노출하지 않는다.

---

## 단계 1 종료 - roadmap 상태 동기화

작업일: 2026-07-06 / 상태: 완료

### 산출물

`docs/roadmap.md`의 단계 1 상태를 ✅로 변경했다. 현재 확인된 상태 문구도 단계 0.5/1 완료 상태에 맞게 갱신했다.

### 핵심 설계 결정

- 단계 1의 완료 기준은 `.\venv\Scripts\python.exe -m pytest tests/test_tools.py` 5 passed로 충족했다.
- 이후 보정된 risk/dispatching/action workflow/LLM provider 계약은 단계 2 이후 구현 기준 문서로 유지한다.

### 필요 지시 정리

- 다음 착수 단계는 단계 2: `schemas.py` + `llm.py` 구현이다.
- 단계 2에서는 `LLM_PROVIDER=auto|qwen|openai`, Qwen 우선/OpenAI fallback, JSON 검증 래퍼를 반영해야 한다.

---

## 단계 1 보정 - LLM provider 선택 계약 정리

작업일: 2026-07-06 / 상태: 완료

### 산출물

`docs/api-spec.md`, `docs/conventions.md`, `.env.example`, `src/llm.py` TODO를 Qwen/OpenAI 선택 구조로 정리했다.

- `LLM_PROVIDER=auto|qwen|openai`
- `POST /run.llm_provider`로 실행 단위 provider 선택 가능
- `auto`는 Qwen 우선, 실패 시 OpenAI fallback
- API key는 `.env`에서만 읽고 요청 payload, 로그, SSE 이벤트에 노출하지 않음
- SSE `llm_provider_selected` 이벤트 추가

### 핵심 설계 결정

- 기본값은 `auto`로 둔다. 로컬 Qwen/Ollama가 동작하면 비용 없이 사용하고, 실패 시 OpenAI API로 전환할 수 있다.
- UI는 provider 선택지만 제공하고 API key 입력 화면은 만들지 않는다.
- provider 선택은 LLM 설명/라우팅/리포트 호출에만 영향을 준다. risk/dispatching/action 추천 판단은 deterministic tool 기준을 유지한다.

### 필요 지시 정리

- 단계 2 `src/llm.py` 구현 시 `LLM_PROVIDER`와 `POST /run.llm_provider` 우선순위를 명확히 적용해야 한다.
- OpenAI fallback이 발생하면 `llm_provider_selected` 이벤트로 `fallback_used=true`를 알려야 한다.

---

## 단계 1 보정 - action workflow API 계약 정리

작업일: 2026-07-06 / 상태: 완료

### 산출물

`docs/api-spec.md`에 재조정 액션 workflow 계약을 추가했다.

- 액션 상태 enum: `PENDING`, `ACCEPTED`, `REJECTED`, `REPROPOSED`, `ESCALATED`, `EXPIRED`
- 승인 API: `POST /api/actions/{action_id}/accept`
- 거절 API: `POST /api/actions/{action_id}/reject`
- 재추천 API: `POST /api/actions/{action_id}/repropose`
- 수동 확인 API: `POST /api/actions/{action_id}/escalate`
- SSE 이벤트: `action_proposed`, `approval_required`, `action_accepted`, `action_rejected`,
  `action_reproposed`, `action_escalated`

추천 판단 경계도 명시했다. 설비 후보 필터링, 정렬, 액션 생성, 재추천 조건 반영은 deterministic tool이 담당하고,
LLM은 routing, 설명, 알림 문구, 리포트 문장화에만 사용한다.

### 핵심 설계 결정

- PoC 사용자는 supervisor 단일 사용자로 본다. 별도 권한/역할 모델은 두지 않는다.
- workflow 요청에는 `supervisor_id`만 사용하고 `actor_role`/권한 필드는 사용하지 않는다.
- 데이터 조회 API는 CSV 원본 컬럼만 반환하되, 승인/거절/재추천 payload와 SSE 이벤트에는 문서에 정의된 workflow 필드를 허용한다.

### 필요 지시 정리

- 단계 7 API 구현 시 `applied_yn='N'`을 거절이 아닌 pending proposal로 해석해야 한다.
- 단계 8 대시보드는 supervisor가 거절 사유, 가중치, 제약조건을 빠르게 조절해 재추천 받을 수 있어야 한다.

---

## 단계 1 보정 - 등급별 알림/승인 정책 정의

작업일: 2026-07-06 / 상태: 완료

### 산출물

`docs/risk-scoring.md`에 risk_level별 운영 액션 정책을 추가했다.

- CRITICAL: 즉시 알림 + 재조정 액션 생성 + 작업자 승인/거절 필수
- HIGH: 알림 + 재조정 액션 생성 + 작업자 승인/거절 권장
- MEDIUM: 대시보드/리포트 표시, 승인 플로우 없음
- LOW: 기록 유지, 별도 처리 없음

Human-in-the-loop 처리 기준도 함께 정했다. CRITICAL 거절 시 다음 후보 재제안 또는 관리자 에스컬레이션,
HIGH 거절 시 모니터링 유지 후 CRITICAL 상승/납기 초과 시 에스컬레이션한다.

### 핵심 설계 결정

- 단계 1 tools는 CRITICAL/HIGH에 대해서만 `build_reschedule_actions`를 생성한다.
- `applied_yn='N'`은 "거절"이 아니라 "아직 승인되지 않은 제안"으로 해석한다.
- 실제 승인/거절 UI와 `applied_yn` 업데이트는 이후 API/대시보드 단계에서 구현한다.

### 필요 지시 정리

- 단계 4 Worker는 CRITICAL/HIGH 알림만 액션 대상으로 취급해야 한다.
- 단계 7~8 API/대시보드는 CRITICAL 액션에는 승인/거절 응답을 필수로 받고, HIGH는 권장 응답으로 표시해야 한다.

---

## 단계 2 - schemas.py + llm.py 구현

작업일: 2026-07-06 / 상태: 완료

### 산출물

`src/schemas.py`에 에이전트 간 공통 계약을 pydantic v2 모델로 구현했다.

- `RoutingDecision`: `target_agents`, `execution_order`, `reason` 검증
- `AgentResult`: `agent`, `summary`, `evidence_tables`, `alerts`, `tool_calls_used` 검증
- `Report`: 최종 report markdown과 Worker 결과 섹션 검증
- 허용 agent 이름과 실행 순서는 Literal 타입으로 제한하고, 라우팅 대상 중복은 validator로 차단한다.

`src/llm.py`에는 Qwen/OpenAI 호환 LLM 호출 래퍼를 구현했다.

- `LLM_PROVIDER=auto|qwen|openai` 선택
- `auto`는 Qwen을 먼저 시도하고 실패 시 OpenAI fallback
- 모델명, base_url, API key는 환경변수에서만 읽음
- `response_format={"type": "json_object"}`, `temperature=0` 고정
- LLM 응답을 pydantic schema로 검증하고, 검증 실패 시 1회 복구 요청
- provider 선택 메타데이터가 필요한 단계 6~7을 위해 `complete_json_result`를 별도로 제공

`tests/test_schemas_llm.py`를 추가해 네트워크 호출 없이 fake OpenAI client로 검증했다. 기존 단계 1 테스트와 함께 실행했다.

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest tests/test_tools.py tests/test_schemas_llm.py
```

결과: 10 passed.

### 핵심 설계 결정

- Qwen strict `json_schema` 지원 여부가 모델/엔드포인트마다 다를 수 있으므로, roadmap 지시대로 `json_object` + pydantic 검증 + 1회 복구 요청 패턴을 기본으로 했다.
- `complete_json`은 기존 호출부가 쓰기 쉽게 검증된 pydantic 모델만 반환하고, SSE `llm_provider_selected` 이벤트에 필요한 provider/model/fallback 정보는 `complete_json_result`에서 받도록 분리했다.
- API key, base_url은 예외 메시지와 테스트 assertion에 노출하지 않고 환경변수 이름만 다룬다.
- `AgentResult.agent`에는 `report`까지 허용하되, `RoutingDecision.target_agents`에는 Worker 4종만 허용한다. `report`는 Supervisor report 모드에서 조립되는 특수 Worker이므로 라우팅 대상에서 제외한다.

### 필요 지시 정리

- 단계 3 `router.py`는 `complete_json(..., RoutingDecision)`을 사용하고, 검증/호출 실패 시 `field_status` 폴백 reason을 명시해야 한다.
- 단계 4 Worker는 반드시 `AgentResult`를 반환하고, evidence table은 tool 산출 markdown을 그대로 넣어야 한다.
- 단계 6~7 EventBus/SSE 구현 시 `complete_json_result`의 `requested_provider`, `active_provider`, `fallback_used`, `model_name`만 이벤트에 노출하고 key/base_url은 노출하지 않아야 한다.

---

## 단계 3 - Routing Agent 구현

작업일: 2026-07-06 / 상태: 완료

### 산출물
`src/router.py`에 Routing Agent를 구현했다. 라우터는 사용자 질의를 `complete_json(..., RoutingDecision)`으로 전달해 Worker 목록을 결정하고, system prompt에서 `temperature=0`으로 고정된 `src/llm.py` 래퍼를 사용한다.

- Worker catalog와 routing rule을 파일 상단 상수로 유지했다.
- `field_status`, `risk_alert`, `delay_pred`, `dispatching` 4개 Worker만 라우팅 대상으로 허용한다.
- 리포트 요청은 `field_status -> risk_alert -> delay_pred -> dispatching` 순서로 라우팅한다.
- 복수 의도는 `RoutingDecision.target_agents`에 여러 Worker를 순서대로 담는다.
- 빈 요청 또는 LLM/검증 실패는 `field_status` fallback으로 처리하고 reason에 fallback임을 명시한다.

`tests/test_router.py`를 추가해 `docs/agents.md` 라우팅 표 기준 6개 케이스를 검증했다. 필수 실패 케이스인 빈 문자열과 LLM 빈 응답 실패 fallback도 함께 검증했다.

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest tests/test_tools.py tests/test_schemas_llm.py tests/test_router.py
```

결과: 13 passed.

### 핵심 설계 결정

- 라우터는 deterministic tool 계산을 수행하지 않고, Worker 선택만 담당한다. 숫자 계산과 근거 표 생성은 이후 Worker와 tools 계층에 남긴다.
- LLM 호출은 `src/llm.py`의 `complete_json`만 사용해 provider, JSON 검증, temperature 0 정책을 한 곳에서 유지한다.
- fallback은 예외를 전파하지 않고 `field_status`로 돌려보낸다. 단계 4 이후 Worker/Supervisor 조립 시 라우팅 실패가 전체 실행을 중단하지 않도록 하기 위한 결정이다.
- `report`는 Worker schema에는 존재하지만 `RoutingDecision.target_agents`에는 포함하지 않는다. report 조립은 단계 5 Supervisor/report Worker 책임으로 남긴다.

### 필요 지시 정리

- 다음 단계는 단계 4 Worker 4종(`field_status`, `risk_alert`, `delay_pred`, `dispatching`) 구현이다.
- 각 Worker는 반드시 `AgentResult`를 반환하고, evidence table은 tool 결과 markdown을 그대로 사용해야 한다.
- 단계 4 테스트는 LLM 없이 tools와 schema 계약 중심으로 작성하고, summary/alerts 문구 생성만 LLM 대상이 되도록 분리해야 한다.

---

## 단계 4 - Worker 4종 구현

작업일: 2026-07-06 / 상태: 완료

### 산출물

`src/agents/base.py`에 Worker 공통 인터페이스와 LLM 서술 helper를 구현했다.

- 모든 Worker는 `run(asof, query=None) -> AgentResult` 계약을 따른다.
- `_narrate()`는 `src.llm.complete_json(..., WorkerNarrative)`를 호출해 `summary`, `alerts`만 생성한다.
- LLM 호출 실패 시 tool 결과로 만든 결정적 fallback summary/alerts를 반환해 기본 실행과 테스트가 중단되지 않게 했다.
- system prompt에서 tool_context 밖 숫자·schedule_id·machine_id 창작 금지와 evidence table 재작성 금지를 명시했다.

Worker 4종을 구현했다.

- `src/agents/field_status.py`: `load_schedule`, `load_work_status` 결합으로 현장 상태 표와 지연/정지/고부하 요약 생성
- `src/agents/risk_alert.py`: `score_delay_risk` 기반 HIGH/CRITICAL 위험 표와 알림 생성
- `src/agents/delay_pred.py`: 예상 지연 시간·지연 확률 기준 표와 알림 생성
- `src/agents/dispatching.py`: `build_reschedule_actions`, `find_machine_candidates` 기반 재조정 액션·대체 설비 후보 표 생성

`src/schemas.py`에 Worker LLM 서술 응답용 `WorkerNarrative` 스키마를 추가했다.
`src/agents/__init__.py`에서 Worker 클래스 4종을 export했다.
`tests/test_workers.py`를 추가해 Worker 단독 실행, AgentResult 계약, LLM 서술 호출, LLM 실패 fallback을 검증했다.

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest tests/test_tools.py tests/test_schemas_llm.py tests/test_router.py tests/test_workers.py
```

결과: 18 passed.

### 핵심 설계 결정

- 수치 계산과 표 생성은 기존 `src/tools/` 함수만 사용한다. LLM에는 tool_context로 계산 결과와 알림 후보만 전달하고, LLM은 문장 생성만 담당한다.
- Worker별 LLM 호출은 공통 `_narrate()` helper로 통일해 Qwen/OpenAI provider, JSON 검증, temperature 0 정책을 `src/llm.py`에 계속 집중시켰다.
- prompt는 Worker별 system prompt와 공통 guardrail로 나눴다. 각 Worker의 역할 경계는 개별 system prompt가 잡고, 수치 창작 금지·표 재작성 금지는 공통 guardrail이 강제한다.
- LLM 실패가 Worker 실패로 번지지 않도록 fallback을 둔다. 이후 Supervisor 단계에서 partial failure 정책을 구현하더라도, LLM 일시 실패는 최소한의 deterministic 결과로 응답할 수 있다.
- `field_status` 근거 표는 단순 우선순위 정렬이 아니라 지연, 설비 정지, 고부하 항목이 먼저 보이도록 정렬했다. 현장 상태 Worker의 목적이 이상 상태 노출이기 때문이다.

### 필요 지시 정리

- 단계 5 Supervisor는 `FieldStatusWorker`, `RiskAlertWorker`, `DelayPredWorker`, `DispatchingWorker`를 순차 실행하고, report Worker는 이 `AgentResult`들을 입력으로 조립해야 한다.
- 단계 5에서 Worker 실패를 partial failure로 처리하되, 현재 Worker 내부 LLM 실패는 이미 fallback 처리되므로 tool/data 예외 중심으로 다루면 된다.
- report Worker는 중복 계산을 피하기 위해 감지 tool을 직접 호출하지 않고 Worker 결과의 `evidence_tables`, `summary`, `alerts`만 사용해야 한다.

---

## 단계 5 - report Worker + Supervisor 조립

작업일: 2026-07-06 / 상태: 완료

### 산출물

`src/agents/report.py`에 `ReportWorker`를 구현했다.

- 입력으로 받은 `AgentResult` 목록만 사용해 최종 `Report`를 생성한다.
- 직접 감지 tool을 호출하지 않아 Worker 계산을 중복하지 않는다.
- 각 Worker의 `summary`, `alerts`, `evidence_tables`를 markdown 섹션으로 조립한다.
- 근거 표 컬럼명은 Worker/tool 결과 markdown을 그대로 사용해 `docs/api-spec.md`의 원본 컬럼명 유지 원칙을 지켰다.

`src/supervisor.py`에 Supervisor 조율 로직을 구현했다.

- report 모드 실행 순서: `field_status -> risk_alert -> delay_pred -> dispatching -> report`
- ask 모드는 Routing Agent 결과의 `target_agents`를 순차 실행한 뒤 report Worker로 조립한다.
- Worker 실행 실패 시 전체 중단 대신 해당 Worker 섹션을 `수집 실패`로 대체하고 계속 진행한다.

`src/main.py`에 단계 5 완료 기준 검증을 위한 최소 CLI 연결을 추가했다.

- `--mode report|ask`, `--asof`, `--q/--query`, `--llm-provider`를 파싱한다.
- `Supervisor().run(...)` 결과의 `report_markdown`을 출력한다.
- EventBus 콘솔 로거는 단계 6 범위로 남겼다.

`tests/test_supervisor_report.py`를 추가했다.

- report Worker markdown 조립
- report 모드 Worker 실행 순서
- ask 모드 router target 사용
- partial failure 계속 진행
- ask mode query 필수 검증
- CLI report markdown 출력

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest
$env:LLM_PROVIDER='disabled'; .\venv\Scripts\python.exe -m src.main --mode report --asof "2026-04-15 14:00"
```

결과:

- pytest: 24 passed
- CLI: 근거 표 포함 markdown 리포트 출력 확인

### 핵심 설계 결정

- `ReportWorker`는 특수 Worker로 `AgentResult` 목록을 받아 `Report`를 반환한다. 감지 tool을 직접 호출하지 않아 `docs/agents.md`의 중복 계산 방지 원칙을 따른다.
- Supervisor는 직접 오케스트레이션한다. 별도 agent framework를 쓰지 않고 Worker 인스턴스를 순서대로 호출해 `docs/architecture.md`의 직접 구현 원칙을 유지했다.
- partial failure는 `AgentResult(agent=..., summary="수집 실패: ...")`로 표현한다. 이렇게 하면 최종 report schema를 깨지 않고 실패 섹션과 성공 섹션을 함께 출력할 수 있다.
- 단계 6의 EventBus/SSE 이벤트 스키마는 아직 구현하지 않았다. `docs/api-spec.md`는 수정하지 않았고, 단계 5에서는 그 계약과 충돌하는 API/이벤트 필드를 추가하지 않았다.

### 필요 지시 정리

- 단계 6에서는 현재 `main.py`의 최소 CLI 위에 EventBus publish/subscribe와 콘솔 로거를 붙이면 된다.
- 단계 6 이후 EventBus 이벤트를 추가할 때는 `docs/api-spec.md` 2장의 이벤트 타입과 순서 보장을 그대로 따라야 한다.
- 단계 7 API 구현 전까지 `/run`, `/events`, `/api/*` 계약은 코드에 추가하지 않는다.

---

## 단계 6 - CLI + EventBus 콘솔 로거

작업일: 2026-07-06 / 상태: 완료

### 산출물

`src/events.py`에 EventBus를 구현했다.

- `EventRecord`는 `event`, `seq`, `ts`, `data`를 보관하며 `data`에도 `seq`, `ts`를 포함한다.
- `EventBus.publish()`는 실행 단위 seq를 1부터 증가시키고 현재/직전 run 버퍼에 이벤트를 저장한다.
- `EventBus.subscribe()`는 콘솔 로거와 향후 SSE가 같은 이벤트 스트림을 구독할 수 있게 한다.
- `replay_after_seq`로 Last-Event-ID 이후 이벤트 재전송에 필요한 기반을 마련했다.
- `ConsoleEventLogger`는 CLI에서 `run_start`, `routing_decision`, `agent_start`, `agent_end`, `error`, `run_end`를 간단한 콘솔 로그로 출력한다.

`src/supervisor.py`에 선택적 EventBus 주입을 연결했다.

- 기존 `Supervisor()` 호출은 그대로 동작하고, `Supervisor(event_bus=...)`인 경우에만 이벤트를 발행한다.
- report 모드 실행 순서는 `field_status -> risk_alert -> delay_pred -> dispatching -> report`로 유지했다.
- 이벤트 순서는 `run_start -> routing_decision -> agent_start/agent_end 또는 error -> run_end`가 되도록 했다.
- Worker 실패는 기존 단계 5 정책대로 recoverable error 이벤트를 남기고 수집 실패 섹션으로 대체한다.
- report Worker 실패나 잘못된 mode/query는 non-recoverable error와 `run_end(status="failed")`를 남기고 예외를 유지한다.

`src/main.py`에서 CLI 실행 시 EventBus를 만들고 `ConsoleEventLogger`를 구독시켰다.

- `python -m src.main --mode report --asof "2026-04-15 14:00"` 실행 시 이벤트 로그가 먼저 출력되고 최종 markdown 리포트가 출력된다.

`tests/test_events.py`를 추가했다.

- EventBus publish/buffer/replay 동작을 검증한다.
- Supervisor report 모드 이벤트 순서와 agent_start 대상 목록을 검증한다.

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest
$env:LLM_PROVIDER='disabled'; .\venv\Scripts\python.exe -m src.main --mode report --asof "2026-04-15 14:00"
```

결과:

- pytest: 26 passed
- CLI: `run_start`, `routing_decision`, 5개 agent 구간, `run_end(status=done)` 로그와 markdown 리포트 출력 확인

### 의사결정

- EventBus는 동기 in-memory pub/sub로 구현했다. 단계 7의 SSE 서버가 같은 객체를 구독할 수 있어야 하므로 외부 큐나 프레임워크 의존성을 추가하지 않았다.
- API 이벤트 타입과 payload 명칭은 `docs/api-spec.md`의 정의를 따랐고, 새 이벤트 타입을 만들지 않았다.
- CLI 콘솔 로그는 사람이 읽는 진행 로그로만 사용하고, 최종 결과 데이터는 기존 `Report.report_markdown` 출력으로 유지했다.
- `tool_call` 이벤트는 이번 단계에서 억지로 만들지 않았다. 현재 Worker의 `tool_calls_used`에는 내부 loader/LLM helper 이름도 포함되어 있는데, `docs/api-spec.md`는 SSE `tool` 값을 제한하고 있어 잘못된 이벤트를 만들 위험이 있기 때문이다. 단계 7 이후 필요하면 API 스펙에 맞는 tool 호출 계측 지점을 별도로 분리한다.

### 필요 지침

- 단계 7 `/events` 구현 시 `EventBus.events`와 `subscribe(replay_after_seq=...)`를 그대로 사용해 현재/직전 run 버퍼 재생 규칙을 맞춘다.
- `docs/api-spec.md`에 없는 이벤트 타입이나 필드는 추가하지 않는다. 변경이 필요하면 문서를 먼저 합의 후 수정한다.
- API key, base_url 등 LLM 접속 정보는 이벤트나 콘솔 로그에 출력하지 않는다.

---

## 단계 7 - FastAPI server.py + SSE /events + /run

작업일: 2026-07-07 / 상태: 완료

### 산출물

`src/server.py`의 단계 7 스텁을 실제 FastAPI 앱으로 구현했다.

- `GET /health`: `{"status": "ok"}` 상태 확인
- `POST /run`: `mode=report|ask`, `asof`, `query`, `llm_provider` payload 검증 후 Supervisor 백그라운드 실행
- `GET /events`: `EventBus`를 구독해 `text/event-stream` SSE frame 송신
- `GET /`: `frontend/dist/index.html`이 있으면 정적 서빙, 아직 빌드가 없으면 API 상태 안내 HTML 반환
- `GET /api/schedules`, `/api/work-status`, `/api/risks`, `/api/machines`, `/api/actions`: `docs/api-spec.md`의 읽기 전용 데이터 조회 API 구현

`src/supervisor.py`에는 SSE 스펙 이벤트를 보강했다.

- Worker별 허용 tool만 `tool_call` 이벤트로 발행
- dispatching 결과의 reschedule action 표를 기반으로 `action_proposed`, `approval_required` 이벤트 발행
- API key/base_url 같은 LLM 접속 정보는 이벤트 payload에 포함하지 않음

`tests/test_server.py`를 추가해 `/health`, `/run` ask 입력 검증, `/api/schedules` 컬럼 보존, `/api/risks` 정렬을 검증했다.
`docs/roadmap.md`와 `README.md`의 단계 7 상태를 완료로 동기화했다.

검증 명령:

```bash
.\venv\Scripts\python.exe -m pytest
```

결과: 30 passed.

SSE 수신 확인:

```bash
uvicorn src.server:app --host 127.0.0.1 --port 8013
curl.exe -sS --no-buffer --max-time 10 http://127.0.0.1:8013/events
```

별도 트리거로 `POST /run`을 호출했을 때 `run_start`, `routing_decision`, `agent_start`,
`tool_call`, `agent_end`, `action_proposed`, `approval_required`, `run_end` 이벤트가 seq 순서로 수신됐다.
SSE는 연결 유지형 스트림이므로 검증용 curl은 `--max-time` 종료 코드 28로 끝났지만, `run_end(status=done)`까지 수신을 확인했다.

### 핵심 설계 결정

- Supervisor 실행은 `asyncio.to_thread()`로 분리했다. FastAPI event loop를 막지 않으면서 기존 동기 Supervisor/Worker 코드를 유지하기 위한 결정이다.
- 단일 실행 PoC 범위에 맞춰 전역 `RunState`와 `asyncio.Lock`으로 중복 `/run` 요청을 409 처리한다. 실행 이력 저장이나 다중 사용자 큐는 단계 7 스코프에서 제외했다.
- SSE 구독자는 `asyncio.Queue`를 사용하고, Supervisor thread에서 발행되는 EventBus 이벤트는 `loop.call_soon_threadsafe()`로 전달한다.
- 데이터 조회 API는 CSV를 직접 열지 않고 `src/tools/loader.py`의 로더 함수만 사용한다. API 응답 필드는 `docs/api-spec.md` 부록 A의 원본 CSV 컬럼을 그대로 유지한다.
- `docs/api-spec.md`는 수정하지 않았다. 단계 7 구현은 기존 계약 안에서 맞췄다.

### 필요 지시 정리

- 다음 단계는 단계 8: `frontend/` Vue 3 대시보드 구현이다.
- 프론트는 `/run`, `/events`, `/api/*`, `/health`만 사용하고 CORS를 추가하지 않는다. Vite dev proxy로 FastAPI 8000에 연결한다.
- 대시보드 상태 전이는 `docs/api-spec.md` 2-2의 Run/Node 상태 정의를 기준으로 구현해야 한다.

---

## 단계 7 보정 - 리포트 품질 개선

작업일: 2026-07-07 / 상태: 완료

### 산출물

`src/agents/report.py`에 핵심 추천 액션 HTML 스냅샷을 추가해, 리포트 상단에서 `dispatching` 결과가 바로 보이도록 보정했다.
`src/agents/risk_alert.py`는 alert 생성과 system prompt를 정리해 같은 표현을 반복하지 않도록 수정했다.

`tests/test_supervisor_report.py`는 리포트 상단에 `핵심 추천 액션`과 HTML `<details>` 카드가 포함되는지 검증하도록 갱신했다.

### 핵심 설계 결정

- 리포트는 markdown만 고집하지 않고, HTML `<details>`와 표를 섞어 우선순위와 액션을 먼저 보이게 했다.
- `risk_alert`는 최대 3개의 서로 다른 schedule_id만 우선 보여주도록 바꿔서 반복 나열을 줄였다.
- `report`는 섹션을 그대로 나열하는 대신, 상단에 액션 스냅샷을 두고 그 아래에 worker별 상세를 이어붙이도록 구성했다.

### 필요 지식 정리

- 이후 대시보드 단계에서는 이 HTML 블록을 그대로 렌더링해도 되고, 별도 카드 UI로 재구성해도 된다.
- 리포트 품질 보정은 LLM 문장만이 아니라 조립 레이아웃과 fallback alert 정책이 같이 맞아야 효과가 있다.

---

## 단계 8 - Vue 3 대시보드 (다크 관제 콘솔 재설계 + 알림/HITL)

### 산출물

- `frontend/src/styles/` — 다크 관제 콘솔 디자인 토큰 재작성. 표면은 청회색 그래파이트,
  액센트는 플라즈마 시안(#45c4f5), 상태색(good/warning/serious/critical)은 dataviz 검증
  팔레트(#0ca30c/#fab219/#ec835a/#d03b3b) 채택. 상태는 항상 라벨과 함께 표기 (색상 단독 의미 전달 금지)
- `ArchitectureView.vue` — 트리형 목록을 SVG 노드 그래프로 교체.
  Supervisor→Routing→Worker4→report 고정 좌표 배치 + 베지어 엣지,
  실행 중 노드로 향하는 엣지 위로 `animateMotion` 패킷 2개가 흐른다 (그래프 라이브러리 없음)
- 알림 시스템 신규: `useNotifications.ts` + `ToastStack`(우측 하단, 6초 자동 소멸·critical은 수동 닫기)
  + `ApprovalModal`(중앙, 승인/거절(사유 필수)/나중에) + `NotificationCenter`(벨 아이콘·미확인 배지·이력·HITL 버튼)
- `src/server.py` — api-spec 1-4의 `POST /api/actions/{id}/accept`·`/reject` 구현.
  `ActionRegistry`(in-memory)가 `action_proposed` 이벤트를 구독 수집,
  응답 처리 시 SSE `action_accepted`/`action_rejected` 발행. repropose/escalate는 계약만 유지
- 재설계 2차 (관리자 한눈 뷰): `KpiStrip`(진행중 스케줄·CRITICAL/HIGH 리스크·가용 설비·승인 대기 타일)
  + `RiskTable`(/api/risks 상위 6건, 원본 컬럼명·1dp 표시) + `useFactorySnapshot`(읽기 전용 /api 집계,
  초기 로드·run 종료 시 재조회). 최종 리포트는 그리드 패널(`ReportPanel`) 대신
  우측 슬라이드 드로어(`ReportDrawer`)로 교체 — run_end 도착 시 자동 오픈, 헤더 "리포트" 버튼으로 재오픈
- 재설계 3차 (실행 결론 전면화): `action_proposed` 이벤트에 `original_machine`·`impact`·
  `efficiency_gain` 추가 (api-spec 2-1 문서 먼저 갱신 후 supervisor 발행 확장,
  근거 표 파싱 실패 수치는 null — 프론트가 수치를 만들지 않는다).
  `ActionQueue` 패널을 좌하단 메인 자리에 신설 — 행마다 "SCH · 원설비→대체설비" 전환 방향,
  risk 배지, 부하 개선(2dp)·영향, 승인/검토 버튼과 응답 상태 칩. 리스크 표는 우하단으로 이동
- ReportWorker 조립 개선 (수치 계산 변경 없음): ① "## 요약" 절 신설 — Worker 4종의 한 줄
  요약을 관리자용 한글 역할명과 함께 bullet으로 상단 배치, ② HTML `<details>` 액션 카드를
  markdown 표(상위 5건, 원본 컬럼명 유지)로 교체 — 드로어·CLI·README 어디서나 동일 렌더링,
  ③ 섹션 제목 `## field_status` → `## 현장 가동 현황 (field_status)`,
  Alerts/Evidence → 주요 알림/근거 표. 드로어의 넓은 근거 표는 표 단위 가로 스크롤 처리
- 재설계 4차 (추이·흐름·효과 시각화, 차트 라이브러리 없이 수제 SVG):
  ① `RiskTrend` — delay_risk.detection_time 1시간 구간 max risk_score 라인차트,
  임계선 85(데이터의 CRITICAL 경계) 표기, 최신 구간 임계 초과 시 "재조정 실행 권고"
  critical 알림 발송 (`pushAlert`, 구간 키 dedupe — 차트와 알림이 같은 `hourlyRiskSeries` 사용).
  ② `LineFlow` — Etch 스텝 4종 스윔레인에 설비 카드(상태·부하바·0.8 틱)와 CRITICAL/HIGH
  스케줄 칩 배치, `현재 배치/제안 적용 후` 토글로 재조정 후 흐름 정리를 시각화 (승인 건은 항상 이동).
  하단 효과 요약은 tool 산출값 집계만 — 조치 대상 CRITICAL/HIGH·평균 efficiency_gain·
  estimated_delay_hr 합계·정지/점검중 이탈·납기 3일 이내. 적용 후 부하 재계산 같은 예측치는
  데이터에 없으므로 표시하지 않는다 (PoC 정직성).
  ③ KPI 타일 5→3 축소(진행중·CRITICAL·승인 대기), `RiskTable`은 추이·플로우가 대체해 제거
- 재설계 5차: 그리드를 3행으로 재배치 — 파이프라인|라인 플로우(상), 현황 스트립(중, 전폭 슬림
  7.5rem: KPI 스탯 바 22rem + 리스크 추이), 제안 큐|이벤트 스트림(하). KPI는 카드 3장 →
  구분선 있는 단일 스탯 바로 압축. 추이 차트 리디자인 — Catmull-Rom 곡선(제어점 y 클램프)·영역
  그라디언트·임계 초과 구간 음영·크로스헤어+커스텀 툴팁·최근값 배지(헤더). 고정 viewBox의
  letterbox 문제를 ResizeObserver 동적 렌더링으로 해결(컨테이너 픽셀 = viewBox, 글자 크기 고정).
  임계값은 패널 헤더 number input으로 사용자 지정 (`defineModel` + localStorage 유지, 기본 85 =
  CRITICAL 경계), 임계 초과 알림 판정도 같은 값·같은 집계 함수 사용, dedupe 키에 임계값 포함

### 검증

- `npm run build` (vue-tsc 타입체크 포함) 통과, FastAPI 단독 서빙(`GET /` → dist) 확인
- TestClient로 승인/거절/중복 응답 409/미존재 404/사유 검증 422/run 교체 시 EXPIRED 409 전 케이스 통과
- 실제 uvicorn + 스크립트 이벤트 시퀀스로 SSE 재생 → `POST accept` → `action_accepted` SSE 수신까지 e2e 확인

### 핵심 설계 결정

- 알림은 SSE 이벤트의 파생 뷰다. `useEventStream`이 유일한 수신 지점(컨벤션 유지)이고,
  `onEvent` 훅으로 `useNotifications.ingest`에 전달한다. run이 바뀌어도 알림 이력은 세션 내 유지
- 승인 상태의 단일 소스는 서버 `ActionRegistry`. 프론트는 HTTP 200과 SSE 이벤트 양쪽에서
  멱등하게 반영한다 (SSE 끊김 대비)
- 새 `run_start`가 오면 이전 run의 PENDING 제안을 서버·프론트 모두 EXPIRED 처리
  — 기준시각이 바뀐 제안을 승인하는 사고 방지 (api-spec 1-4 EXPIRED 의미 그대로)
- 애니메이션은 SVG SMIL(`animateMotion`+`mpath`)로 구현해 JS 프레임 루프 없이 동작,
  `prefers-reduced-motion`에서 패킷·펄스를 끈다

### 필요 지식 정리

- SMIL `animateMotion`은 `mpath`로 기존 path를 재사용하므로 엣지 좌표를 한 곳에서 관리할 수 있다
- EventBus 구독자는 run reset과 무관하게 유지된다 — 서버 레지스트리를 모듈 로드 시 1회 구독
- FastAPI 동기 엔드포인트는 threadpool에서 실행되므로 Supervisor worker thread와의
  레지스트리 경합은 `threading.Lock`으로 직렬화했다

---

## 단계 10 - Mosquitto MQTT 센서 스트림 + 대시보드 센서 패널

### 산출물

- backend (별도 세션 작업): `src/sensors/simulator.py`(6라인×3센서 publish, 이상 주입 CLI),
  `src/sensors/subscriber.py`(`factory/#` 구독 → sensor_update/sensor_alert 발행),
  `src/sensors/rules.py`(60초 내 3연속 임계 초과 rule), `MQTT_ENABLED` startup 연동,
  `tests/test_sensor_stream.py`
- frontend: `SensorPanel.vue`(라인 카드 + 최근 60초 vanilla canvas 스파크라인 + 경고 토글),
  `useSensorStream` composable(60초 샘플 링버퍼·경고 감쇠), `types/events.ts` 센서 이벤트 타입,
  `useNotifications` sensor_alert 연동(라인·센서당 60초 스로틀), App 4행 그리드 통합
- 증빙: `reports/dashboard-stage10-sensor-panel.png` (Line-2 temp-drift 경고 상태)

### 검증

- Mosquitto 서비스 + `python -m src.sensors.simulator --anomaly temp-drift` +
  `MQTT_ENABLED=true uvicorn`으로 실동작 E2E: SSE에서 sensor_update 초당 18건 수신,
  Line-2 온도 80°C 초과 3연속 시 sensor_alert → 카드 경고색·critical 토스트·타임라인 기록 확인
- Playwright 자동 체크: 라인 카드 6개, 스파크라인 18개, MQTT LIVE 표시, 타임라인에
  sensor_update 0건(비flood), 경고 배지 "임계 초과" — 전부 통과. pytest 35+1(계약 갱신) 통과

### 핵심 설계 결정

- 센서 이벤트도 `useEventStream`이 유일한 수신 지점(컨벤션) — onEvent 훅을 알림과 센서
  상태 저장소 2곳으로 팬아웃했다
- sensor_update(≤18건/초)는 타임라인에 쌓지 않는다 — 이벤트 스트림 패널은 실행·워크플로우
  이벤트용이고, 고빈도 텔레메트리는 센서 패널이 전용 표시 계층이다
- 지속 이상 시 rule 엔진이 ~3초마다 sensor_alert를 재발행하므로 알림센터·토스트는
  라인·센서당 60초 스로틀. 카드 경고색은 매 alert마다 갱신 (알림 피로와 상태 표시를 분리)
- 임계치 판정은 서버 rules.py만 한다 — 프론트는 임계값을 복제하지 않고 sensor_alert
  이벤트만으로 경고색을 칠한다 (절대 규칙 2: 판단은 코드, 표시는 프론트)
- 센서 패널은 첫 sensor_update 수신 시에만 나타난다 — MQTT 없이 돌리는 기존 데모의
  레이아웃을 바꾸지 않는다 (단계 8 화면 회귀 방지)

### 필요 지식 정리

- paho-mqtt 2.x는 CallbackAPIVersion 지정이 필요하다 (1.x 호환 fallback을 subscriber가 처리)
- EventSource 재접속 replay와 고빈도 텔레메트리가 겹치면 재접속 시 수천 건이 한 번에
  들어온다 — 타임라인 제외가 없으면 페이지 복귀가 눈에 띄게 느려진다
- canvas 스파크라인은 devicePixelRatio 보정(물리 픽셀 리사이즈) 없이는 HiDPI에서 흐릿하다
