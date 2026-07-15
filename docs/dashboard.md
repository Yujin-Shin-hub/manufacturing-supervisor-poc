# dashboard.md — 실행 과정 시각화 대시보드

```
작성자 : 신유진
작성 목적 : Supervisor + Dispatching 실행 과정(라우팅→위임→툴콜→리포트)을 실시간으로 보여주는 UI 설계
```

## 목적

콘솔 로그로만 흘러가던 실행 과정을 대시보드에서 두 가지로 보여준다.

1. **아키텍처 뷰**: Supervisor → Routing → Worker → Tools 구조도 위에서
   지금 실행 중인 노드가 하이라이트되며 움직이는 모습
2. **로그 타임라인**: 이벤트가 시간순으로 쌓이는 리스트 + 최종 리포트 패널

## 기술 선택

- **백엔드**: FastAPI + SSE (`/events` 엔드포인트)
- **프론트**: `frontend/` — Vite + Vue 3 + TypeScript SPA
- 선택 이유: LINA 프로젝트의 Vue 3·TypeScript·SSE 스트리밍 이벤트 처리 경험을 그대로 재사용한다.
- 개발 시: Vite dev 서버(5173)가 `/run`·`/events`·`/api`를 FastAPI(8000)로 **proxy** (CORS 설정 불필요)
- 데모/제출 시: `npm run build` → FastAPI가 `frontend/dist`를 정적 서빙 (`GET /`)
  — 심사자는 uvicorn 하나만 띄우면 된다
- 상태 관리: Pinia 없이 composable 4개로 충분 (`useEventStream` — SSE 수신·재접속·상태머신,
  `useRunControl` — POST /run·실행 상태, `useNotifications` — 알림·HITL,
  `useFactorySnapshot` — 읽기 전용 /api 현황 집계). 이벤트→상태 전이는 `docs/api-spec.md` 2-2가 유일한 기준

## 이벤트 스키마 (Supervisor가 발행)

모든 이벤트는 코드가 발행한다. LLM이 이벤트를 만들지 않는다.

```json
{"type": "run_start",        "asof": "2026-04-15 10:00", "mode": "ask", "query": "..."}
{"type": "routing_decision", "target_agents": ["delay_pred","dispatching"], "reason": "..."}
{"type": "agent_start",      "agent": "dispatching"}
{"type": "tool_call",        "agent": "dispatching", "tool": "find_machine_candidates", "rows": 2}
{"type": "agent_end",        "agent": "dispatching", "summary": "...", "alerts": ["..."]}
{"type": "report_done",      "markdown": "<최종 리포트>"}
{"type": "error",            "agent": "dispatching", "message": "...", "recoverable": true}
```

구현: `src/events.py`에 `EventBus` (asyncio.Queue 기반 pub/sub).
Supervisor·Worker는 print 대신 `bus.emit(...)`을 호출하고,
CLI 모드에서는 같은 이벤트를 콘솔 로거가 구독해 출력한다 (로그와 UI의 단일 소스).

## 화면 구성 (단일 페이지 — 다크 관제 콘솔)

```
┌──────────────────────────────────────────────────────────┐
│ 헤더바: 브랜드 · RUN 상태 칩 · SSE 칩 · 리포트 버튼 · 알림 벨 │
├──────────────────────────────────────────────────────────┤
│ 실행 툴바: 모드 세그먼트(리포트/질의) · asof · query · LLM · 실행 │
├───────────────────────────┬──────────────────────────────┤
│ 실행 파이프라인 (SVG 그래프) │ Etch 라인 플로우              │
│  Supervisor→Routing→Worker │  스텝별 설비 풀·부하바(0.8 틱)· │
│  →report, 패킷 애니메이션    │  위험 스케줄 칩 배치,          │
│                           │  [현재 배치|제안 적용 후] 토글,  │
│                           │  하단 효과 요약(조치 범위 집계)  │
├───────────────────────────┴──────────────────────────────┤
│ 현황 스트립(슬림, 전폭): KPI 3종 스탯 바 | 리스크 추이 차트    │
│  (곡선+영역 그라디언트, 임계선 사용자 지정 · 기본 85)          │
├───────────────────────────┬──────────────────────────────┤
│ 재조정 제안 큐 (실행 결론)   │ 이벤트 스트림                  │
│  CRITICAL SCH-0003        │  (원문 payload 접기/펼치기)    │
│  ETCH-105 → ETCH-102 [승인]│                              │
└───────────────────────────┴──────────────────────────────┘
  + 최종 리포트: 우측 슬라이드 드로어 (run_end 도착 시 자동 오픈, 헤더 버튼으로 재오픈)
  + 우측 하단 토스트 스택 / 중앙 승인 모달 / 벨 클릭 시 알림센터 패널
```

- **KPI·리스크 추이·라인 플로우**는 읽기 전용 조회 API(api-spec 1-3)를 초기 로드·run 종료 시 조회한다.
  집계(개수 세기·시간 구간 max·합계)는 프론트 표시 계층에서만 하고, 수치 표시는 api-spec 3-1 자릿수 규칙을 따른다
