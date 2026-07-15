[01] run_start mode=report asof=2026-04-15 14:00
[02] routing_decision agents=field_status,risk_alert,delay_pred,dispatching
[03] agent_start agent=field_status
[04] tool_call
[05] agent_end agent=field_status alerts=5
[06] agent_start agent=risk_alert
[07] tool_call
[08] tool_call
[09] agent_end agent=risk_alert alerts=3
[10] agent_start agent=delay_pred
[11] tool_call
[12] tool_call
[13] agent_end agent=delay_pred alerts=8
[14] agent_start agent=dispatching
[15] tool_call
[16] tool_call
[17] tool_call
[18] agent_end agent=dispatching alerts=8
[19] action_proposed
[20] approval_required
[21] action_proposed
[22] approval_required
[23] action_proposed
[24] approval_required
[25] action_proposed
[26] approval_required
[27] action_proposed
[28] approval_required
[29] action_proposed
[30] approval_required
[31] action_proposed
[32] approval_required
[33] action_proposed
[34] approval_required
[35] action_proposed
[36] approval_required
[37] action_proposed
[38] approval_required
[39] action_proposed
[40] approval_required
[41] action_proposed
[42] approval_required
[43] agent_start agent=report
[44] agent_end agent=report alerts=0
[45] run_end status=done
# 제조 Supervisor 운영 리포트

- 기준시각: 2026-04-15 14:00

## 요약

- **현장 가동 현황** — 2026-04-15 14:00 기준 100개 스케줄 중 지연 22건, 설비 정지 19건, 부하 0.8 이상 45건입니다.
- **리스크 알림** — 2026-04-15 14:00 기준 HIGH/CRITICAL 위험은 총 31건입니다. CRITICAL 18건, HIGH 13건입니다.
- **지연 예측** — 2026-04-15 14:00 기준 지연 위험 31건 중 최대 예상 지연은 8.1시간, 최대 지연 확률은 0.92입니다.
- **설비 재배정 제안** — 2026-04-15 14:00 기준 재조정 제안 31건을 생성했습니다. 대체 설비는 qualified_yn=Y, 가동, available_yn=Y 후보로 제한했습니다.

## 핵심 추천 액션 (승인 필요 순)

| # | schedule_id | original_machine | alternative_machine | risk_level | impact | efficiency_gain |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | SCH-0083 | ETCH-105 | **ETCH-102** | CRITICAL | 높음 | 0.51 |
| 2 | SCH-0023 | ETCH-105 | **ETCH-102** | CRITICAL | 높음 | 0.59 |
| 3 | SCH-0094 | ETCH-103 | **ETCH-104** | CRITICAL | 높음 | 0.32 |
| 4 | SCH-0007 | ETCH-104 | **ETCH-102** | HIGH | 보통 | 0.0 |
| 5 | SCH-0066 | ETCH-101 | **ETCH-104** | HIGH | 보통 | 0.35 |

전체 12건 중 상위 5건입니다. 전체 목록은 아래 설비 재배정 제안 절의 근거 표를 참고하세요.

## 현장 가동 현황 (`field_status`)

2026-04-15 14:00 기준 100개 스케줄 중 지연 22건, 설비 정지 19건, 부하 0.8 이상 45건입니다.

### 주요 알림
- SCH-0003 ETCH_VIA 작업은 ETCH-105 설비 상태가 정지, 스케줄 상태가 지연입니다.
- SCH-0047 ETCH_VIA 작업은 ETCH-105 설비 상태가 정지, 스케줄 상태가 지연입니다.
- SCH-0012 ETCH_ALE_TRIM 작업은 ETCH-105 설비 상태가 정지, 스케줄 상태가 지연입니다.
- SCH-0011 ETCH_VIA 작업은 ETCH-105 설비 상태가 정지, 스케줄 상태가 지연입니다.
- SCH-0088 ETCH_ALE_TRIM 작업은 ETCH-105 설비 상태가 정지, 스케줄 상태가 지연입니다.

