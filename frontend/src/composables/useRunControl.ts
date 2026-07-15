/**
 * 작성자  : 신유진
 * 작성일  : 2026-07-07
 * 작성 목적: POST /run 실행 트리거·실행 요청 상태 관리 (docs/api-spec.md 1-2 계약)
 * 변경 이력:
 *   - 2026-07-07: 단계 8 최초 작성
 */
import { reactive, ref, type Ref } from "vue";

export type RunMode = "ask" | "report";
export type LlmProvider = "auto" | "qwen" | "openai";

export interface RunForm {
  mode: RunMode;
  asof: string;
  query: string;
  llm_provider: LlmProvider;
}

export interface RunControlState {
  form: RunForm;
  submitting: Ref<boolean>;
  errorMessage: Ref<string | null>;
  startRun: () => Promise<void>;
}

/**
 * /run 실행 폼 상태와 실행 트리거 함수를 제공한다.
 *
 * @returns 실행 폼·전송 중 여부·에러 메시지·startRun 함수를 담은 상태 객체
 */
export function useRunControl(): RunControlState {
  const form = reactive<RunForm>({
    mode: "report",
    asof: "",
    query: "",
    llm_provider: "auto",
  });
  const submitting = ref(false);
  const errorMessage = ref<string | null>(null);

  /**
   * POST /run으로 Supervisor 실행을 요청한다. 202면 성공, 409(run in progress) 등은 에러 메시지로 노출한다.
   */
  async function startRun(): Promise<void> {
    errorMessage.value = null;
    if (form.mode === "ask" && form.query.trim() === "") {
      errorMessage.value = "ask 모드에서는 query가 필요합니다";
      return;
    }
    submitting.value = true;
    try {
      const payload: Record<string, string> = {
        mode: form.mode,
        llm_provider: form.llm_provider,
      };
      if (form.asof.trim() !== "") payload.asof = form.asof.trim();
      if (form.mode === "ask") payload.query = form.query.trim();

      const response = await fetch("/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        errorMessage.value = body?.detail ?? `HTTP ${response.status}`;
      }
    } catch (requestError) {
      errorMessage.value =
        requestError instanceof Error ? requestError.message : String(requestError);
    } finally {
      submitting.value = false;
    }
  }

  return { form, submitting, errorMessage, startRun };
}
