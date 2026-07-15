/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: 관제 현황 스냅샷 — 읽기 전용 /api(schedules·risks·machines)를 로드해
 *           KPI·리스크 추이·라인 플로우가 쓰는 원본 행과 집계값을 만든다
 *           (api-spec 1-3, 원본 CSV 컬럼 그대로. 집계는 표시 계층에서만)
 * 변경 이력:
 *   - 2026-07-07: 단계 8 대시보드 재설계 2차 — KPI 스트립·리스크 표 데이터 소스로 추가
 *   - 2026-07-07: 재설계 4차 — 원본 행(risks/machines/schedules) 노출, 시간당 리스크 추이 헬퍼,
 *                 asof 저장 추가 (리스크 추이 차트·라인 플로우·개선 효과 요약용)
 *   - 2026-07-14: KPI CRITICAL 집계를 /api/risk-summary(risk_alert Worker와 동일한
 *                 score_delay_risk 집계)로 교체 — 대시보드-리포트 수치 정합 (api-spec 1-3)
 */
import { computed, onMounted, ref, type ComputedRef, type Ref } from "vue";

/** GET /api/schedules row — schedule_master 컬럼 중 사용하는 필드만 */
export interface ScheduleRow {
  schedule_id: string;
  status: string;
  due_date: string;
  process_step: string;
  assigned_machine: string;
}

/** GET /api/risks row — delay_risk 컬럼 중 사용하는 필드만 */
export interface RiskRow {
  risk_id: string;
  schedule_id: string;
  machine_id: string;
  risk_score: number;
  risk_level: string;
  risk_factor: string;
  estimated_delay_hr: number;
  detection_time: string;
}

/** GET /api/machines row — machine_process_map 컬럼 중 사용하는 필드만 */
export interface MachineRow {
  process_step: string;
  machine_id: string;
  machine_status: string;
  current_load: number;
  available_yn: string;
}

/** 리스크 추이 차트의 1시간 구간 1점 */
export interface TrendPoint {
  /** 구간 키 ("YYYY-MM-DD HH") — 임계 초과 알림 dedupe에도 사용 */
  hourKey: string;
  /** 축 라벨 ("HH시") */
  label: string;
  maxScore: number;
  count: number;
}

/** CRITICAL 판정 경계 (delay_risk 데이터의 risk_level 경계값: CRITICAL ≥ 85) */
export const RISK_SCORE_CRITICAL_THRESHOLD = 85;

/** GET /api/risk-summary 응답 — risk_alert Worker와 동일한 score_delay_risk(asof) 집계 */
export interface RiskSummary {
  asof: string;
  total: number;
  critical: number;
  high: number;
}

export interface FactorySnapshotState {
  loading: Ref<boolean>;
  errorMessage: Ref<string | null>;
  asof: Ref<string>;
  schedules: Ref<ScheduleRow[]>;
  risks: Ref<RiskRow[]>;
  machines: Ref<MachineRow[]>;
  /** risk_alert Worker와 동일한 서버 집계 (KPI 수치 정합의 원천) */
  riskSummary: Ref<RiskSummary | null>;
  scheduleTotal: ComputedRef<number>;
  scheduleActive: ComputedRef<number>;
  criticalCount: ComputedRef<number>;
  refresh: () => Promise<void>;
}

/**
 * detection_time을 1시간 구간으로 묶어 구간별 max risk_score와 감지 건수를 만든다.
 * 차트 렌더링과 임계 초과 알림 판단이 같은 함수를 쓴다 (단일 소스).
 *
 * @param rows /api/risks 원본 행 목록
 * @returns 시간순 정렬된 추이 점 목록
 */
export function hourlyRiskSeries(rows: RiskRow[]): TrendPoint[] {
  const buckets = new Map<string, { maxScore: number; count: number }>();
  for (const row of rows) {
    if (typeof row.detection_time !== "string" || row.detection_time.length < 13) continue;
    const hourKey = row.detection_time.slice(0, 13);
    const bucket = buckets.get(hourKey);
    if (bucket === undefined) {
      buckets.set(hourKey, { maxScore: row.risk_score, count: 1 });
    } else {
      bucket.maxScore = Math.max(bucket.maxScore, row.risk_score);
      bucket.count += 1;
    }
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([hourKey, bucket]) => ({
      hourKey,
      label: `${hourKey.slice(11, 13)}시`,
      maxScore: bucket.maxScore,
      count: bucket.count,
    }));
}

/**
 * 읽기 전용 조회 API 3종을 로드해 관제 화면들이 공유하는 스냅샷 상태를 제공한다.
 *
 * @returns 로딩·오류 상태, 원본 행, KPI 집계값, 재조회 함수를 담은 상태 객체
 */
export function useFactorySnapshot(): FactorySnapshotState {
  const loading = ref(false);
  const errorMessage = ref<string | null>(null);
  const asof = ref("");
  const schedules = ref<ScheduleRow[]>([]);
  const risks = ref<RiskRow[]>([]);
  const machines = ref<MachineRow[]>([]);
  const riskSummary = ref<RiskSummary | null>(null);

  const scheduleTotal = computed(() => schedules.value.length);
  const scheduleActive = computed(
    () => schedules.value.filter((row) => row.status === "진행중").length,
  );
  // KPI CRITICAL은 리포트의 리스크 알림 Worker와 같은 서버 집계를 쓴다 (수치 정합).
  // risks 원본 행은 리스크 추이 차트(감지 이력 전체) 전용으로 유지한다.
  const criticalCount = computed(() => riskSummary.value?.critical ?? 0);

  /**
   * 조회 API 1건을 호출해 asof와 rows 배열을 반환한다.
   *
   * @param path /api 하위 경로 (예: "/api/risks")
   * @returns 응답의 asof 문자열과 rows 배열
   */
  async function fetchRows<RowType>(
    path: string,
  ): Promise<{ asof: string; rows: RowType[] }> {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`${path} → HTTP ${response.status}`);
    return (await response.json()) as { asof: string; rows: RowType[] };
  }

  /**
   * 스냅샷 3종을 병렬 재조회한다. 실패 시 기존 값을 유지하고 오류 메시지만 노출한다.
   */
  async function refresh(): Promise<void> {
    loading.value = true;
    errorMessage.value = null;
    try {
      const [scheduleBody, riskBody, machineBody, summaryResponse] = await Promise.all([
        fetchRows<ScheduleRow>("/api/schedules"),
        fetchRows<RiskRow>("/api/risks"),
        fetchRows<MachineRow>("/api/machines"),
        fetch("/api/risk-summary"),
      ]);
      if (!summaryResponse.ok) {
        throw new Error(`/api/risk-summary → HTTP ${summaryResponse.status}`);
      }
      asof.value = scheduleBody.asof;
      schedules.value = scheduleBody.rows;
      risks.value = riskBody.rows;
      machines.value = machineBody.rows;
      riskSummary.value = (await summaryResponse.json()) as RiskSummary;
    } catch (requestError) {
      errorMessage.value =
        requestError instanceof Error ? requestError.message : String(requestError);
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => void refresh());

  return {
    loading,
    errorMessage,
    asof,
    schedules,
    risks,
    machines,
    riskSummary,
    scheduleTotal,
    scheduleActive,
    criticalCount,
    refresh,
  };
}