### 근거 표: field_status
| schedule_id | product | priority | due_date | status | process_step | assigned_machine | machine_status | current_load | operator |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCH-0003 | MCU-C | 3 | 2026-04-16 | 지연 | ETCH_VIA | ETCH-105 | 정지 | 0.9 | OP-003 |
| SCH-0047 | CIS-B | 3 | 2026-04-23 | 지연 | ETCH_VIA | ETCH-105 | 정지 | 0.89 | OP-002 |
| SCH-0012 | CIS-B | 5 | 2026-04-19 | 지연 | ETCH_ALE_TRIM | ETCH-105 | 정지 | 0.86 | OP-002 |
| SCH-0011 | PMIC-A | 2 | 2026-04-19 | 지연 | ETCH_VIA | ETCH-105 | 정지 | 0.84 | OP-001 |
| SCH-0088 | MCU-C | 4 | 2026-04-16 | 지연 | ETCH_ALE_TRIM | ETCH-105 | 정지 | 0.8 | OP-003 |
| SCH-0028 | MCU-C | 4 | 2026-04-19 | 지연 | ETCH_ALE_TRIM | ETCH-105 | 정지 | 0.79 | OP-003 |
| SCH-0041 | PMIC-A | 2 | 2026-04-22 | 지연 | ETCH_DIELECTRIC | ETCH-103 | 점검중 | 0.95 | OP-001 |
| SCH-0005 | DDI-E | 4 | 2026-04-20 | 지연 | ETCH_DIELECTRIC | ETCH-103 | 점검중 | 0.94 | OP-005 |
| SCH-0010 | DDI-E | 2 | 2026-04-18 | 지연 | ETCH_CONDUCTOR | ETCH-103 | 점검중 | 0.93 | OP-005 |
| SCH-0022 | CIS-B | 4 | 2026-04-18 | 지연 | ETCH_CONDUCTOR | ETCH-103 | 점검중 | 0.91 | OP-002 |
| SCH-0034 | RF-D | 5 | 2026-04-22 | 지연 | ETCH_CONDUCTOR | ETCH-103 | 점검중 | 0.86 | OP-004 |
| SCH-0056 | PMIC-A | 5 | 2026-04-24 | 지연 | ETCH_ALE_TRIM | ETCH-103 | 점검중 | 0.86 | OP-001 |

## 리스크 알림 (`risk_alert`)

2026-04-15 14:00 기준 HIGH/CRITICAL 위험은 총 31건입니다. CRITICAL 18건, HIGH 13건입니다.

### 주요 알림
- SCH-0083 ETCH_VIA CRITICAL 위험: risk_score=93.6, 원인=Particle/defect excursion
- SCH-0023 ETCH_VIA CRITICAL 위험: risk_score=92.0, 원인=PM연장/설비다운
- SCH-0094 ETCH_CONDUCTOR CRITICAL 위험: risk_score=88.7, 원인=PM연장/설비다운

### 근거 표: risk
| schedule_id | product | priority | due_date | process_step | assigned_machine | risk_score | risk_level | risk_factor | machine_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCH-0083 | MCU-C | 1 | 2026-04-17 | ETCH_VIA | ETCH-105 | 93.6 | CRITICAL | Particle/defect excursion | 정지 |
| SCH-0023 | MCU-C | 1 | 2026-04-16 | ETCH_VIA | ETCH-105 | 92.0 | CRITICAL | PM연장/설비다운 | 정지 |
| SCH-0094 | RF-D | 1 | 2026-04-18 | ETCH_CONDUCTOR | ETCH-103 | 88.7 | CRITICAL | PM연장/설비다운 | 점검중 |
| SCH-0007 | CIS-B | 1 | 2026-04-22 | ETCH_VIA | ETCH-104 | 73.3 | HIGH | Recipe qualification 대기 | 가동 |
| SCH-0066 | PMIC-A | 1 | 2026-04-15 | ETCH_CONDUCTOR | ETCH-101 | 70.3 | HIGH | PM연장/설비다운 | 가동 |
| SCH-0010 | DDI-E | 2 | 2026-04-18 | ETCH_CONDUCTOR | ETCH-103 | 100.0 | CRITICAL | Endpoint abnormal | 점검중 |
| SCH-0011 | PMIC-A | 2 | 2026-04-19 | ETCH_VIA | ETCH-105 | 100.0 | CRITICAL | High WIP/load | 정지 |
| SCH-0041 | PMIC-A | 2 | 2026-04-22 | ETCH_DIELECTRIC | ETCH-103 | 100.0 | CRITICAL | Recipe qualification 대기 | 점검중 |
| SCH-0084 | RF-D | 2 | 2026-04-16 | ETCH_ALE_TRIM | ETCH-103 | 87.8 | CRITICAL | Particle/defect excursion | 점검중 |
| SCH-0081 | PMIC-A | 2 | 2026-04-22 | ETCH_DIELECTRIC | ETCH-101 | 79.2 | HIGH | Recipe qualification 대기 | 가동 |
| SCH-0055 | DDI-E | 2 | 2026-04-15 | ETCH_VIA | ETCH-104 | 72.4 | HIGH | Chamber clean 필요 | 가동 |
| SCH-0069 | RF-D | 2 | 2026-04-16 | ETCH_DIELECTRIC | ETCH-101 | 68.6 | HIGH | Chamber clean 필요 | 가동 |

