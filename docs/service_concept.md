# 서비스 컨셉: Supervisor + Dynamic Dispatching Agent

작성일: 2026-07-06

## 1. 한 줄 정의

**생산 Supervisor AI Service**로 공정군의 현황과 위험을 감지하고, 그 위험을 기반으로 **공정군 내 작업 순서 및 대체 설비를 추천하는 Dynamic Dispatching / Rescheduling Agent**까지 연결하는 PoC.

## 2. 범위

이 프로젝트는 반도체 전공정 전체 Fab Scheduler가 아니다.

정확한 범위는 다음이다.

> **반도체 Etch(식각) 공정군 내 Lot 작업의 우선순위와 설비 배정을 재조정하는 AI Scheduling PoC**

Etch 공정군으로 좁힌 이유는 명확하다.

- 실제 반도체 팹 전체 Route는 공정 반복, queue time, recipe qualification, batch, WIP 제약이 복잡하다.
- 현재 엑셀 발의안의 테이블 구조는 전체 Route 최적화보다 `process_step`, `assigned_machine`, `risk_score`, `alternative_machine` 중심이다.
- 따라서 PoC 단계에서는 특정 공정군 안에서 “어떤 작업을 어떤 설비에 넣을지”를 판단하는 구조가 가장 자연스럽다.
- 식각은 웨이퍼 위의 막이나 재료를 선택적으로 제거하는 공정이며, RIE, ALE, conductor etch, dielectric etch처럼 응용과 장비군을 나눠 설명하기 좋다.
- 따라서 `기존 설비 → 대체 설비`, `기존 순번 → 신규 순번` 구조가 식각 공정군의 설비 가용성 기반 재배정과 작업 순서 조정 스토리에 잘 맞는다.

## 3. 서비스 구조

서비스는 두 레이어로 본다.

| 레이어 | 역할 | 주요 산출 |
|---|---|---|
| Supervisor AI Service | 공정군 현황, 설비 상태, 지연 위험을 감지하고 요약 | 위험 목록, 알림, 근거 표, 현황 리포트 |
| Dynamic Dispatching / Rescheduling Agent | 위험 작업에 대해 대체 설비와 작업 순서 변경안을 추천 | `reschedule_action`, 대체 설비, 새 작업 순서, 예상 개선율 |

즉, 흐름은 다음과 같다.

```text
schedule_master
      |
      v
work_status + delay_risk + machine_process_map
      |
      v
Supervisor AI Service
      |
      v
Dynamic Dispatching / Rescheduling Agent
      |
      v
reschedule_action
```

## 4. 핵심 질문

이 서비스가 답해야 하는 질문은 다음이다.

- 현재 지연 위험이 높은 schedule은 무엇인가?
- 어떤 설비가 정지, 점검중, 과부하 상태인가?
- 현재 배정된 설비가 위험하다면 같은 `process_step`을 처리할 수 있는 대체 설비가 있는가?
- 어떤 작업을 먼저 당겨야 납기 위험을 줄일 수 있는가?
- AI가 제안한 재조정 액션을 작업자가 수락했는가?

## 5. 데이터 모델

### 5.1 Canonical Tables

엑셀 발의안의 구조를 기준으로 다음 4개 테이블을 canonical 데이터로 둔다.

| 파일 | 역할 |
|---|---|
| `schedule_master.csv` | 생산 스케줄 허브. 작업, 제품, 공정, 배정 설비, 납기, 우선순위 관리 |
| `work_status.csv` | 설비 및 작업 현황. 설비 상태, 부하율, 작업자, 산출량 관리 |
| `delay_risk.csv` | 지연 위험 분석. 위험 점수, 위험 등급, 지연 확률, 예상 지연 시간 관리 |
| `reschedule_action.csv` | 재조정 액션. 대체 설비, 순서 변경, 수락 여부, 예상 개선율 관리 |

`delay_risk.risk_factor`의 PoC용 범주와 공개 자료 근거는 `docs/etch_risk_factors.md`에 따로 정리한다.

### 5.2 추가 매핑 테이블

`machine_process_map.csv`는 `process_step`별로 어떤 설비가 배정 가능한지 정의한다.

| 필드 | 의미 |
|---|---|
| `process_step` | 작업 공정. 예: `ETCH_DIELECTRIC`, `ETCH_CONDUCTOR`, `ETCH_VIA`, `ETCH_ALE_TRIM` |
| `machine_id` | 설비 ID. 예: `ETCH-101` |
| `recipe_id` | 해당 설비에서 사용하는 레시피 ID |
| `qualified_yn` | 해당 설비가 그 공정/레시피를 처리할 수 있는지 |
| `avg_process_hr` | 평균 처리 시간 |
| `available_yn` | 현재 대체 설비 후보로 사용할 수 있는지 |

현재 데이터에는 운영 판단을 위해 `process_name`, `preferred_rank`, `setup_time_min`, `machine_status`, `current_load`도 함께 둔다.

## 6. PoC 시나리오

공정군은 **300mm Fab Etch Area**로 제한한다.

`process_step`은 다음 4개로 둔다.

| process_step | 의미 |
|---|---|
| `ETCH_DIELECTRIC` | Dielectric etch |
| `ETCH_CONDUCTOR` | Conductor etch |
| `ETCH_VIA` | Via etch |
| `ETCH_ALE_TRIM` | ALE trim etch |

예시 상황:

- `SCH-0003`: `ETCH_VIA` 작업이 `ETCH-105`에 배정되었으나 설비 정지 상태
- `delay_risk`에서 `CRITICAL`로 판정
- `machine_process_map`에서 `ETCH_VIA`를 처리할 수 있고 가용한 설비를 탐색
- `ETCH-102` 또는 `ETCH-104` 같은 대체 설비를 추천
- `reschedule_action`에 `설비대체` 액션을 생성하고 `applied_yn`으로 수락 여부 추적

## 7. 포트폴리오 설명 문장

면접이나 문서에서는 이렇게 설명하는 것이 정확하다.

> 기존 생산 Supervisor AI Service에 Etch 공정군 단위 Dynamic Dispatching 기능을 확장했다. `schedule_master`, `work_status`, `delay_risk`를 조인해 지연 위험을 감지하고, `machine_process_map`을 통해 해당 식각 공정을 처리할 수 있는 qualified 설비만 후보로 삼아 `reschedule_action`을 추천한다.

피해야 할 표현:

- 반도체 전공정 전체 Fab Scheduler
- 전체 Route 최적화
- Fab-wide WIP optimization

위 표현들은 현재 데이터 구조보다 훨씬 큰 문제를 암시하므로 쓰지 않는 것이 좋다.
