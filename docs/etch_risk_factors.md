# Etch Risk Factors

작성일: 2026-07-06

## 목적

`delay_risk.csv`의 `risk_factor` 값은 특정 회사의 실제 내부 taxonomy가 아니라,
공개적으로 확인 가능한 식각 공정 특성과 팹 운영 리스크를 바탕으로 만든 **PoC용 risk category**다.

## 적용 Risk Factor

| risk_factor | PoC에서의 의미 | 출처/근거와의 관계 |
|---|---|---|
| `PM연장/설비다운` | 예방정비가 길어지거나 설비가 down되어 배정된 작업을 제때 처리하지 못하는 상황 | 스케줄링/dispatching 관점의 운영 리스크. 설비 상태(`machine_status`)와 직접 연결 |
| `Chamber clean 필요` | chamber residue, contamination, seasoning 문제로 clean 또는 안정화가 필요한 상황 | Lam Research 설명에서 wafer cleaning은 particle/residue/film 제거와 yield 영향에 연결됨. Etch chamber에서도 residue/particle 관리는 현실적인 운영 이슈 |
| `Recipe qualification 대기` | 특정 recipe가 해당 장비/챔버에서 검증되었는지 확인이 필요한 상황 | `machine_process_map.recipe_id`, `qualified_yn`과 연결되는 PoC 제약 |
| `Endpoint abnormal` | endpoint 신호 이상으로 under-etch/over-etch 위험 또는 추가 확인이 필요한 상황 | 식각 깊이/공정 결과는 공정 파라미터와 모니터링에 민감하다는 연구 근거에 기반한 PoC 리스크 |
| `High WIP/load` | 특정 설비 또는 공정 step에 WIP/부하가 몰려 지연 가능성이 커진 상황 | 엑셀 발의안의 `current_load`, `utilization_rate`와 직접 연결되는 dispatching 리스크 |
| `Particle/defect excursion` | particle 또는 defect 이상 발생으로 hold, rework, 추가 검사 가능성이 생긴 상황 | cleaning/contamination 및 yield 영향 설명에 기반한 품질 리스크 |
| `Gas/chemical supply issue` | 식각 gas/chemical 공급, flow, recipe 조건 이슈로 작업이 지연되는 상황 | RIE와 plasma etch는 gas flow, pressure, RF power 등 조건에 민감하다는 공개 자료에 기반 |

## 참고 자료

- Lam Research / plasma etch 개요: Lam의 plasma etch는 wafer 표면에서 재료를 선택적으로 제거해 device feature/pattern을 형성하며, RIE와 ALE를 conductive/dielectric feature 형성에 사용한다고 설명한다.  
  https://en.wikipedia.org/wiki/Lam_Research

- Reactive-ion etching 개요: RIE는 reactive plasma로 wafer 위 재료를 제거하며, pressure, gas flow, RF power 등 공정 조건에 영향을 받는다.  
  https://en.wikipedia.org/wiki/Reactive-ion_etching

- Plasma etching parameter uncertainty 연구: plasma etch 결과는 chamber pressure, gas flow rate, RF power 등 공정 변수와 wafer 위치별 변동성에 영향을 받는다고 다룬다.  
  https://arxiv.org/abs/2511.04990

- Etch depth prediction 연구: etch depth와 절연막 두께 모니터링은 device performance/yield에 중요하며, ex-situ 분석은 지연과 contamination risk를 가질 수 있다고 설명한다.  
  https://arxiv.org/abs/2505.03826

- RCA clean / particle clean 개요: semiconductor wafer cleaning에서 particle과 contamination 제거가 중요하다는 배경 자료.  
  https://en.wikipedia.org/wiki/RCA_clean

## 주의

이 문서의 risk factor는 실제 fab MES/EAP/FDC 시스템의 표준 코드를 그대로 가져온 것이 아니다.
포트폴리오 PoC에서 `delay_risk`, `work_status`, `machine_process_map`, `reschedule_action`을 자연스럽게 연결하기 위한 현실적인 범주화다.