- **리스크 추이 차트**: `delay_risk.detection_time` 1시간 구간별 max risk_score
  (Catmull-Rom 곡선 + 영역 그라디언트 + 임계 초과 구간 음영 + 크로스헤어 툴팁 + 최근값 배지).
  임계값은 패널 헤더에서 **사용자가 직접 지정**한다 (기본값 85 = 데이터의 CRITICAL 경계,
  localStorage에 유지). 최신 구간이 임계를 넘으면 "재조정 실행 권고" critical 알림을
  발송한다 (임계+구간 키로 dedupe — 차트와 알림이 같은 집계 함수·같은 임계값 사용)
- **Etch 라인 플로우**: process_step 4종 스윔레인에 설비 카드(상태·current_load 바·0.8 고부하 틱)와
  CRITICAL/HIGH 스케줄 칩을 배치한다. `현재 배치 / 제안 적용 후` 토글로 재조정 시 칩이 대체
  설비로 이동한 모습(유입 +n / 이탈 −n)을 보여준다. 승인된 제안은 두 모드 모두 이동으로 그린다.
  하단 효과 요약은 tool 산출값 집계만 사용한다 — CRITICAL/HIGH 조치 대상 수,
  평균 efficiency_gain, estimated_delay_hr 합계("지연 노출 대상"), 정지·점검중 설비 이탈 수,
  납기 3일 이내 포함 수. **새 수치를 만들지 않는다** (적용 후 부하 재계산 같은 예측치 표시 금지)
- **재조정 제안 큐**가 "어디로 스케줄링할지"의 정답 화면이다. `action_proposed` 이벤트
  (original_machine·alternative_machine·impact·efficiency_gain 포함, api-spec 2-1)를
  행으로 쌓고, 행마다 원설비→대체설비 전환 방향과 승인/검토 버튼(HITL)·응답 상태 칩을 보여준다.
  큐는 현재 run의 제안만 유지한다 (run_start 시 초기화, 이력은 알림센터에 남는다)

- 파이프라인은 고정 좌표 SVG 그래프에 이벤트로 상태 클래스만 토글 — 그래프 라이브러리 불필요.
  실행 중인 노드로 향하는 엣지에는 `animateMotion` 패킷(반짝이는 점)이 흐른다
  (`prefers-reduced-motion` 설정 시 패킷·펄스 비활성)
- 이벤트 스트림은 이벤트 원문을 접었다 펼 수 있게 (면접 때 "실제 이벤트 페이로드"를 바로 보여주는 용도)
- 최종 리포트는 marked로 markdown 렌더링 (npm 의존성). 그리드에 끼우지 않고
  우측 드로어로 띄워 표가 넓게 보이게 한다 (Esc/백드롭 클릭으로 닫기)
- **알림 시스템** (SSE 이벤트에서 파생, `useNotifications` composable):
  - `agent_end.alerts`·복구 가능 `error` → 우측 하단 토스트 (6초 자동 소멸)
  - `approval_required` → 중앙 모달 (승인 / 거절(사유 필수) / 나중에 처리). critical 토스트는 수동 닫기
  - 헤더 벨 아이콘 → 알림센터 패널: 세션 내 알림 이력 + 승인 대기 건의 HITL 버튼(승인/검토)
  - 승인/거절은 `POST /api/actions/{id}/accept|reject`(api-spec 1-4) 호출, 결과는
    SSE `action_accepted`/`action_rejected`로 모든 구독자에 반영
  - 새 `run_start` 수신 시 이전 run의 미응답 승인 건은 EXPIRED 처리 (프론트·서버 동일 규칙)
- 컴포넌트 분할: `RunControls`(실행 툴바) / `KpiStrip`(현황 타일 3종) / `RiskTrend`(추이 차트) /
  `ArchitectureView`(파이프라인) / `LineFlow`(Etch 라인 플로우) / `ActionQueue`(재조정 제안 큐) /
  `LogTimeline`(이벤트 스트림) / `ReportDrawer`(최종 리포트 드로어) / `NotificationCenter`(벨+패널) /
  `ToastStack` / `ApprovalModal` / 단계 10에서 `SensorPanel` 추가
- composable: `useEventStream`(SSE 수신·상태머신) / `useRunControl`(/run 트리거) /
  `useNotifications`(알림·HITL) / `useFactorySnapshot`(읽기 전용 /api 현황 집계)

## API

| 엔드포인트 | 역할 |
|---|---|
| `GET /` | `frontend/dist` 정적 서빙 (빌드 산출물) |
| `POST /run` | `{mode, asof, query}` 실행 트리거 (실행 중이면 409) |
| `GET /events` | SSE 스트림 (text/event-stream) |
| `GET /health` | 상태 확인 |

## 스코프 가드

- 인증·다중 사용자·실행 이력 저장 없음 (단일 실행 관찰용)
- 차트 **라이브러리** 금지 — 필요한 시각화(추이 라인·부하 바)는 수제 SVG/CSS로만 구현한다
- 대시보드가 죽어도 CLI 실행은 독립적으로 동작해야 한다
