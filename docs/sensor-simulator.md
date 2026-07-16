# sensor-simulator.md — 가상 센서 시뮬레이터 구현 기록

```
작성자 : 신유진
작성 목적 : 단계 10 MQTT 센서 시뮬레이터(src/sensors/simulator.py)를 왜 이렇게 만들었는지,
           구현하면서 실제로 걸렸던 문제와 해결 과정을 남긴다.
           설계 원본은 docs/sensor-stream.md, 이 문서는 그 구현 후기다.
```

## 왜 시뮬레이터가 별도 프로세스인가

처음에 가장 쉬운 길은 FastAPI 서버 안에서 asyncio 태스크로 가짜 센서값을 만들어
EventBus에 바로 넣는 것이었다. 그런데 그렇게 하면 이 단계에서 증명하려던 것,
즉 "센서 계층과 서비스 계층이 브로커를 사이에 두고 분리된다"는 구조 자체가 사라진다.
실제 팹에서 센서/PLC 쪽 장비와 상위 서비스는 같은 프로세스일 수가 없고,
그 사이에 MQTT 같은 경량 브로커가 들어간다.

그래서 구성은 프로세스 3개로 고정했다.

```
python -m src.sensors.simulator      Mosquitto(브로커)      uvicorn src.server:app
        (publish만 한다)      ◄──►    localhost:1883   ◄──►   (subscribe만 한다)
```

시뮬레이터는 서버가 죽어 있어도 계속 publish하고, 서버는 시뮬레이터가 없어도
그냥 조용할 뿐이다. 둘은 서로의 존재를 모른다. 이 분리 덕에 데모 중에
시뮬레이터만 껐다 켜서 "센서 유실 → 복구" 상황도 보여줄 수 있다.

## 데이터 생성 — 랜덤워크 + 클램프

6개 라인(Line-1 ~ Line-6) × 3종 센서를 1초 주기로 만든다.
값은 완전 랜덤이 아니라 **직전 값에서 조금씩 움직이는 랜덤워크**다.
완전 랜덤으로 하면 스파크라인이 노이즈 덩어리로 보여서
"센서값이 흘러간다"는 느낌이 전혀 안 난다.

```python
drift = random.uniform(-0.4, 0.4)
if sensor == "temperature":
    return min(78.5, max(61.5, current + drift))
```

여기서 클램프 범위가 임계치보다 **안쪽**인 것이 의도된 부분이다.

| 센서 | 임계치 (rules.py) | 정상 랜덤워크 클램프 | 여유 |
|---|---|---|---|
| temperature | 60 ~ 80 °C | 61.5 ~ 78.5 | ±1.5 |
| vibration | 0.5 ~ 2.8 mm/s | 0.7 ~ 2.5 | 0.2~0.3 |
| throughput | 35 이상 | 42 ~ 68 | 7 |

클램프를 임계치와 같은 값으로 두면 랜덤워크가 경계에 붙었을 때 드리프트 한 번에
임계를 살짝 넘는 일이 간헐적으로 생길 수 있다. 정상 운전 시나리오인데 알림이 뜨면
"알림 0건 유지 확인용" 시나리오가 성립하지 않는다. 그래서 정상 모드에서는
**구조적으로 임계를 넘을 수 없게** 처음부터 클램프를 임계 안쪽으로 잡았고,
이상 상황은 아래 주입 시나리오로만 만든다.

## 이상 주입 — 시나리오 3종

데모 재현성이 목적이라 이상은 랜덤 발생이 아니라 CLI 플래그로 주입한다.
`--anomaly` 없이 돌리면 영원히 정상이다.

```bash
python -m src.sensors.simulator --anomaly temp-drift
```

| 플래그 | 대상 | 구현 | 의도 |
|---|---|---|---|
| `temp-drift` | Line-2 온도 | 매 틱 +0.35°C, 92°C에서 캡 | 서서히 나빠지는 열화. 70→80 도달에 약 29초, 3연속 초과까지 약 32초 |
| `vib-spike` | Line-5 진동 | `tick % 6 ∈ {0,1,2}`일 때 3.6, 아니면 회복 | **정확히 3연속** 초과 후 정상 복귀 — 룰 경계 검증용 |
| `throughput-drop` | Line-3 처리량 | 매 틱 −0.7, 바닥 24 | 하한(35) 위반 케이스. 상한만 있는 게 아님을 보여준다 |

