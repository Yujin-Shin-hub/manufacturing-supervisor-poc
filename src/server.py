"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: FastAPI 서버 — 대시보드 서빙 + SSE(/events) + 실행(/run)
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 7)
  - 2026-07-07: 단계 7 FastAPI /run, /events, /health, 읽기 전용 /api 조회 구현
  - 2026-07-07: 단계 8 대시보드 HITL — 액션 승인/거절 API(api-spec 1-4)와
                in-memory ActionRegistry 추가 (repropose/escalate는 계약만 유지)
  - 2026-07-14: GET /api/risk-summary 추가 — KPI가 risk_alert Worker와 같은
                score_delay_risk(asof) 집계를 쓰도록 (대시보드-리포트 수치 정합, api-spec 1-3)

"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from src.events import EventBus, EventRecord
from src.main import DEFAULT_ASOF
from src.sensors.subscriber import MqttSensorSubscriber, mqtt_enabled
from src.schemas import StrictModel
from src.supervisor import Supervisor
from src.tools.loader import (
    load_delay_risk,
    load_machine_process_map,
    load_reschedule_action,
    load_schedule,
    load_work_status,
)
from src.tools.risk import score_delay_risk


class RunRequest(StrictModel):
    """POST /run 요청 payload."""

    mode: Literal["ask", "report"]
    asof: str | None = None
    query: str | None = None
    llm_provider: Literal["auto", "qwen", "openai"] | None = None


RejectReason = Literal[
    "machine_reserved",
    "operator_unavailable",
    "recipe_not_ready",
    "quality_risk",
    "setup_time_too_long",
    "priority_changed",
    "manual_override",
    "other",
]


class ActionAcceptRequest(StrictModel):
    """POST /api/actions/{action_id}/accept 요청 payload (api-spec 1-4)."""

    supervisor_id: str
    comment: str | None = None


class ActionRejectRequest(StrictModel):
    """POST /api/actions/{action_id}/reject 요청 payload (api-spec 1-4)."""

    supervisor_id: str
    reject_reason: RejectReason
    comment: str | None = None


class RunState:
    """단일 Supervisor 실행 상태를 관리한다.

    이 PoC는 실행 이력/큐를 두지 않고 한 번에 하나의 run만 관찰한다.
    따라서 running flag와 asyncio.Lock으로 동시 /run 요청을 의도적으로 409 처리한다.
    """

    def __init__(self) -> None:
        """초기 실행 상태와 동시성 제어용 lock을 생성한다.

        Returns:
            None.
        """
        self.running: bool = False
        self.lock: asyncio.Lock = asyncio.Lock()


class ActionRegistry:
    """action_proposed 이벤트로 수집한 승인 대기 액션의 in-memory 저장소.

    이력 저장 없음(스코프 가드) — 승인 workflow 상태만 세션 메모리에 유지한다.
    Supervisor는 worker thread에서 이벤트를 발행하고 승인/거절 API는 FastAPI
    threadpool에서 호출되므로 threading.Lock으로 상태 전이를 직렬화한다.
    """

    def __init__(self) -> None:
        """빈 레지스트리와 동시성 제어용 lock을 생성한다.

        Returns:
            None.
        """
        self._actions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def track(self, event: EventRecord) -> None:
        """EventBus 구독자 — 제안 이벤트를 수집하고 새 run 시작 시 이전 제안을 만료한다.

        Args:
            event: EventBus가 발행한 이벤트 레코드.

        Returns:
            None.
        """
        with self._lock:
            if event.event == "run_start":
                # 기준시각이 바뀌면 이전 run의 제안은 더 이상 유효하지 않다 (api-spec 1-4 EXPIRED)
                for action in self._actions.values():
                    if action["action_status"] == "PENDING":
                        action["action_status"] = "EXPIRED"
            elif event.event == "action_proposed":
                data = event.data
                self._actions[str(data["action_id"])] = {
                    "action_id": data["action_id"],
                    "schedule_id": data["schedule_id"],
                    "risk_level": data["risk_level"],
                    "alternative_machine": data["alternative_machine"],
                    "action_status": "PENDING",
                }

    def decide(self, action_id: str, new_status: Literal["ACCEPTED", "REJECTED"]) -> dict[str, Any]:
        """PENDING 액션을 승인/거절 상태로 전이하고 액션 정보를 반환한다.

        Args:
            action_id: 전이 대상 action_id.
            new_status: 전이할 상태 (ACCEPTED 또는 REJECTED).

        Returns:
            전이 완료된 액션 정보 딕셔너리의 복사본.

        Raises:
            HTTPException: action_id가 없으면 404, 이미 응답됐거나 만료된 액션이면 409.
        """
        with self._lock:
            action = self._actions.get(action_id)
            if action is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"unknown action_id: {action_id}",
                )
            if action["action_status"] != "PENDING":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"action already {action['action_status']}",
                )
            action["action_status"] = new_status
            return dict(action)