## 지연 예측 (`delay_pred`)

2026-04-15 14:00 기준 지연 위험 31건 중 최대 예상 지연은 8.1시간, 최대 지연 확률은 0.92입니다.

### 주요 알림
- SCH-0003는 예상 지연 8.1시간, 지연 확률 0.92로 CRITICAL입니다.
- SCH-0011는 예상 지연 7.8시간, 지연 확률 0.9로 CRITICAL입니다.
- SCH-0023는 예상 지연 7.8시간, 지연 확률 0.82로 CRITICAL입니다.
- SCH-0047는 예상 지연 6.9시간, 지연 확률 0.85로 CRITICAL입니다.
- SCH-0028는 예상 지연 6.1시간, 지연 확률 0.83로 CRITICAL입니다.
- SCH-0078는 예상 지연 6.0시간, 지연 확률 0.77로 CRITICAL입니다.
- SCH-0010는 예상 지연 5.9시간, 지연 확률 0.82로 CRITICAL입니다.
- SCH-0059는 예상 지연 5.9시간, 지연 확률 0.67로 HIGH입니다.

### 근거 표: delay_prediction
| schedule_id | priority | due_date | days_to_due | process_step | risk_level | delay_probability | estimated_delay_hr | impact_scope | due_risk_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCH-0003 | 3 | 2026-04-16 | 1 | ETCH_VIA | CRITICAL | 0.92 | 8.1 | 연속 | status=delayed,due_within_d3 |
| SCH-0011 | 2 | 2026-04-19 | 4 | ETCH_VIA | CRITICAL | 0.9 | 7.8 | 단일 | status=delayed |
| SCH-0023 | 1 | 2026-04-16 | 1 | ETCH_VIA | CRITICAL | 0.82 | 7.8 | 연속 | due_within_d3 |
| SCH-0047 | 3 | 2026-04-23 | 8 | ETCH_VIA | CRITICAL | 0.85 | 6.9 | 연속 | status=delayed |
| SCH-0028 | 4 | 2026-04-19 | 4 | ETCH_ALE_TRIM | CRITICAL | 0.83 | 6.1 | 연속 | status=delayed |
| SCH-0078 | 3 | 2026-04-16 | 1 | ETCH_CONDUCTOR | CRITICAL | 0.77 | 6.0 | 전체라인 | status=delayed,due_within_d3 |
| SCH-0010 | 2 | 2026-04-18 | 3 | ETCH_CONDUCTOR | CRITICAL | 0.82 | 5.9 | 단일 | status=delayed,due_within_d3 |
| SCH-0059 | 4 | 2026-04-18 | 3 | ETCH_VIA | HIGH | 0.67 | 5.9 | 연속 | due_within_d3 |
| SCH-0022 | 4 | 2026-04-18 | 3 | ETCH_CONDUCTOR | CRITICAL | 0.9 | 5.8 | 연속 | status=delayed,due_within_d3 |
| SCH-0088 | 4 | 2026-04-16 | 1 | ETCH_ALE_TRIM | CRITICAL | 0.92 | 5.6 | 전체라인 | status=delayed,due_within_d3 |
| SCH-0005 | 4 | 2026-04-20 | 5 | ETCH_DIELECTRIC | CRITICAL | 0.87 | 5.6 | 단일 | status=delayed |
| SCH-0041 | 2 | 2026-04-22 | 7 | ETCH_DIELECTRIC | CRITICAL | 0.84 | 5.6 | 단일 | status=delayed |

## 설비 재배정 제안 (`dispatching`)

2026-04-15 14:00 기준 재조정 제안 31건을 생성했습니다. 대체 설비는 qualified_yn=Y, 가동, available_yn=Y 후보로 제한했습니다.

