# troubleshooting.md — 설계 선택과 트러블슈팅 메모

```
작성자 : 신유진
작성 목적 : 프로젝트 진행 중 신경 쓴 설계 선택, 예상 질문, 트러블슈팅 포인트를 정리한다.
작성일 : 2026-07-06
```

## 1. 왜 Etch 공정군으로 범위를 좁혔나

이 프로젝트는 반도체 전공정 전체 Fab Scheduler가 아니라,
**Etch 공정군 안에서 Lot 우선순위와 설비 배정을 재조정하는 PoC**로 정의했다.

전체 Fab scheduling은 route 반복, queue time, recipe qualification, batch 제약,
WIP 제약이 얽혀 있어 현재 데이터셋과 PoC 범위를 크게 넘어간다.
반면 현재 데이터는 `schedule_master`, `work_status`, `delay_risk`,
`machine_process_map`, `reschedule_action`처럼 특정 공정 step과 설비 배정,
리스크, 대체 설비 추천을 연결하기 좋은 구조다.

Etch를 선택한 이유는 다음과 같다.

- `process_step`별로 처리 가능한 설비가 다르고, `qualified_yn`, `recipe_id` 같은 제약을 설명하기 좋다.
- 설비 down, chamber clean, recipe qualification, endpoint abnormal 같은 리스크가 dispatching 판단과 자연스럽게 연결된다.
- `기존 설비 -> 대체 설비`, `기존 순번 -> 신규 순번` 구조가 Etch 공정군의 가용 설비 기반 재배정 시나리오와 잘 맞는다.
- 포트폴리오 설명에서 “전체 Fab 최적화”처럼 과한 주장을 피하고, 데이터로 증명 가능한 범위만 말할 수 있다.

따라서 면접이나 문서에서는 “Etch 공정군 단위 Dynamic Dispatching / Rescheduling PoC”라고 설명하는 것이 정확하다.

## 2. 왜 SSE를 썼나

대시보드는 Supervisor 실행 과정을 실시간으로 보여줘야 한다.
필요한 흐름은 서버가 `run_start`, `routing_decision`, `agent_start`,
`tool_call`, `agent_end`, `run_end` 같은 이벤트를 브라우저로 계속 밀어주는 구조다.

SSE를 선택한 이유는 다음과 같다.

- 이 프로젝트의 실시간 통신은 대부분 **서버 -> 브라우저 단방향 이벤트 스트림**이다.
- WebSocket처럼 양방향 세션을 직접 관리할 필요가 없다.
- HTTP 기반이라 FastAPI에서 구현이 단순하고, 브라우저는 `EventSource`로 바로 구독할 수 있다.
- 자동 재연결, `Last-Event-ID` 기반 재전송 같은 패턴을 적용하기 쉽다.
- 실행 과정 관찰용 PoC에는 복잡한 메시지 브로커나 WebSocket room 관리가 과하다.

주의한 점은 이벤트의 단일 소스다.
LLM이 이벤트를 만들지 않고, Supervisor/Worker 코드가 EventBus를 통해 이벤트를 발행한다.
CLI 로그와 대시보드 SSE가 같은 EventBus를 구독하게 만들면,
콘솔과 화면이 서로 다른 사실을 보여주는 문제를 줄일 수 있다.

트러블슈팅 포인트:

- `run_end`는 성공/실패와 관계없이 항상 마지막에 1회 발행한다.
- `seq`는 run 안에서 단조 증가해야 하며 중간에 빠지면 안 된다.
- `routing_decision`은 모든 `agent_start`보다 먼저 나와야 한다.
- 대시보드는 상태 전이표에 없는 이벤트 순서를 받으면 화면을 깨뜨리지 말고 무시/경고 처리한다.
- 프론트 개발 모드에서는 Vite proxy를 사용해 CORS 설정을 늘리지 않는다.

## 3. 왜 MQTT를 추가 설계했나

SSE는 대시보드로 실행 상태를 보여주는 채널이고,
MQTT는 센서/설비 계층에서 서버로 실시간 telemetry를 보내는 채널이다.
역할이 다르다.

