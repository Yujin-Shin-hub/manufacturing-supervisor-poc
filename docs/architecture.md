# architecture.md — Supervisor + Dispatching 에이전틱 구조

```
작성자 : 신유진
작성 목적 : Supervisor AI Service와 Dynamic Dispatching/Rescheduling Agent 구조 정의
```

## 설계 원칙

1. **역할 분리 3층**: 판단(LLM) / 계산(판다스 툴) / 조율(Supervisor 코드)
2. **라우팅은 1회 LLM 호출**로 결정하고, 결과는 구조화 출력(JSON)으로 강제한다
3. Worker는 서로를 호출하지 않는다. 조합이 필요하면 Supervisor가 순차 호출한다
4. 전공정 전체 Route 최적화가 아니라 **공정군 단위 dispatching/rescheduling**으로 범위를 제한한다

## 전체 흐름

```
사용자 요청 (질문 / 정기 리포트 트리거)
        │
        ▼
┌─ Supervisor ────────────────────────────────┐
│  1. 요청 접수, asof(기준시각) 확정          │
│  2. Routing Agent 호출 ──► {target_agents,  │
│     reason} JSON 수신                       │
│  3. 대상 Worker Agent(들) 순차 실행         │
│  4. 결과 취합 → 최종 응답/리포트 조립       │
└─────────────────────────────────────────────┘
        │ 실행 위임
        ▼
┌─ Worker Agents (역할별 전담) ───────────────┐
│ field_status   공정군 작업·설비 상태 요약   │
│ risk_alert     HIGH/CRITICAL 위험 알림       │
│ delay_pred     지연 위험·예상 지연 판단     │
│ dispatching    대체 설비·작업 순서 추천     │
│ report         Supervisor 운영 리포트 조립  │
└─────────────────────────────────────────────┘
        │ tool call (function calling)
        ▼
┌─ Tools (판다스, LLM 아님) ──────────────────┐
│ load_schedule / load_work_status            │
│ score_delay_risk / find_machine_candidates  │
│ build_reschedule_actions / summarize_status │
└─────────────────────────────────────────────┘
        │
        ▼
      data/ (canonical CSV 5종)
```

Canonical CSV는 `schedule_master`, `work_status`, `delay_risk`, `reschedule_action`,
`machine_process_map`이다.

## Routing Agent 동작

- 입력: 사용자 요청 원문 + 에이전트 카탈로그(이름·책임·전형 질문 예시)
- 출력(구조화 JSON, pydantic 검증):

```json
{
  "target_agents": ["delay_pred", "dispatching"],
  "execution_order": "sequential",
  "reason": "지연 위험과 대체 설비/순서 조정을 함께 묻고 있음"
}
```

- 매칭 실패 시 `target_agents: ["field_status"]`로 폴백하고 reason에 폴백 사유 기록
- 라우팅 판단 기준 상세는 `docs/agents.md`의 라우팅 표 참고

## 목표 디렉토리 구조

```
src/
├── main.py          # CLI 진입점 (--mode report|ask)
├── supervisor.py    # 조율 로직 (라우팅 호출, worker 실행, 취합)
├── router.py        # Routing Agent (LLM 1회 호출 + 스키마 검증)
├── llm.py           # LLM 클라이언트 래퍼 — Qwen, OpenAI 호환 API (모델명·재시도·structured output)
├── events.py        # EventBus — 실행 이벤트 발행 (콘솔 로거·SSE가 공동 구독)
├── server.py        # FastAPI — 대시보드 서빙 + SSE (docs/dashboard.md 참고)
├── schemas.py       # pydantic: RoutingDecision, AgentResult, Report 등
├── agents/
│   ├── base.py      # Worker 공통 인터페이스 (run(asof, query) -> AgentResult)
│   ├── field_status.py
│   ├── risk_alert.py
│   ├── delay_pred.py
│   ├── dispatching.py
│   └── report.py
└── tools/
    ├── loader.py    # 데이터 접근 계층 — 모든 CSV/DB 읽기는 여기만 거친다
    ├── risk.py      # risk_score/risk_level 계산 또는 조회
    ├── dispatching.py # 설비 후보 탐색·액션 생성
    └── formatting.py# df → markdown 표 (프로토타입의 df_to_markdown 이식)
frontend/            # Vite + Vue 3 + TypeScript SPA (빌드: npm run build → dist/)
├── src/
│   ├── App.vue
│   ├── components/  # RunControls, ArchitectureView, LogTimeline, ReportPanel
│   ├── composables/ # useEventStream(SSE·상태머신), useRunControl
│   └── types/       # 이벤트·상태 타입 (api-spec.md 2장과 1:1)
└── vite.config.ts   # dev proxy → localhost:8000
```

## 왜 이 구조인가 (설계 근거)

- **선택 실행**: 모든 에이전트를 항상 실행하지 않고, 라우팅 결과에 따라 필요한
  Worker만 실행해 토큰·응답시간을 절감한다
- **명시적 컨텍스트 전달**: Worker 간 데이터는 `AgentResult` 스키마로만 오가며,
  암묵적 공유 상태를 두지 않는다 (디버깅·테스트 용이)
- **오케스트레이션 직접 구현**: 라우팅·조율의 제어 흐름을 직접 작성해
  에이전트 시스템의 동작 원리를 코드로 증명한다
- **설비 후보 근거 명시**: 대체 설비는 단순히 부하가 낮은 설비가 아니라
  `machine_process_map`에서 해당 `process_step`을 처리할 수 있는 설비로 제한한다

## 실행 관측 (Observability)

Supervisor와 Worker는 모든 진행 상황을 `events.py`의 EventBus로 발행한다.
같은 이벤트 스트림을 CLI 콘솔 로거와 대시보드 SSE가 함께 구독하므로,
로그와 UI가 항상 동일한 사실을 보여준다. 상세는 `docs/dashboard.md`.

## 확장 여지 (문서만, 구현 약속 아님)

- 정기 실행: `--mode report`를 스케줄러(cron)에 연결
- 예측 강화: 실제 MES/EAP 이력 기반 risk_score 모델 삽입
- 제약 강화: recipe qualification, setup time, queue time 제한 추가