app: FastAPI = FastAPI(title="Manufacturing Supervisor PoC")
event_bus: EventBus = EventBus()
run_state: RunState = RunState()
action_registry: ActionRegistry = ActionRegistry()
event_bus.subscribe(action_registry.track)
sensor_subscriber: MqttSensorSubscriber | None = None

FRONTEND_DIST: Path = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )


@app.on_event("startup")
def startup_mqtt_subscriber() -> None:
    """MQTT_ENABLED=true이면 Mosquitto 센서 topic 구독을 시작한다."""
    global sensor_subscriber
    if not mqtt_enabled():
        return
    sensor_subscriber = MqttSensorSubscriber(event_bus=event_bus)
    sensor_subscriber.start()


@app.on_event("shutdown")
def shutdown_mqtt_subscriber() -> None:
    """서버 종료 시 MQTT loop를 정리한다."""
    if sensor_subscriber is not None:
        sensor_subscriber.stop()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """대시보드 index HTML 또는 서버 상태 안내 HTML을 반환한다.

    Returns:
        `frontend/dist/index.html`이 있으면 해당 HTML 응답을 반환하고,
        아직 프론트 빌드가 없으면 API 사용 가능 상태를 안내하는 HTML 응답을 반환한다.
    """
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    return HTMLResponse(
        "<!doctype html><html><body>"
        "<h1>Manufacturing Supervisor API</h1>"
        "<p>frontend/dist is not built yet. Use /health, /run, /events, /api/*.</p>"
        "</body></html>"
    )


@app.get("/health")
def health() -> dict[str, str]:
    """FastAPI 서버 상태를 확인한다.

    Returns:
        서버가 응답 가능한 상태임을 나타내는 `{"status": "ok"}` 딕셔너리.
    """
    return {"status": "ok"}


@app.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_supervisor(payload: RunRequest) -> dict[str, str]:
    """Supervisor 실행을 백그라운드 태스크로 시작한다.

    Args:
        payload: 실행 모드, 기준시각, 질문, LLM provider 선택값을 담은 `/run` 요청 payload.

    Returns:
        실행 요청이 수리됐음을 나타내는 `{"status": "started"}` 딕셔너리.

    Raises:
        HTTPException: ask mode에서 query가 비어 있거나, 이미 다른 run이 실행 중일 때.
    """
    if payload.mode == "ask" and not (payload.query or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="query is required when mode='ask'",
        )

    async with run_state.lock:
        # 상태 확인과 running=True 변경은 하나의 임계 구역으로 묶는다.
        # 동시에 들어온 /run 요청 2개가 둘 다 실행을 시작하지 못하게 하기 위한 의도적 제한이다.
        if run_state.running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="run in progress",
            )
        run_state.running = True

    asyncio.create_task(_run_in_background(payload))
    return {"status": "started"}


async def _run_in_background(payload: RunRequest) -> None:
    """Supervisor를 worker thread에서 실행하고 실행 상태를 해제한다.

    Args:
        payload: `/run`에서 검증된 Supervisor 실행 요청 payload.

    Returns:
        None.
    """
    try:
        await asyncio.to_thread(
            Supervisor(event_bus=event_bus).run,
            payload.mode,
            payload.asof or DEFAULT_ASOF,
            payload.query,
            payload.llm_provider,
        )
    finally:
        async with run_state.lock:
            run_state.running = False


