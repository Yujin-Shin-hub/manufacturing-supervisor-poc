/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-14
 * 작성 목적: 단계 10 센서 패널 상태 저장소 — SSE sensor_update/sensor_alert를 라인·센서별
 *           최신값 + 최근 60초 샘플로 유지한다 (시계열 DB 없음, 메모리 60초 한정 — 스코프 가드).
 *           임계치 판정은 서버 rules.py가 하며 프론트는 sensor_alert 표시만 담당한다.
 * 변경 이력:
 *   - 2026-07-14: 단계 10 최초 작성
 */
import { computed, onBeforeUnmount, reactive, ref, type ComputedRef, type Ref } from "vue";

import type { EventDataMap, EventName } from "../types/events";

/** 스파크라인·샘플 유지 시간 (docs/sensor-stream.md — 최근 60초만 메모리 유지) */
const SAMPLE_WINDOW_MS = 60_000;

/** sensor_alert 경고색 유지 시간 — 마지막 alert 이후 이 시간이 지나면 카드가 정상색으로 돌아온다 */
const ALERT_DECAY_MS = 60_000;

/** 스파크라인 1점 — 수신 시각 기준 (서버 observed_ts는 표시용으로만 유지) */
export interface SensorSample {
  at: number;
  value: number;
}

/** 라인 1개 × 센서 1종의 표시 상태 */
export interface SensorSeries {
  sensor: string;
  unit: string;
  latest: number;
  observedTs: string;
  samples: SensorSample[];
  /** 마지막 sensor_alert (rule·values는 서버 판정 결과 그대로) */
  alertRule: string | null;
  alertValues: number[];
  alertAt: number | null;
}

export interface SensorStreamState {
  /** line 이름 → (sensor 이름 → 시리즈). 수신된 것만 존재한다 */
  lines: Record<string, Record<string, SensorSeries>>;
  lineNames: ComputedRef<string[]>;
  /** 센서 이벤트를 한 번이라도 받았는지 — 패널 표시 여부 (MQTT 비활성 시 레이아웃 불변) */
  hasData: ComputedRef<boolean>;
  /** 마지막 수신 후 5초 이내인지 — LIVE 표시용 */
  receiving: ComputedRef<boolean>;
  /** 1초 틱 — 스파크라인 창·경고 감쇠 재계산 트리거 */
  now: Ref<number>;
  ingest: (event: EventName, data: EventDataMap[EventName]) => void;
  isAlerting: (series: SensorSeries) => boolean;
  lineAlerting: (line: string) => boolean;
}

/**
 * SSE 센서 이벤트를 센서 패널이 그릴 수 있는 반응형 상태로 유지한다.
 * useEventStream의 onEvent 훅에서 알림 시스템과 함께 호출된다.
 *
 * @return 라인별 센서 시리즈, 표시 여부, 경고 판정 헬퍼를 담은 상태 객체
 */
export function useSensorStream(): SensorStreamState {
  const lines = reactive<Record<string, Record<string, SensorSeries>>>({});
  const lastReceivedAt = ref(0);
  const now = ref(Date.now());

  const tick = window.setInterval(() => {
    now.value = Date.now();
  }, 1000);
  onBeforeUnmount(() => window.clearInterval(tick));

  const lineNames = computed(() =>
    Object.keys(lines).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
  );
  const hasData = computed(() => lastReceivedAt.value > 0);
  const receiving = computed(() => now.value - lastReceivedAt.value < 5000);

  /**
   * 라인·센서 시리즈를 얻거나 초기화한다.
   *
   * @param line 라인 이름 (예: Line-2)
   * @param sensor 센서 종류 (temperature 등)
   * @param unit 단위 문자열
   * @return 해당 시리즈 (없으면 새로 만들어 등록)
   */
  function series(line: string, sensor: string, unit: string): SensorSeries {
    const bucket = (lines[line] ??= {});
    return (bucket[sensor] ??= {
      sensor,
      unit,
      latest: 0,
      observedTs: "",
      samples: [],
      alertRule: null,
      alertValues: [],
      alertAt: null,
    });
  }

  /**
   * SSE 이벤트 1건을 센서 상태에 반영한다. 센서 외 이벤트는 무시한다.
   *
   * @param event api-spec 2-1의 이벤트 타입명
   * @param data 이벤트 data payload
   */
  function ingest(event: EventName, data: EventDataMap[EventName]): void {
    if (event === "sensor_update") {
      const update = data as EventDataMap["sensor_update"];
      const entry = series(update.line, update.sensor, update.unit);
      const at = Date.now();
      entry.latest = update.value;
      entry.unit = update.unit;
      entry.observedTs = update.observed_ts;
      entry.samples.push({ at, value: update.value });
      while (entry.samples.length > 0 && at - (entry.samples[0]?.at ?? at) > SAMPLE_WINDOW_MS) {
        entry.samples.shift();
      }
      lastReceivedAt.value = at;
      return;
    }
    if (event === "sensor_alert") {
      const alert = data as EventDataMap["sensor_alert"];
      const entry = series(alert.line, alert.sensor, alert.unit);
      entry.alertRule = alert.rule;
      entry.alertValues = alert.values;
      entry.alertAt = Date.now();
      lastReceivedAt.value = Date.now();
    }
  }

  /**
   * 시리즈가 현재 경고 표시 상태인지 판정한다 (마지막 alert 이후 ALERT_DECAY_MS 이내).
   *
   * @param seriesEntry 판정 대상 시리즈
   * @return 경고색으로 표시해야 하면 true
   */
  function isAlerting(seriesEntry: SensorSeries): boolean {
    return seriesEntry.alertAt !== null && now.value - seriesEntry.alertAt < ALERT_DECAY_MS;
  }

  /**
   * 라인의 센서 중 하나라도 경고 상태인지 판정한다 (카드 경고색 토글).
   *
   * @param line 라인 이름
   * @return 경고 상태 센서가 있으면 true
   */
  function lineAlerting(line: string): boolean {
    return Object.values(lines[line] ?? {}).some(isAlerting);
  }

  return { lines, lineNames, hasData, receiving, now, ingest, isAlerting, lineAlerting };
}