MQTT를 둔 이유는 스마트팩토리 구조를 축소해서 보여주기 위해서다.

```text
sensor_sim.py -> Mosquitto -> subscriber.py -> rules.py -> EventBus/Supervisor
```

이 구조에서는 센서 시뮬레이터와 FastAPI 서버가 직접 붙지 않는다.
중간에 MQTT broker를 두어 실제 현장의 “장비/센서 계층과 서비스 계층 분리”를 작게 재현한다.

선택 기준은 다음과 같다.

- 센서값은 최신성이 중요하므로 QoS 0, retain false로 충분하다.
- 로컬 PoC에서는 인증/TLS를 넣지 않고, Mosquitto + `paho-mqtt`로 단순하게 검증한다.
- 이상 감지 판단은 LLM이 아니라 `rules.py` 코드가 한다.
- 같은 이상으로 Supervisor가 반복 실행되지 않도록 라인당 5분 cooldown을 둔다.
- 수동 실행 중 자동 트리거가 오면 대기열에 쌓지 않고 폐기한다. 센서 판단은 최신 상태가 더 중요하기 때문이다.

트러블슈팅 포인트:

- Mosquitto broker가 떠 있지 않으면 publisher/subscriber가 연결되지 않는다.
- Windows에서는 Mosquitto 서비스 실행 여부와 1883 포트 점유를 먼저 확인한다.
- subscriber는 payload를 바로 신뢰하지 말고 pydantic 검증 후 EventBus로 넘긴다.
- `sensor_update`는 빈번하므로 최근 60초만 메모리에 유지하고, DB 저장은 PoC 범위에서 제외한다.
- 자동 트리거는 `sensor_alert` 발생 후 cooldown을 확인한 뒤 `mode: "auto"` 실행으로 연결한다.

## 4. LLM은 어디까지 쓰나

이 프로젝트에서 LLM은 판단 숫자를 만들지 않는다.

LLM이 해도 되는 일:

- 사용자 질문을 어떤 Worker로 보낼지 라우팅한다.
- tool 결과를 사람이 읽기 좋은 summary, alert, report 문장으로 설명한다.
- Qwen/OpenAI structured output으로 정해진 JSON schema를 채운다.

LLM이 하면 안 되는 일:

- `risk_score`, `priority`, `current_load`, `setup_time_min`, `candidate_rank`를 생성하거나 수정한다.
- 설비 후보를 임의로 고른다.
- tool이 만든 evidence table을 다시 작성한다.

수치와 추천 판단은 `src/tools/`의 deterministic Python 코드가 담당한다.
LLM 응답은 반드시 pydantic schema로 검증하고, 실패하면 1회 복구 요청 후 그래도 실패하면 recoverable error로 다룬다.

## 5. Qwen/OpenAI provider 처리

기본 provider는 `LLM_PROVIDER=auto`다.
`auto`는 Qwen을 먼저 시도하고 실패하면 OpenAI fallback을 사용한다.

환경변수만 사용한다.