@app.get("/events")
async def events(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    """EventBus 이벤트를 SSE `text/event-stream` 응답으로 전달한다.

    Args:
        request: 클라이언트 연결 상태를 확인하기 위한 FastAPI request 객체.
        last_event_id: SSE 재연결 시 클라이언트가 마지막으로 받은 event id.

    Returns:
        EventBus buffer replay와 신규 이벤트를 흘려보내는 SSE 응답 객체.
    """
    replay_after_seq = _parse_last_event_id(last_event_id)

    async def generator() -> AsyncIterator[dict[str, str]]:
        """EventBus replay와 신규 이벤트를 SSE frame으로 순차 생성한다.

        Yields:
            sse-starlette가 직렬화할 `id`, `event`, `data` 필드를 가진 SSE frame 딕셔너리.
        """
        queue: asyncio.Queue[EventRecord] = asyncio.Queue()
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        def subscriber(event: EventRecord) -> None:
            """EventBus 이벤트를 현재 event loop의 queue로 전달한다.

            Args:
                event: Supervisor 실행 중 EventBus가 발행한 이벤트 레코드.

            Returns:
                None.
            """
            loop.call_soon_threadsafe(queue.put_nowait, event)

        unsubscribe = event_bus.subscribe(
            subscriber,
            replay_after_seq=replay_after_seq,
        )
        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                yield _sse_frame(event)
        finally:
            unsubscribe()

    return EventSourceResponse(generator())


def _parse_last_event_id(last_event_id: str | None) -> int | None:
    """`Last-Event-ID` 헤더를 EventBus replay 기준 seq로 변환한다.

    Args:
        last_event_id: SSE 클라이언트가 전달한 마지막 event id 문자열.

    Returns:
        유효한 정수 id면 해당 값, 비어 있거나 잘못된 값이면 0.
    """
    if last_event_id is None or not str(last_event_id).strip():
        return 0
    try:
        return int(last_event_id)
    except ValueError:
        return 0


def _sse_frame(event: EventRecord) -> dict[str, str]:
    """EventRecord를 sse-starlette용 SSE frame 딕셔너리로 변환한다.

    Args:
        event: EventBus가 발행한 이벤트 레코드.

    Returns:
        `id`, `event`, `data` 문자열 필드를 가진 SSE frame 딕셔너리.
    """
    return {
        "id": str(event.seq),
        "event": event.event,
        "data": json.dumps(event.data, ensure_ascii=False),
    }


@app.get("/api/schedules")
def api_schedules(
    status: str | None = None,
    process_step: str | None = None,
) -> dict[str, object]:
    """`schedule_master` 데이터를 조회한다.

    Args:
        status: 원본 `status` 컬럼 기준 선택 필터.
        process_step: 원본 `process_step` 컬럼 기준 선택 필터.

    Returns:
        `{"asof": ..., "rows": [...]}` 형태의 schedule 조회 응답.
    """
    df = _filter(load_schedule(), status=status, process_step=process_step)
    df = df.sort_values(["priority"], ascending=[True])
    return _rows(df)


@app.get("/api/work-status")
def api_work_status(
    machine_id: str | None = None,
    schedule_id: str | None = None,
) -> dict[str, object]:
    """`work_status` 데이터를 조회한다.

    Args:
        machine_id: 원본 `machine_id` 컬럼 기준 선택 필터.
        schedule_id: 원본 `schedule_id` 컬럼 기준 선택 필터.

    Returns:
        `{"asof": ..., "rows": [...]}` 형태의 work status 조회 응답.
    """
    df = _filter(load_work_status(), machine_id=machine_id, schedule_id=schedule_id)
    return _rows(df)


@app.get("/api/risks")
def api_risks(
    risk_level: str | None = None,
    schedule_id: str | None = None,
) -> dict[str, object]:
    """`delay_risk` 데이터를 risk_score 내림차순으로 조회한다.

    Args:
        risk_level: 원본 `risk_level` 컬럼 기준 선택 필터.
        schedule_id: 원본 `schedule_id` 컬럼 기준 선택 필터.

    Returns:
        `{"asof": ..., "rows": [...]}` 형태의 risk 조회 응답.
    """
    df = _filter(load_delay_risk(), risk_level=risk_level, schedule_id=schedule_id)
    df = df.sort_values(["risk_score"], ascending=[False])
    return _rows(df)


@app.get("/api/risk-summary")
def api_risk_summary(asof: str | None = None) -> dict[str, object]:
    """asof 기준 납기 위험(HIGH/CRITICAL) 집계를 조회한다 (api-spec 1-3).

    risk_alert Worker와 동일한 `score_delay_risk(asof)` tool 결과를 세기만 한다 —
    대시보드 KPI와 리포트가 같은 숫자를 쓰게 하기 위한 엔드포인트다 (수치 정합).

    Args:
        asof: 집계 기준시각 문자열. 생략 시 서버 기본 기준시각.

    Returns:
        `{"asof": ..., "total": ..., "critical": ..., "high": ...}` 집계 딕셔너리.

    Raises:
        HTTPException: asof가 datetime으로 해석되지 않을 때 400.
    """
    effective_asof = asof or DEFAULT_ASOF
    try:
        df = score_delay_risk(effective_asof)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid asof: {effective_asof}",
        ) from exc
    return {
        "asof": effective_asof,
        "total": int(len(df)),
        "critical": int((df["risk_level"] == "CRITICAL").sum()),
        "high": int((df["risk_level"] == "HIGH").sum()),
    }


