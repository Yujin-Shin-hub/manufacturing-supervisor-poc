# 리스크 및 재조정 기준

작성일: 2026-07-06

## 목적

`score_delay_risk`와 `build_reschedule_actions`가 따르는 기준을 명시한다.
이 PoC는 새 ML 점수나 LLM 점수를 만들지 않고, 엑셀 시나리오의 운영 흐름과
canonical CSV에 이미 존재하는 `delay_risk.risk_score`, `delay_risk.risk_level`을 기준으로 판단한다.

## 전체 처리 흐름

| 단계 | 작업명 | 기준 |
|---|---|---|
| STEP 1 | 납기 위험 계획 식별 | `schedule_master.status='지연'` 또는 `due_date <= asof 날짜 + 3일` |
| STEP 2 | 해당 계획의 리스크 확인 | `delay_risk.schedule_id` 조인 후 `risk_level in ('CRITICAL', 'HIGH')`만 대상 |
| STEP 3 | 설비 가동 가능 여부 확인 | 같은 `process_step`을 처리할 수 있고 `qualified_yn='Y'`, `machine_status='가동'`, `available_yn='Y'`, `current_load < 0.5`인 설비 |
| STEP 4 | 재조정 조치 생성 및 제안 | 원 설비와 다른 후보 중 `current_load`, `preferred_rank`, `setup_time_min` 순으로 선택하고 `applied_yn='N'` 액션 생성 |
| STEP 5 | 작업자 수락/기각 반영 | 이후 단계에서 `reschedule_action.applied_yn` 업데이트로 반영한다 |

## 정렬 기준

- 위험 계획: `priority ASC`, `risk_score DESC`, `due_date ASC`, `schedule_id ASC`
- 대체 설비 후보: `current_load ASC`, `preferred_rank ASC`, `setup_time_min ASC`, `machine_id ASC`

## 점수 기준

`score_delay_risk`는 새로운 점수를 재계산하지 않는다.
`delay_risk.csv`의 `risk_score`, `risk_level`, `delay_probability`, `estimated_delay_hr`를
리스크의 기준값으로 사용한다.

등급 해석은 데이터 생성 기준을 따른다.

| risk_level | 기준 |
|---|---|
| CRITICAL | `risk_score >= 85` |
| HIGH | `65 <= risk_score < 85` |
| MEDIUM | `35 <= risk_score < 65` |
| LOW | `risk_score < 35` |

현재 단계 1에서는 HIGH/CRITICAL만 재조정 후보로 삼는다.

## 등급별 알림 및 승인 정책

| risk_level | 운영 의미 | 시스템 액션 | supervisor 응답 | 후속 처리 |
|---|---|---|---|---|
| CRITICAL | 이미 지연 영향이 크거나 즉시 재배치가 필요한 상태 | 즉시 알림 + 재조정 액션 생성 + supervisor 승인 요청 | 승인 / 거절 필수 | 승인 시 `applied_yn='Y'`, 거절 시 재제안 또는 수동 확인 |
| HIGH | 납기 D+3 안에 지연 가능성이 높거나 대체 설비 검토가 필요한 상태 | 알림 + 재조정 액션 생성 + supervisor 승인 요청 | 승인 / 거절 권장 | 승인 시 `applied_yn='Y'`, 거절 시 모니터링 유지 |
| MEDIUM | 관찰 필요하지만 즉시 재배치 대상은 아닌 상태 | 대시보드/리포트 표시 | 응답 없음 | 다음 실행에서 HIGH 이상으로 상승하면 액션 생성 |
| LOW | 정상 관리 범위 | 기록만 유지 | 응답 없음 | 별도 처리 없음 |

단계 1 tools는 CRITICAL/HIGH에 대해서만 `build_reschedule_actions` 결과를 만든다.
생성 시점의 `applied_yn='N'`은 "아직 supervisor가 승인하지 않은 제안"을 뜻한다.
승인/거절 UI와 실제 `applied_yn` 업데이트는 이후 Worker/API/대시보드 단계에서 구현한다.

### Human-in-the-loop 처리 규칙

- CRITICAL: 알림과 동시에 승인/거절을 반드시 받아야 한다. 거절되면 같은 `process_step`의 다음 후보를 재제안하고, 후보가 없으면 supervisor 수동 확인 대상으로 표시한다.
- HIGH: 승인/거절을 받을 수 있으면 받되, 거절되더라도 즉시 에스컬레이션하지 않는다. 다음 실행에서 CRITICAL로 상승하거나 납기 초과가 되면 에스컬레이션한다.
- MEDIUM/LOW: 승인 플로우에 태우지 않는다. 리포트와 대시보드에서만 관찰한다.

## asof 기준

`asof`는 판단 기준시각이다. 납기 D+3 계산은 `asof`의 날짜를 기준으로 한다.
예를 들어 `asof='2026-04-15 14:00'`이면 D+3 기준일은 `2026-04-18`이다.
