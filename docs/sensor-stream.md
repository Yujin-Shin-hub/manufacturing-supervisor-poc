# sensor-stream.md — MQTT 실시간 센서 스트림

```
작성자 : 신유진
작성 목적 : 가상 센서 → MQTT → 대시보드/에이전트 자동 트리거로 이어지는 실시간 데이터 계층 설계
전제 : roadmap 단계 9까지 완료 후 착수 (단계 10~11)
```

## 목적

1. 실제 스마트팩토리의 데이터 수집 구조(센서 계층과 서비스 계층의 브로커 분리)를 축소판으로 재현한다
2. 센서 이상 감지 시 사람 개입 없이 Supervisor 파이프라인이 자동 실행되는
   "모니터링 → 자율 대응" 흐름을 완성한다

## 아키텍처

```
sensor_sim.py          Mosquitto           FastAPI(server.py)
(별도 프로세스)          (MQTT 브로커)
  라인별 센서값 생성 ──publish──► topic ──subscribe──► subscriber.py
  1초 주기, 이상주입                                      │
                                              rules.py (임계치 판정, 코드가 판단)
                                                │               │
                                          EventBus(sensor_*)   자동 트리거
                                                │               │
                                          SSE → 대시보드    Supervisor 실행
                                                            (run_start mode:"auto")
```

- 시뮬레이터와 서버는 **반드시 별도 프로세스** — 브로커를 사이에 둔 분리가 이 설계의 핵심 증명 포인트
- 브로커: Mosquitto (오픈소스, 로컬 설치). 시뮬레이터·구독자 모두 `paho-mqtt` 사용
- 접속 정보는 환경변수: `MQTT_HOST`(기본 localhost), `MQTT_PORT`(기본 1883)

## 토픽 설계

```
factory/{line_id}/sensor/{sensor_type}
예) factory/line-2/sensor/temperature
```

| sensor_type | 단위 | 정상 범위 | 발행 주기 |
|---|---|---|---|
| temperature | °C | 60~80 | 1초 |
| vibration | mm/s | 0.5~2.8 | 1초 |
| throughput | ea/min | 라인별 상이 (line_capacity 기준) | 5초 |

- QoS 0, retain false (텔레메트리 표준 관행 — 유실보다 최신성 우선)
- 페이로드(JSON):

```json
{"ts": "2026-04-15T10:00:03", "line": "Line-2", "sensor": "temperature", "value": 87.3, "unit": "C"}
```

## 시뮬레이터 (`src/sensors/simulator.py`)

- 6개 라인 × 3종 센서를 정상 범위 내 랜덤워크로 생성
- **이상 주입 시나리오** (CLI 플래그로 선택, 데모 재현성 확보):

| 플래그 | 시나리오 | 기대 반응 |
|---|---|---|
| `--anomaly temp-drift` | Line-2 온도가 3분에 걸쳐 서서히 90°C 초과 | sensor_alert → 자동 트리거 |
| `--anomaly vib-spike` | Line-5 진동 급증 (설비 이상 모사) | sensor_alert → 자동 트리거 |
| `--anomaly throughput-drop` | Line-3 처리량 40% 급감 (정체 모사) | delay_pred 라우팅 확인용 |
| (없음) | 정상 운전 | 알림 0건 유지 확인용 |

## 구독·판정 (`src/sensors/subscriber.py`, `src/sensors/rules.py`)

- subscriber: `factory/#` 구독 → 페이로드 검증(pydantic) → `EventBus.emit(sensor_update)`
- rules: **판정은 전부 코드** (절대 규칙 2 준수 — LLM은 판단에 관여하지 않음)
  - 임계치 테이블: 센서별 상한/하한 (`rules.py`에 상수, 근거 주석 필수)
  - 알림 조건: 동일 라인·동일 센서가 **60초 내 3회 연속** 임계치 초과 → `sensor_alert`
  - 자동 트리거: sensor_alert 발생 시 Supervisor 실행
    (`mode: "auto"`, query는 고정 템플릿 — 예: "Line-2 온도 이상. 지연 위험과 재배치 필요성 평가")
  - **쿨다운: 라인당 5분** — 같은 이상으로 파이프라인이 반복 실행되는 루프 방지
  - 수동 실행 중이면 자동 트리거는 대기열이 아니라 **폐기** (최신 상태로 다시 판정하는 게 맞음)

## EventBus 추가 이벤트

```json
{"type": "sensor_update", "line": "Line-2", "sensor": "temperature", "value": 87.3}
{"type": "sensor_alert",  "line": "Line-2", "sensor": "temperature", "rule": "3연속 초과", "values": [86.1, 88.4, 90.2]}
{"type": "auto_run_triggered", "cause": "sensor_alert", "line": "Line-2", "query": "..."}
```

기존 대시보드는 이 이벤트를 그대로 구독한다.
화면에는 ④ 센서 패널(라인별 최신값 + 최근 60초 스파크라인, vanilla canvas)을 추가하고,
sensor_alert 발생 시 해당 라인 카드를 경고색으로 토글한다.
`run_start`의 `mode:"auto"`는 타임라인에 "자동 실행" 배지로 구분 표시한다.

## 스코프 가드

- 시계열 DB 없음 — 최근 60초만 메모리 유지 (이력 저장은 확장 여지로만 문서화)
- MQTT 인증/TLS 없음 (로컬 데모 한정, README에 한계로 명시)
- sensor_update는 SSE로 초당 20건 미만 — 성능 튜닝 불필요, 최적화 금지
- 자동 트리거 규칙은 데모용 단순 임계치임을 README에 명시 (예지보전 모델 아님)

## 설치 (Windows)

```bash
# Mosquitto: https://mosquitto.org/download/ 설치 후
net start mosquitto              # 또는 mosquitto -v (포그라운드)
pip install paho-mqtt
python -m src.sensors.simulator --anomaly temp-drift   # 별도 터미널
uvicorn src.server:app --reload
```

## 구현 기록

시뮬레이터의 구현 판단(랜덤워크 클램프, 이상 주입 패턴, 문제-해결 메모)은
`docs/sensor-simulator.md`에 따로 정리했다.

## 구현 상태 (2026-07-14)

- 단계 10 구현: `src/sensors/simulator.py`, `src/sensors/subscriber.py`, `src/sensors/rules.py`
- FastAPI 연동: `MQTT_ENABLED=true`일 때 서버 startup에서 `factory/#` subscriber 시작
- SSE 이벤트: `sensor_update`, `sensor_alert`
- 자동 Supervisor 실행(`auto_run_triggered`)과 쿨다운은 단계 11 범위로 남긴다
- 센서 패널 구현 (2026-07-15): `frontend/src/components/SensorPanel.vue` +
  `useSensorStream` composable — 라인 6개 카드 × 3종 센서 최신값 + 최근 60초 스파크라인
  (vanilla canvas), sensor_alert 시 카드 경고색 토글. 센서 이벤트 수신 시에만 전용 행이
  나타난다 (MQTT 비활성 데모 레이아웃 불변). sensor_update는 고빈도(≤18건/초)라
  이벤트 스트림 타임라인에서 제외하고 센서 패널만 갱신한다.
  알림센터·토스트는 라인·센서당 60초 스로틀 (지속 이상 시 rule이 ~3초마다 재발행하므로)
- E2E 검증 (2026-07-15): Mosquitto 서비스 + `--anomaly temp-drift` 시뮬레이터로
  Line-2 카드 경고 토글·critical 토스트·sensor_alert 타임라인 수신 확인
  (증빙: reports/dashboard-stage10-sensor-panel.png)
