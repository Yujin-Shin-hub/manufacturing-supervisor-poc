# CLAUDE.md

```
작성자 : 신유진
작성 목적 : Claude Code가 이 레포에서 작업할 때 따라야 할 기준 문서 (인덱스)
프로젝트 : 제조 생산 모니터링 Supervisor PoC — 에이전틱 AI 시스템
```

## 프로젝트 한 줄 요약

이벤트 로그 기반 룰 감지(판다스) 위에, **Supervisor → Routing Agent → 역할별 Worker Agent**
구조의 에이전틱 시스템을 구현한다.
LLM은 판단·라우팅·문구 생성만 담당하고, 모든 수치는 코드가 계산한다.

## 문서 맵 (작업 전 반드시 해당 문서를 먼저 읽을 것)

| 문서 | 내용 | 언제 읽나 |
|---|---|---|
| `docs/architecture.md` | Supervisor-Routing 구조, 데이터 흐름, 목표 디렉토리 구조 | 구조 관련 모든 작업 전 |
| `docs/agents.md` | 에이전트별 역할·입출력 계약·라우팅 규칙·프롬프트 원칙 | 에이전트 구현/수정 전 |
| `docs/roadmap.md` | 단계별 구현 플랜과 현재 상태 | 어떤 작업이 다음 순서인지 확인 |
| `docs/dashboard.md` | 실행 과정 시각화 대시보드 (SSE 이벤트·화면 설계) | 대시보드/이벤트 관련 작업 전 |
| `docs/sensor-stream.md` | MQTT 실시간 센서 스트림·자동 트리거 설계 | 센서/MQTT 관련 작업 전 |
| `docs/api-spec.md` | REST·SSE API 계약, 이벤트 상태 정의, 수치 정밀도 규칙 | 서버/대시보드/스키마 작업 전 |
| `docs/conventions.md` | 코드 스타일, 파일 머리말, 환경변수, 기록 규칙 | 코드 작성 전 |
| `docs/troubleshooting.md` | 설계 판단 근거·문제 해결 기록 (면접 대비 원본) | 주요 설계 결정·이슈 해결 후 기록 |
| `data/README_dataset.txt` | 합성 데이터셋 7종 명세, 내장 이상상황 시나리오 | 데이터 다루기 전 |
| `notebooks/` | 초기 프로토타입 (감지 로직의 원본. 참조용, 수정 금지) | 로직 이식 시 |

## 절대 규칙

1. **API 키를 코드에 하드코딩하지 않는다.** `os.getenv` + `.env`만 사용.
   과거 이 프로젝트에서 키 유출 사고가 있었다. 어떤 예시 코드에도 키 문자열을 쓰지 않는다.
   LLM은 Qwen을 사용한다 (접속 정보는 `docs/conventions.md`의 LLM 호출 절 참고).
2. **수치는 LLM이 만들지 않는다.** 지연 시간, 리스크 점수, 수량 등 모든 숫자는
   `src/tools/`의 판다스 함수가 계산하고, LLM은 그 결과를 해석·서술만 한다.
3. **라이브러리는 자유롭게 쓰되, 추가 시 `docs/roadmap.md`에 선택 사유를 기록한다.**
   단, Supervisor-Routing 오케스트레이션의 핵심 제어 흐름은 프레임워크에 맡기지 않고
   직접 구현한다 (이 프로젝트의 증명 포인트이기 때문).
4. **노트북(`notebooks/`)은 수정하지 않는다.** 프로토타입은 비교·증빙용으로 보존한다.
5. **PoC 정직성 유지.** README나 문서에 구현 안 된 기능을 완료형으로 쓰지 않는다.
   상태는 ✅/🚧/⬜ 표로 표기한다.

## 작업 기록 규칙

- 단계가 끝날 때마다 `process.md`에 산출물·설계 결정·필요 지식을 기록한다
  (기존 planning-multi-agent 레포의 process.md 형식을 따른다).
- 코드 파일 변경 시 머리말에 변경일·변경사항을 추가한다.

## 빠른 시작 (구현 완료 후 기준)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m src.main --mode report --asof "2026-01-15 14:00"
python -m src.main --mode ask --q "지금 어느 공정이 제일 위험해?"
uvicorn src.server:app --reload   # 대시보드: http://localhost:8000
```