`vib-spike`의 `tick % 6` 패턴은 일부러 룰의 "3연속" 조건에 맞춘 것이다.
스파이크 3번 → alert 1번 → 회복(버킷 리셋) → 다시 3번 → alert...
가 반복되므로, "연속 3회를 채워야만 alert가 난다"는 룰 동작을
화면에서 주기적으로 확인할 수 있다. 스파이크가 2번에서 끊기는 패턴이었다면
alert가 절대 나지 않는다는 것도 같은 룰의 반대면 증명이 된다.

`temp-drift`의 92°C 캡은 값이 무한히 커지는 것을 막는 동시에,
대시보드 스파크라인에서 "상승 → 고점 유지" 모양이 나오게 한다.
캡 없이 계속 오르면 y축 스케일이 계속 늘어나서 스파크라인이 초반 상승분을 뭉개버린다.

## 페이로드와 토픽

```
topic:   factory/line-2/sensor/temperature      (QoS 0, retain false)
payload: {"ts": "2026-07-15T23:17:39", "line": "Line-2",
          "sensor": "temperature", "value": 87.3, "unit": "C"}
```

- 토픽의 라인은 소문자(`line-2`), 페이로드의 라인은 표시용 표기(`Line-2`)다.
  구독 쪽은 어차피 `factory/#` 와일드카드 하나로 받고 파싱은 페이로드로만 하므로
  토픽은 라우팅 역할만 한다.
- QoS 0 / retain false는 텔레메트리 관행을 따랐다. 1초마다 새 값이 오는데
  유실된 옛 값을 재전송받을 이유가 없고(유실보다 최신성),
  retain을 켜면 구독 시작 시점에 낡은 값이 최신인 척 들어온다.
- `ts`는 `datetime.now().replace(microsecond=0).isoformat()`.
  마이크로초를 지운 것은 구독 쪽 `rules.py`가 `datetime.fromisoformat()`으로
  그대로 파싱하고, 사람이 로그를 읽을 때도 초 단위면 충분하기 때문이다.
- 값은 publish 직전에 `round(value, 2)` 한 번만 한다. 내부 랜덤워크 상태는
  반올림하지 않은 float을 유지한다 (반올림 누적 오차 방지 — api-spec 3-3 규칙과 동일한 태도).

## 문제 — 해결 — 결과 메모

> 구현·검증 과정에서 troubleshooting

### 1. paho-mqtt 2.x에서 `mqtt.Client()` 시그니처가 바뀜

- **문제**: paho-mqtt 2.0부터 `Client()`를 인자 없이 만들면 deprecation 경고가 나오고,
  콜백(`on_connect` 등) 시그니처도 VERSION1/VERSION2가 다르다. 설치 환경에 따라
  1.x가 깔릴 수도 있어서 한쪽에 고정하면 다른 쪽에서 깨진다.
- **해결**: `mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)`를 먼저 시도하고
  `AttributeError/TypeError`면 구버전 방식으로 fallback. 콜백은 VERSION2 시그니처
  (`reason_code`, `properties=None`)로 맞추되 타입을 느슨하게 받았다.
- **결과**: venv의 paho-mqtt 2.1.0에서 경고 없이 동작. 1.x 환경에서도 같은 코드로 돈다.

### 2. 지속 이상에서 sensor_alert가 3초마다 재발행됨

- **문제**: `temp-drift`는 92°C 캡에 도달한 뒤 계속 임계 초과 상태다. 룰 엔진은
  alert를 내면 버킷을 비우는데, 그 다음 3틱(≈3초)이면 다시 3연속이 차서 alert가 또 나온다.
  E2E에서 몇 분 방치하니 sensor_alert가 수십 건 쌓였고, 토스트/알림센터가 그대로면
  알림 피로로 쓸 수 없는 화면이 된다.
