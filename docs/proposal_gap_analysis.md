# SI 발의안 반영 방향 정리

작성일: 2026-07-06  
기준 문서: `docs/service_concept.md`

## 결론

엑셀 발의안은 전공정 전체 Fab Scheduler라기보다 **공정군 단위 Dynamic Dispatching / Rescheduling Agent**에 가깝다.

따라서 이 프로젝트의 최종 방향은 다음으로 잡는다.

> **생산 Supervisor AI Service + 공정군 내 작업 순서 및 대체 설비를 추천하는 Dynamic Dispatching / Rescheduling Agent**

## 해석

엑셀의 핵심 테이블은 다음 관계를 가진다.

```text
schedule_master.schedule_id
  -> work_status.schedule_id
  -> delay_risk.schedule_id
  -> reschedule_action.schedule_id
```

`schedule_master` 한 행은 전체 Fab Route가 아니라 “현재 스케줄링 대상 작업 하나”에 가깝다.
핵심 필드도 `process_step`, `assigned_machine`, `priority`, `due_date`, `status`이므로
현재 작업을 어떤 설비에 넣고 어떤 순서로 처리할지 판단하는 구조다.

`reschedule_action` 역시 `original_machine`, `alternative_machine`, `original_sequence`, `new_sequence`,
`action_type`을 가지므로 로컬 재스케줄링에 적합하다.

## 반도체 PoC 범위

반도체 맥락에서는 **Etch(식각) 공정군**으로 범위를 제한한다.

| 항목 | 선택 |
|---|---|
| 공정군 | 300mm Fab Etch Area |
| 작업 단위 | schedule_id 단위 etch 작업 |
| 공정 단계 | `ETCH_DIELECTRIC`, `ETCH_CONDUCTOR`, `ETCH_VIA`, `ETCH_ALE_TRIM` |
| 설비 | `ETCH-101` ~ `ETCH-106` |
| 핵심 판단 | 위험 schedule 식별, 대체 설비 후보 탐색, 작업 순서 재조정 |

이 범위는 PoC로 적절하다. 식각은 웨이퍼 위의 막이나 재료를 선택적으로 제거하는 공정이고,
RIE, ALE, conductor etch, dielectric etch 등 응용과 장비군을 나눠 설명하기 자연스럽다.
따라서 `reschedule_action`의 기존 설비→대체 설비, 기존 순번→신규 순번 구조가
식각 공정군의 설비 가용성 기반 재배정 및 작업 순서 조정과 잘 맞는다.

전공정 전체의 반복 route, queue time, batch, downstream bottleneck까지
다루겠다고 하면 현재 데이터 모델보다 훨씬 큰 시스템이 필요하다.

## 데이터 반영

현재 canonical CSV는 다음 5개다.

| 파일 | 역할 |
|---|---|
| `schedule_master.csv` | 생산 스케줄 허브 |
| `work_status.csv` | 설비·작업 현황 |
| `delay_risk.csv` | 지연 위험 분석 |
| `reschedule_action.csv` | 재조정 액션 이력 |
| `machine_process_map.csv` | `process_step`별 배정 가능 설비/레시피/가용성 매핑 |

특히 `machine_process_map.csv`를 추가해 “이 설비가 이 공정을 처리할 수 있는가?”를 명시한다.
대체 설비 추천은 이 테이블에서 같은 `process_step`, `qualified_yn='Y'`, `available_yn='Y'`인 후보만 사용한다.

## 설명 문장

포트폴리오에서는 다음 문장이 가장 정확하다.

> 생산계획, 설비 부하, 작업 상태, 지연 리스크를 연계해 공정군 단위의 작업 우선순위와 대체 설비를 재조정하는 AI Scheduling PoC입니다.

반도체 버전으로는 다음처럼 말한다.

> 반도체 Etch 공정군 내 설비 상태와 지연 위험을 기반으로 Lot 작업 순서 및 대체 설비를 동적으로 추천하는 Dynamic Dispatching / Rescheduling Agent PoC입니다.

피해야 할 표현:

- 반도체 전공정 전체 Fab Scheduler
- Fab-wide route optimization
- 전체 WIP 흐름 최적화