### 주요 알림
- SCH-0083는 ETCH-105에서 ETCH-102로 설비대체를 권고합니다 (new_sequence=1, impact=높음).
- SCH-0023는 ETCH-105에서 ETCH-102로 설비대체를 권고합니다 (new_sequence=2, impact=높음).
- SCH-0094는 ETCH-103에서 ETCH-104로 설비대체를 권고합니다 (new_sequence=3, impact=높음).
- SCH-0007는 ETCH-104에서 ETCH-102로 설비대체를 권고합니다 (new_sequence=4, impact=보통).
- SCH-0066는 ETCH-101에서 ETCH-104로 설비대체를 권고합니다 (new_sequence=5, impact=보통).
- SCH-0010는 ETCH-103에서 ETCH-104로 설비대체를 권고합니다 (new_sequence=6, impact=높음).
- SCH-0011는 ETCH-105에서 ETCH-102로 설비대체를 권고합니다 (new_sequence=7, impact=높음).
- SCH-0041는 ETCH-103에서 ETCH-102로 설비대체를 권고합니다 (new_sequence=8, impact=높음).

### 근거 표: reschedule_actions
| action_id | schedule_id | risk_id | original_machine | alternative_machine | new_sequence | action_type | impact | efficiency_gain | process_step | risk_level |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GEN-0001 | SCH-0083 | RSK-0083 | ETCH-105 | ETCH-102 | 1 | 설비대체 | 높음 | 0.51 | ETCH_VIA | CRITICAL |
| GEN-0002 | SCH-0023 | RSK-0023 | ETCH-105 | ETCH-102 | 2 | 설비대체 | 높음 | 0.59 | ETCH_VIA | CRITICAL |
| GEN-0003 | SCH-0094 | RSK-0094 | ETCH-103 | ETCH-104 | 3 | 설비대체 | 높음 | 0.32 | ETCH_CONDUCTOR | CRITICAL |
| GEN-0004 | SCH-0007 | RSK-0007 | ETCH-104 | ETCH-102 | 4 | 설비대체 | 보통 | 0.0 | ETCH_VIA | HIGH |
| GEN-0005 | SCH-0066 | RSK-0066 | ETCH-101 | ETCH-104 | 5 | 설비대체 | 보통 | 0.35 | ETCH_CONDUCTOR | HIGH |
| GEN-0006 | SCH-0010 | RSK-0010 | ETCH-103 | ETCH-104 | 6 | 설비대체 | 높음 | 0.49 | ETCH_CONDUCTOR | CRITICAL |
| GEN-0007 | SCH-0011 | RSK-0011 | ETCH-105 | ETCH-102 | 7 | 설비대체 | 높음 | 0.48 | ETCH_VIA | CRITICAL |
| GEN-0008 | SCH-0041 | RSK-0041 | ETCH-103 | ETCH-102 | 8 | 설비대체 | 높음 | 0.59 | ETCH_DIELECTRIC | CRITICAL |
| GEN-0009 | SCH-0084 | RSK-0084 | ETCH-103 | ETCH-106 | 9 | 설비대체 | 높음 | 0.54 | ETCH_ALE_TRIM | CRITICAL |
| GEN-0010 | SCH-0081 | RSK-0081 | ETCH-101 | ETCH-102 | 10 | 설비대체 | 보통 | 0.4 | ETCH_DIELECTRIC | HIGH |
| GEN-0011 | SCH-0055 | RSK-0055 | ETCH-104 | ETCH-102 | 11 | 설비대체 | 보통 | 0.09 | ETCH_VIA | HIGH |
| GEN-0012 | SCH-0069 | RSK-0069 | ETCH-101 | ETCH-102 | 12 | 설비대체 | 보통 | 0.44 | ETCH_DIELECTRIC | HIGH |

### 근거 표: machine_candidates
| source_process_step | machine_id | qualified_yn | preferred_rank | setup_time_min | machine_status | current_load | available_yn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ETCH_VIA | ETCH-102 | Y | 1 | 34 | 가동 | 0.36 | Y |
| ETCH_VIA | ETCH-104 | Y | 2 | 23 | 가동 | 0.44 | Y |
| ETCH_CONDUCTOR | ETCH-104 | Y | 3 | 53 | 가동 | 0.44 | Y |
| ETCH_DIELECTRIC | ETCH-102 | Y | 2 | 45 | 가동 | 0.36 | Y |
| ETCH_ALE_TRIM | ETCH-106 | Y | 3 | 21 | 가동 | 0.29 | Y |