@app.get("/api/machines")
def api_machines(
    process_step: str | None = None,
    available_yn: str | None = None,
    qualified_yn: str | None = None,
) -> dict[str, object]:
    """`machine_process_map` 데이터를 조회한다.

    Args:
        process_step: 원본 `process_step` 컬럼 기준 선택 필터.
        available_yn: 원본 `available_yn` 컬럼 기준 선택 필터.
        qualified_yn: 원본 `qualified_yn` 컬럼 기준 선택 필터.

    Returns:
        `{"asof": ..., "rows": [...]}` 형태의 machine map 조회 응답.
    """
    df = _filter(
        load_machine_process_map(),
        process_step=process_step,
        available_yn=available_yn,
        qualified_yn=qualified_yn,
    )
    return _rows(df)


@app.get("/api/actions")
def api_actions(
    applied_yn: str | None = None,
    schedule_id: str | None = None,
) -> dict[str, object]:
    """`reschedule_action` 데이터를 action_time 내림차순으로 조회한다.

    Args:
        applied_yn: 원본 `applied_yn` 컬럼 기준 선택 필터.
        schedule_id: 원본 `schedule_id` 컬럼 기준 선택 필터.

    Returns:
        `{"asof": ..., "rows": [...]}` 형태의 action 조회 응답.
    """
    df = _filter(load_reschedule_action(), applied_yn=applied_yn, schedule_id=schedule_id)
    df = df.sort_values(["action_time"], ascending=[False])
    return _rows(df)


@app.post("/api/actions/{action_id}/accept")
def accept_action(action_id: str, payload: ActionAcceptRequest) -> dict[str, object]:
    """재조정 액션을 승인하고 SSE `action_accepted` 이벤트를 발행한다 (api-spec 1-4).

    Args:
        action_id: 승인 대상 action_id.
        payload: supervisor 식별자와 선택 코멘트.

    Returns:
        승인 결과 (`action_status="ACCEPTED"`, `applied_yn="Y"`, 결정 시각 포함).

    Raises:
        HTTPException: action_id가 없거나 이미 응답/만료된 액션일 때.
    """
    action = action_registry.decide(action_id, "ACCEPTED")
    event_bus.publish(
        "action_accepted",
        action_id=action["action_id"],
        schedule_id=action["schedule_id"],
        supervisor_id=payload.supervisor_id,
    )
    return {
        "action_id": action["action_id"],
        "schedule_id": action["schedule_id"],
        "action_status": "ACCEPTED",
        "applied_yn": "Y",
        "decision_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@app.post("/api/actions/{action_id}/reject")
def reject_action(action_id: str, payload: ActionRejectRequest) -> dict[str, object]:
    """재조정 액션을 거절하고 SSE `action_rejected` 이벤트를 발행한다 (api-spec 1-4).

    repropose API(1-4 재추천)는 아직 계약만 정의된 상태이므로
    `reproposal_available`은 항상 False로 응답한다.

    Args:
        action_id: 거절 대상 action_id.
        payload: supervisor 식별자, 거절 사유, 선택 코멘트.

    Returns:
        거절 결과 (`action_status="REJECTED"`, 거절 사유 포함).

    Raises:
        HTTPException: action_id가 없거나 이미 응답/만료된 액션일 때.
    """
    action = action_registry.decide(action_id, "REJECTED")
    event_bus.publish(
        "action_rejected",
        action_id=action["action_id"],
        schedule_id=action["schedule_id"],
        reject_reason=payload.reject_reason,
        reproposal_available=False,
    )
    return {
        "action_id": action["action_id"],
        "schedule_id": action["schedule_id"],
        "action_status": "REJECTED",
        "reject_reason": payload.reject_reason,
        "reproposal_available": False,
    }


def _filter(df: pd.DataFrame, **filters: str | None) -> pd.DataFrame:
    """원본 컬럼명과 동일한 필터만 적용해 DataFrame을 반환한다.

    Args:
        df: 필터링 대상 DataFrame.
        **filters: 컬럼명과 필터값 매핑. 값이 None인 필터는 무시한다.

    Returns:
        필터가 적용되고 index가 재정렬된 DataFrame.

    Raises:
        HTTPException: 필터 컬럼이 DataFrame에 존재하지 않을 때.
    """
    result = df.copy()
    for column, value in filters.items():
        if value is None:
            continue
        if column not in result.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown filter column: {column}",
            )
        result = result[result[column].astype(str) == value]
    return result.reset_index(drop=True)


def _rows(df: pd.DataFrame) -> dict[str, object]:
    """DataFrame을 api-spec의 공통 조회 응답 형태로 변환한다.

    Args:
        df: API 응답으로 직렬화할 DataFrame.

    Returns:
        기준시각과 row 목록을 포함한 `{"asof": ..., "rows": [...]}` 딕셔너리.
    """
    records = (
        df.astype(object)
        .where(pd.notna(df), None)
        .to_dict(orient="records")
    )
    return {"asof": DEFAULT_ASOF, "rows": records}