- `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL_NAME`
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL_NAME`

API key는 요청 payload, 로그, SSE 이벤트, 리포트에 노출하지 않는다.
SSE에는 provider 이름, 모델명, fallback 여부만 표시한다.

Qwen은 엔드포인트/모델별로 strict `json_schema` 지원이 다를 수 있으므로,
현재 구현은 `json_object` + pydantic 검증 + 1회 복구 요청 패턴을 쓴다.

## 6. 데이터와 API에서 지킨 선

데이터 조회 API는 CSV 원본 컬럼만 반환한다.
프론트 표시를 위해 컬럼명을 바꾸거나 없는 필드를 만들어 반환하지 않는다.
승인/거절/재추천 같은 workflow 필드는 API payload와 SSE 이벤트에서만 정의한다.

추천 판단도 같은 원칙을 따른다.

- 위험 작업 필터링: `score_delay_risk`
- 설비 후보 필터링/정렬: `find_machine_candidates`
- 재조정 액션 생성: `build_reschedule_actions`
- 문장 요약: LLM

이 선을 지키면 “AI가 추천을 만들었다”가 아니라
“코드가 계산한 추천을 AI가 설명했다”고 명확히 말할 수 있다.

## 7. 리스크 점수를 새로 만들지 않은 이유

초기에는 `score_delay_risk`라는 이름 때문에 위험 점수를 코드가 새로 계산하는 것처럼 보일 수 있었다.
하지만 PoC 설명의 정직성을 위해 새 risk score 산식을 만들지 않고,
`delay_risk.csv`의 기존 `risk_score`, `risk_level`, `delay_probability`,
`estimated_delay_hr`를 기준값으로 신뢰하기로 했다.

이 결정의 이유는 다음과 같다.

- 현재 데이터에는 이미 리스크 점수와 등급이 들어 있다.
- 임의의 가중치 산식을 새로 만들면 “왜 그 가중치인가?”라는 설명 부담이 생긴다.
- 현업 관점에서는 새 점수 발명보다 조회, 필터, 정렬 기준이 명확한 쪽이 납득하기 쉽다.
- LLM이 숫자를 만들지 않는다는 프로젝트 원칙과도 맞다.

따라서 `score_delay_risk`는 “점수 재계산 함수”가 아니라
“위험 계획 조회/필터/정렬 함수”로 해석한다.

현재 기준은 다음과 같다.

- `schedule_master.status='지연'` 또는 `due_date <= asof 날짜 + 3일`
- `delay_risk.risk_level in ('CRITICAL', 'HIGH')`
- 정렬: `priority ASC`, `risk_score DESC`, `due_date ASC`, `schedule_id ASC`

이 기준은 `docs/risk-scoring.md`와 `process.md`의 단계 1 보정에 맞춘 것이다.

## 8. 대체 설비 후보를 엄격히 제한한 이유

대체 설비 추천은 단순히 부하가 낮은 설비를 고르는 문제가 아니다.
특히 Etch 공정에서는 같은 공정 step을 처리할 수 있는지, recipe qualification이 되어 있는지가 중요하다.

그래서 `find_machine_candidates`와 `build_reschedule_actions`는 후보 설비를 다음 조건으로 제한한다.

- 같은 `process_step`
- `qualified_yn='Y'`
- `machine_status='가동'`
- `available_yn='Y'`
- `current_load < 0.5`

이 조건을 둔 이유는 추천 결과가 “그럴듯한 설비명”이 아니라,
데이터상 실제로 처리 가능한 설비 후보여야 하기 때문이다.
면접에서는 이 부분을 “LLM 추천이 아니라 제약 기반 후보 필터링”이라고 설명하면 된다.

## 9. action workflow를 따로 둔 이유

`reschedule_action.csv`에는 `applied_yn`이 있지만,
이 값만으로 승인/거절/재추천/에스컬레이션 상태를 모두 표현하기 어렵다.
특히 `applied_yn='N'`을 거절로 해석하면 잘못이다.
이 값은 “아직 승인되지 않은 제안”으로 봐야 한다.

그래서 API/SSE 레벨에서는 별도 workflow 상태를 정의했다.

- `PENDING`: 제안됐지만 아직 응답 없음
- `ACCEPTED`: supervisor가 승인
- `REJECTED`: 제안 거절
- `REPROPOSED`: 조건을 바꿔 재추천
- `ESCALATED`: 자동 추천만으로 처리하기 어려워 수동 확인 필요
- `EXPIRED`: 현장 상태 변화나 기준시각 변경으로 제안이 더 이상 유효하지 않음

이렇게 나눈 이유는 다음과 같다.

- 원본 CSV 컬럼을 억지로 확장하지 않고 보존할 수 있다.
- 대시보드에서 supervisor가 “승인/거절/재추천”을 명확히 처리할 수 있다.
- 거절 사유와 재추천 조건은 원본 데이터가 아니라 workflow 이벤트로 다루는 것이 자연스럽다.
- 단계 7 API와 단계 8 대시보드가 같은 상태 모델을 공유할 수 있다.

PoC에서는 단일 supervisor 사용자를 전제로 하므로 별도 권한/역할 모델은 두지 않는다.
요청 payload에는 `supervisor_id`만 둔다.

## 10. 등급별 알림/승인 정책

모든 리스크를 같은 강도로 처리하면 대시보드가 쉽게 시끄러워진다.
그래서 `risk_level`별로 알림과 승인 정책을 나눴다.

| risk_level | 정책 |
|---|---|
| `CRITICAL` | 즉시 알림 + 재조정 액션 생성 + 승인/거절 필수 |
| `HIGH` | 알림 + 재조정 액션 생성 + 승인/거절 권장 |
| `MEDIUM` | 대시보드/리포트 표시, 승인 플로우 없음 |
| `LOW` | 기록 유지, 별도 처리 없음 |

단계 1 tools는 CRITICAL/HIGH에 대해서만 `build_reschedule_actions`를 생성한다.
MEDIUM/LOW까지 액션을 만들면 실제 운영에서 처리해야 할 제안이 너무 많아지고,
PoC의 핵심인 “위험 작업에 대한 빠른 재배정”이 흐려진다.

Human-in-the-loop 기준도 함께 정했다.

- CRITICAL 액션이 거절되면 다음 후보를 재제안하거나 관리자 수동 확인으로 에스컬레이션한다.
- HIGH 액션이 거절되면 모니터링을 유지하고, CRITICAL로 상승하거나 납기 초과가 보이면 에스컬레이션한다.
- 실제 `applied_yn` 업데이트는 이후 API/대시보드 단계에서 처리한다.

## 11. 발표/면접에서 바로 답할 수 있는 문장

Etch 범위:

> 전체 Fab Scheduler를 만들었다고 주장하지 않고, Etch 공정군 안에서 Lot 우선순위와 qualified 설비 배정을 재조정하는 PoC로 범위를 제한했습니다. 현재 데이터 구조가 process_step, assigned_machine, risk_score, alternative_machine 중심이라 이 범위가 가장 정직합니다.

SSE:

> 대시보드는 서버가 실행 이벤트를 브라우저로 밀어주는 단방향 스트림이면 충분해서 SSE를 선택했습니다. WebSocket보다 단순하고, EventSource의 재연결과 Last-Event-ID를 활용하기 쉽습니다.

MQTT:

> SSE는 화면으로 보내는 채널이고 MQTT는 센서 계층에서 서비스 계층으로 들어오는 채널입니다. Mosquitto를 사이에 둬 센서 시뮬레이터와 FastAPI 서버를 분리했고, 실제 스마트팩토리의 broker 기반 telemetry 구조를 작게 재현했습니다.

LLM:

> LLM은 라우팅과 설명만 맡고, 위험 점수·설비 후보·작업 순서 같은 수치 판단은 deterministic tool이 계산합니다. 그래서 결과를 재현 가능하게 테스트할 수 있습니다.

리스크 점수:

> 리스크 점수는 새로 발명하지 않았습니다. `delay_risk.csv`에 있는 `risk_score`와 `risk_level`을 기준값으로 쓰고, 코드는 HIGH/CRITICAL 필터링과 정렬만 수행합니다. 임의 가중치를 만들지 않는 편이 PoC 설명에 더 정직합니다.

대체 설비:

> 대체 설비는 LLM이 고르지 않습니다. 같은 `process_step`이고 `qualified_yn='Y'`, `machine_status='가동'`, `available_yn='Y'`, `current_load < 0.5`인 설비만 후보로 필터링합니다.

액션 workflow:

> `applied_yn='N'`은 거절이 아니라 아직 승인되지 않은 제안입니다. 그래서 API에서는 PENDING, ACCEPTED, REJECTED, REPROPOSED, ESCALATED 같은 workflow 상태를 따로 정의했습니다.

등급별 승인:

> CRITICAL은 즉시 알림과 승인/거절 필수, HIGH는 승인/거절 권장, MEDIUM/LOW는 리포트 중심으로 처리합니다. 모든 리스크에 액션을 만들면 운영 화면이 시끄러워져서 HIGH 이상만 재조정 대상으로 잡았습니다.
