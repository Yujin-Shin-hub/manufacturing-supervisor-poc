# 제조 Supervisor 운영 리포트

- 기준시각: 2026-04-15 14:00
- 요청: Find HIGH or CRITICAL SCH risk and recommend reschedule_action candidates.

## 요약

- **리스크 알림** — 2026-04-15 14:00 기준 HIGH/CRITICAL 위험은 총 31건입니다. CRITICAL 18건, HIGH 13건입니다.
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