- **해결**: 두 층으로 나눴다. 카드 경고색(상태 표시)은 매 alert마다 갱신하되,
  토스트·알림센터(사람 호출)는 프론트에서 **라인·센서당 60초 스로틀**.
  발행 자체를 줄이는 서버측 쿨다운(라인당 5분)은 자동 트리거와 묶여 있어
  설계 문서대로 단계 11로 넘겼다.
- **결과**: 지속 이상 중에도 벨 badge가 1~2건에 머무르고, 카드는 계속 경고 상태를 유지한다.
  이벤트 스트림 패널에는 alert 원문이 전부 남아서 "실제 발행 빈도"는 추적 가능하다.

### 3. sensor_update가 이벤트 스트림 타임라인을 밀어냄

- **문제**: 6라인 × 3센서 × 1초 = 초당 18건이 SSE로 온다. 기존 타임라인은 모든 이벤트를
  쌓는 구조라 몇 초 만에 라우팅/툴콜/리포트 이벤트가 화면 밖으로 밀려났다.
  페이지 새로고침 시에는 EventBus replay로 수천 건이 한 번에 재생돼 복귀가 눈에 띄게 느렸다.
- **해결**: `useEventStream`에서 `sensor_update`만 타임라인 수집에서 제외했다.
  센서값의 표시 계층은 센서 패널(최근 60초 메모리)이 전담하고,
  `sensor_alert`는 워크플로우 이벤트로 보고 타임라인에 남긴다.
- **결과**: 타임라인은 실행·승인·alert 이벤트만 보여주고, 센서 패널은 1초 단위로 갱신된다.
  스코프 가드("초당 20건 미만이므로 성능 튜닝 금지")를 지키면서 표시 계층만 분리한 것이라
  서버는 손대지 않았다.

### 4. Windows에서 Mosquitto 확인

- **문제**: 처음 E2E를 돌릴 때 브로커가 떠 있는지부터 불확실했다.
- **해결**: Mosquitto는 Windows 설치 시 서비스로 등록된다.
  `sc query mosquitto`로 RUNNING 확인, 안 떠 있으면 `net start mosquitto`.
  subscriber는 `connect_async` + 자동 재연결이라 브로커가 늦게 떠도 알아서 붙는다.
- **결과**: 이 프로젝트 데모 순서는 "브로커(서비스) → 서버(MQTT_ENABLED=true) → 시뮬레이터"
  인데, 사실 어느 순서로 띄워도 동작한다. 재연결이 다 흡수한다.

## 한계 (정직하게)

- 임계치와 3연속 룰은 데모용 단순 규칙이다. 예지보전 모델이 아니고,
  실장비의 센서 노이즈 특성(드리프트, 스파이크 분포)을 재현한 것도 아니다.
- 랜덤워크 파라미터(±0.4 드리프트 등)는 화면에서 보기 좋은 값으로 고른 것이지
  공정 물리에 근거한 값이 아니다.
- 시계열 저장이 없다. 브라우저·서버 모두 최근 60초만 유지하고 과거는 버린다.
- `--anomaly`는 한 번에 하나만 주입된다. 복합 이상(온도+진동 동시)은 미지원.

## 실행 요약

```bash
# 1) 브로커 (Windows 서비스면 이미 떠 있음)
sc query mosquitto        # RUNNING 확인

# 2) 서버 — MQTT 구독 켜서
MQTT_ENABLED=true uvicorn src.server:app --port 8000

# 3) 시뮬레이터 — 별도 터미널
python -m src.sensors.simulator --anomaly temp-drift
python -m src.sensors.simulator                        # 정상 운전 (알림 0건 확인용)
python -m src.sensors.simulator --interval-sec 0.5     # 주기 변경
```

기대 동작: 대시보드에 "센서 스트림" 행이 나타나고(MQTT LIVE), temp-drift 기준
약 30초 뒤 Line-2 카드가 경고색으로 바뀌면서 critical 토스트가 1건 뜬다.
증빙: `reports/dashboard-stage10-sensor-panel.png`, `reports/mqtt실시간센서입력.mp4`
