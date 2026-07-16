# roadmap.md — 단계별 구현 플랜

```
작성자 : 신유진
작성 목적 : 구현 단계·순서·완료 기준 정의. 상태 표가 곧 진행 현황판이다.
```

## 단계별 플랜

| 단계 | 작업 | 완료 기준 | 상태 |
|---|---|---|---|
| 0 | 문서 세트 작성 (CLAUDE.md, docs/) | 문서 4종 커밋 | ✅ |
| 0.5 | 구현 골격 생성 (`src/`, `tests/`, `reports/`, `process.md`) | 디렉터리 구조와 기본 파일 머리말 생성, `process.md` 기록 시작 | ✅ |
| 1 | canonical CSV 로딩·리스크/dispatching 로직을 `src/tools/`로 구현 | 노트북 없이 `pytest tests/test_tools.py` 통과 | ✅ |
| 2 | `schemas.py` + `llm.py` (Qwen OpenAI 호환 호출 + JSON 검증 래퍼) | RoutingDecision·AgentResult 검증 동작 | ✅ |
| 3 | Routing Agent (`router.py`) | 라우팅 표의 6개 케이스 프롬프트 테스트 통과 | ✅ |
| 4 | Worker 4종 (field_status, risk_alert, delay_pred, dispatching) | 각 Worker 단독 실행으로 AgentResult 생성 | ✅ |
| 5 | report Worker + Supervisor 조립 | `--mode report` 실행 시 근거 표 포함 리포트 출력 | ✅ |
| 6 | CLI (`main.py`) + `events.py` EventBus (콘솔 로거 구독) | CLI 실행 시 이벤트 기반 로그 출력 | ✅ |
| 7 | FastAPI `server.py` + SSE `/events` + `/run` | curl로 SSE 이벤트 수신 확인 | ✅ |
| 8 | `frontend/` Vue 3 대시보드 (Vite+TS, 파이프라인 그래프·이벤트 스트림·리포트·알림/HITL) | dev proxy로 실행 과정 재생 + `npm run build` 후 FastAPI 단독 서빙 확인 | ✅ |
| 9 | README 갱신 + 결과물 커밋 | 리포트 예시 2건 + 대시보드 리포트 drawer 스크린샷을 `reports/`에 커밋 | ✅ |
| 10 | MQTT 센서 스트림 — 시뮬레이터 + Mosquitto + 구독자 + 대시보드 센서 패널 | 이상 주입 시나리오가 대시보드에 실시간 표시 | ✅ |
| 11 | 센서 이상 → Supervisor 자동 트리거 (rules.py, 쿨다운 포함) | temp-drift 데모에서 자동 실행이 타임라인에 기록됨 | ✅ |
| 12 | (선택) SQLite 연동 — CSV를 `data/factory.db`로 적재, loader.py 내부만 교체 | 툴·에이전트 코드 수정 0줄로 전환 완료 | ⬜ |

## 구현 방향 정리

현재 `notebooks/`는 기존 프로토타입과 증빙 자료로 보존한다. 노트북 고도화는 노트북 파일을 직접 수정하는 방식이 아니라, 노트북에 있던 감지·요약·리포트 로직을 `src/` 코드로 이관해 재사용 가능한 PoC 애플리케이션으로 만드는 것을 의미한다.

따라서 구현 우선순위는 다음과 같다.

1. `src/tools/`에 LLM 없이 동작하는 계산 로직을 먼저 이식한다.
2. `tests/`로 tool 함수의 재현성을 확보한다.
3. 그 다음 `schemas.py`, `llm.py`, `router.py`, Worker Agent를 올린다.
4. CLI가 먼저 완전히 동작한 뒤 FastAPI/SSE 대시보드를 붙인다.
5. 마지막에 README, `process.md`, `reports/` 산출물을 roadmap 상태와 동기화한다.

## 단계별 주의사항

**단계 0.5 (스캐폴딩)**
- 현재 구현 디렉터리인 `src/`, `tests/`, `reports/`와 작업 기록 파일 `process.md`가 없으므로 먼저 생성한다.
- Python 파일은 `docs/conventions.md`의 파일 머리말 형식을 따른다.
- `process.md`에는 단계별 산출물 / 핵심 설계 결정 / 필요 지식 정리 3절을 기록한다.
- 이 단계에서는 노트북을 수정하지 않는다.

**단계 1 (tool 구현)**
- canonical 데이터는 `schedule_master`, `work_status`, `delay_risk`, `reschedule_action`, `machine_process_map`
- `find_machine_candidates`는 반드시 `process_step`과 `qualified_yn='Y'`를 기준으로 후보를 제한
- 데이터 경로 하드코딩 금지 → `loader.py`에서 `DATA_DIR` 상수 관리
- 기존 노트북의 `summarize_field_status`, `detect_delayed_start`, `detect_pause`, 리포트 표 변환 로직은 필요한 부분만 함수 단위로 이관한다.
- 이 단계의 완료 기준은 LLM, CrewAI, Jupyter 없이 순수 Python/pytest로 검증되는 것이다.

