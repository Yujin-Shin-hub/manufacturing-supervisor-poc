# conventions.md — 코드·문서 컨벤션

```
작성자 : 신유진
작성 목적 : 이 레포의 코드 스타일과 기록 규칙 (기존 개인 레포 컨벤션 계승)
```

## Python

- Python 3.11+, 타입 힌트 필수, 입력값 검증 포함
- 파일 머리말 필수:

```python
"""
작성자  : 신유진
작성일  : YYYY-MM-DD
작성 목적: (이 파일의 책임 한 줄)
변경 이력:
  - YYYY-MM-DD: (변경 내용)
"""
```

- 함수는 단일 책임, 주요 함수에 한 줄 docstring
- **데이터 접근은 반드시 `src/tools/loader.py` 경유** — 툴·에이전트가 CSV/DB를
  직접 열지 않는다. 저장소 교체(CSV→SQLite)가 loader 내부 수정만으로 가능해야 한다
- 환경변수는 하드코딩 금지, `python-dotenv`로 `.env` 로드
- 기본 의존성: openai, pydantic, pandas, python-dotenv.
  필요한 라이브러리는 자유롭게 추가하되 `docs/roadmap.md`에 선택 사유를 한 줄 기록

### 함수 주석

Python Google-style Docstring
```python
def select_top_k_chunks(query: str, top_k: int = 5, *, acl: AclFilter) -> list[Chunk]:
    """ACL이 적용된 Hybrid Search를 수행하여 Top-K 청크를 반환한다.

    Args:
        query: 사용자의 자연어 질의 또는 Query Rewriter가 확장한 쿼리.
        top_k: 반환할 청크 수. 기본값 5.
        acl: ACL Pre-filter. allowed_groups, allowed_users 정보를 포함한다.

    Returns:
        관련도 점수 기준으로 내림차순 정렬된 Top-K 청크 리스트.

    Raises:
        QdrantConnectionError: Qdrant 호출 실패 시.
    """
    ...
```

## LLM 호출 (Qwen/OpenAI)

- 모든 호출은 `src/llm.py` 래퍼 경유 (모델명·temperature·재시도 한 곳 관리)
- provider 선택은 `LLM_PROVIDER` 환경변수 또는 `POST /run.llm_provider`로만 한다.
  허용값은 `auto`, `qwen`, `openai`이며 기본값은 `auto`다.
- `auto`는 Qwen을 먼저 호출하고 실패 시 OpenAI로 fallback한다. fallback이 발생하면 이벤트/로그에 남긴다.
- Qwen은 OpenAI 호환 API로 호출한다 — openai SDK에 `base_url`만 교체:
  - 기본: **로컬 Ollama (오픈소스, 키 불필요)** — `http://localhost:11434/v1`, `qwen2.5:7b`
  - 대안: DashScope 클라우드 API (`QWEN_API_KEY` 발급 필요)
  - 코드는 환경변수만 읽으므로 두 방식 전환에 코드 수정이 없어야 한다
- OpenAI API 사용 시 `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL_NAME`을 환경변수로 읽는다.
  API key는 요청 payload, 로그, SSE 이벤트에 절대 포함하지 않는다.
- structured output 필수 — 자유 텍스트 응답을 파싱하는 코드 작성 금지.
  단, Qwen은 `json_schema` strict 모드 지원이 모델·엔드포인트별로 다르므로
  `json_object` 모드 + pydantic 검증 + 실패 시 1회 재요청을 기본 패턴으로 한다
- 프롬프트 문자열은 각 agent 파일 상단에 상수로 두고, f-string 조립은 함수 안에서만

## Frontend (frontend/, Vue 3 + TypeScript)

- 이벤트·상태 타입은 `types/`에 정의하고 `docs/api-spec.md` 2장과 1:1로 유지한다
  (스펙 변경 없이 타입만 바꾸는 것 금지)
- SSE 수신·상태 전이는 `useEventStream` composable에만 둔다 — 컴포넌트에서 EventSource 직접 생성 금지
- 수치 표시 반올림은 프론트에서만 한다 (자릿수는 api-spec.md 3-1 표 기준)
- 스타일은 컴포넌트 scoped CSS. UI 라이브러리·차트 라이브러리 추가 금지 (스코프 가드)

### 함수 주석

Java Javadoc
```java
/**
 * 사용자의 자연어 질문을 받아 RAG 파이프라인에 위임하고, 결과를 SSE 스트림으로 반환한다.
 *
 * @param request 사용자 질문 및 대화 컨텍스트 정보
 * @param user 인증된 사용자 정보
 * @return SseEmitter — 답변 토큰, 인용 출처, 검증 결과를 순차 전송
 * @throws BizException SSE 연결 수립 실패 또는 ML Pipeline 호출 실패 시
 */
public SseEmitter streamAnswer(ChatRequest request, LinaUserPrincipal user) {
    ...
}
```


## 테스트

- tool 함수(리스크 조회·설비 후보 탐색·액션 생성)는 LLM 없이 테스트 가능해야 한다 → `tests/test_tools.py`
- LLM 의존 테스트는 별도 파일로 분리하고 기본 실행에서 제외 (비용)
- 데모 검증은 HIGH/CRITICAL risk schedule과 `machine_process_map` 기반 대체 설비 추천 케이스로 수행

## 문서·커밋

- 단계 완료마다 `process.md`에 기록: 산출물 / 핵심 설계 결정 / 필요 지식 정리 3절 구성
- README의 구현 상태 표는 `docs/roadmap.md`와 항상 일치시킨다
- 커밋 메시지: `[단계N] 요약` 형식 (예: `[단계1] 감지 로직 src/tools 이식`)
- 구현 안 된 기능을 완료형으로 서술하지 않는다 (PoC 정직성 원칙)

## 보안

- `.env`는 절대 커밋하지 않는다 (.gitignore 확인)
- 노트북 재실행 후 커밋 전, 출력 셀에 키·토큰이 찍히지 않았는지 확인
- 과거 키 유출 이력이 있으므로 커밋 전 `git diff`에서 `sk-` 문자열 검색을 습관화