**단계 2 (LLM 래퍼)**
- Qwen의 json_schema strict 지원 여부를 먼저 확인하고, 안 되면
  json_object + pydantic 검증 + 1회 재요청 패턴 적용 (conventions.md 참고)
- 모델명, base_url, API key는 모두 환경변수로 읽고 코드에 하드코딩하지 않는다.

**단계 3 (라우팅)**
- 라우팅 실패 케이스 테스트 필수: 빈 문자열, 잡담, 복수 의도
- temperature 0 고정

**단계 5 (Supervisor)**
- Worker 실패 시 전체 중단 대신 해당 섹션에 "수집 실패" 표기 후 계속 (partial failure 허용)
- 리포트 모드의 Worker 실행 순서: field_status → risk_alert → delay_pred → dispatching → report

**단계 7~8 (대시보드)**
- 이벤트 스키마·화면 구성은 `docs/dashboard.md`를 기준으로 구현
- 대시보드가 없어도 CLI가 완전히 동작해야 한다 (의존 역전 금지)

**단계 10~11 (센서 스트림)**
- 설계 기준은 `docs/sensor-stream.md`. 시뮬레이터는 반드시 별도 프로세스로 실행
- 자동 트리거 판정은 코드만 담당 (LLM 개입 금지), 쿨다운 5분 필수

**단계 12 (SQLite, 선택)**
- 표준 라이브러리 sqlite3 사용 (의존성 추가 없음). 스키마는 CSV 컬럼 그대로
- CSV → DB 적재 스크립트(`scripts/load_db.py`)와 loader 내부 교체만. 이 전환이
  "코드 수정 0줄"로 되는 것 자체가 loader 계층 설계의 증명이므로 결과를 process.md에 기록
- 단계 1~9 완료 전에는 착수 금지 (데모 우선)

**단계 9 (증빙)**
- 데모 케이스(SCH 단위 HIGH/CRITICAL risk와 reschedule_action 추천)가 리포트에 잡힌 결과를 커밋
- 대시보드에서 실행 완료 후 오른쪽 최종 리포트 drawer가 열린 스크린샷을 README 상단에 삽입
- README의 "현재 구현 상태" 표를 이 문서 상태와 동기화

## 현재 확인된 상태

- `docs/service_concept.md` 기준 서비스 범위는 Etch 공정군 내 Lot 우선순위 및 설비 배정 재조정 PoC로 적절하다.
- `docs/roadmap.md`의 큰 흐름은 서비스 컨셉과 일치한다.
- `src/`, `tests/`, `reports/`, `process.md` 골격 생성, 단계 1 tools 구현, 단계 2 schemas/LLM 검증 래퍼, 단계 3 Routing Agent, 단계 4 Worker 4종, 단계 5 report Worker + Supervisor 조립, 단계 6 CLI + EventBus, 단계 7 FastAPI/SSE, 단계 8 Vue 대시보드, 단계 9 README/증빙 산출물 커밋은 완료됐다.
- 단계 10 (MQTT 센서 스트림)은 완료됐다 — `src/sensors/`(simulator·subscriber·rules) + `SensorPanel.vue` 센서 패널, temp-drift E2E 검증 증빙은 `reports/dashboard-stage10-sensor-panel.png` (상세: `docs/sensor-stream.md` 구현 상태 절).
- 단계 11 (센서 자동 트리거)은 완료됐다 — 라인당 5분 쿨다운·mode "auto"·auto_run_triggered 이벤트·타임라인 "자동 실행" 배지. temp-drift E2E 증빙은 `reports/stage11-auto-trigger-events.log`. 자동 트리거는 데모용 단순 임계치 규칙이며, 추후 ML 기반 예측(예상 이상 감지) 트리거로 확장할 계획이다 (README 한계·확장 여지 참고).
- `notebooks/01-monitoring-agents.ipynb`, `notebooks/02-supervisor-report.ipynb`는 CrewAI 기반 초기 프로토타입이며, 수정 대상이 아니라 이관 참고 자료다.

## 의존성 추가 기록

| 날짜 | 라이브러리 | 선택 사유 |
|---|---|---|
| 2026-07-06 | fastapi, uvicorn, sse-starlette | 대시보드 SSE 스트리밍 (docs/dashboard.md) |
| 2026-07-06 | paho-mqtt (+ Mosquitto 브로커) | 센서 pub/sub 스트림 (docs/sensor-stream.md) |
| 2026-07-07 | vue 3, vite, typescript, vue-tsc, @vitejs/plugin-vue (frontend devDeps) | 단계 8 대시보드 SPA — docs/dashboard.md 기술 선택(Vite+Vue 3+TS) 그대로 |
| 2026-07-07 | marked (frontend) | 결과 패널 report_markdown 렌더링 (docs/dashboard.md ③에 명시된 의존성) |

## 하지 않는 것 (스코프 제외)

- DB 연동, 실공정 데이터 연결, 인증·다중 사용자
- 전공정 전체 Fab route 최적화
- delay_pred의 ML 모델화 (확장 여지로만 문서화)
