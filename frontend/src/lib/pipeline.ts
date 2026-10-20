import type { ProgressEvent, StepEvent, StepStatus } from "../types";

/** Steps reported once for the whole document (``page: null``); the rest are per page. */
export const DOC_STEPS = new Set(["ingest", "parse", "assemble"]);

export const STEP_LABELS: Record<string, string> = {
  ingest: "Nhận file",
  parse: "Đọc cấu trúc",
  preprocess: "Làm sạch ảnh",
  layout: "Bố cục",
  tables: "Bảng",
  ocr: "Đọc chữ",
  marks: "Dấu & ghép trang",
  vlm: "AI chuyên sâu",
  assemble: "Hoàn tất",
};

export interface StepState {
  status: StepStatus;
  ms?: number;
  summary?: Record<string, unknown>;
  error?: string;
  reason?: string;
}

export interface PipelineState {
  plan: { kind: string; total_pages: number | null; steps: string[] } | null;
  doc: Record<string, StepState>;
  pages: Record<number, Record<string, StepState>>;
  focus: { page: number; step: string } | null;
  status: string;
  pct: number;
  message: string;
  final: boolean;
}

const FINAL = new Set(["COMPLETED", "PARTIAL", "FAILED"]);

export const initialPipeline: PipelineState = {
  plan: null, doc: {}, pages: {}, focus: null, status: "PENDING", pct: 0, message: "", final: false,
};

function applyStep(s: PipelineState, ev: StepEvent): PipelineState {
  const { page, step, status, ...rest } = ev;
  const st: StepState = { status, ...rest };
  if (page == null) {
    const focusPage = s.focus?.page ?? 1;
    return { ...s, doc: { ...s.doc, [step]: st }, focus: status === "done" && step === "ingest" ? s.focus : { page: focusPage, step } };
  }
  const pages = { ...s.pages, [page]: { ...s.pages[page], [step]: st } };
  const moves = status === "running" || status === "failed" || !s.focus || s.focus.page !== page;
  return { ...s, pages, focus: moves ? { page, step } : s.focus };
}

export function reducePipeline(s: PipelineState, ev: ProgressEvent): PipelineState {
  let next: PipelineState = { ...s, status: ev.status, pct: ev.progress_percentage, message: ev.message_vi, final: FINAL.has(ev.status) };
  if (ev.current_stage === "PLAN" && ev.plan) next = { ...next, plan: ev.plan, doc: {}, pages: {}, focus: null };
  else if (ev.current_stage === "STEP" && ev.step) next = applyStep(next, ev.step);
  if (next.final && next.plan) next = { ...next, focus: { page: next.focus?.page ?? 1, step: "assemble" } };
  return next;
}

/** Percentage of finished steps (doc-level once, page-level per page): moves within a page, unlike the backend's per-page %. */
export function progressOf(s: PipelineState): number {
  if (s.final) return 100;
  if (!s.plan) return s.pct;
  const docSteps = s.plan.steps.filter((x) => DOC_STEPS.has(x));
  const pageSteps = s.plan.steps.filter((x) => !DOC_STEPS.has(x));
  const pages = s.plan.total_pages ?? 1;
  const total = docSteps.length + pageSteps.length * pages;
  const finished = (st?: StepState) => !!st && st.status !== "pending" && st.status !== "running";
  const done =
    docSteps.filter((x) => finished(s.doc[x])).length +
    Object.values(s.pages).reduce((n, pg) => n + pageSteps.filter((x) => finished(pg[x])).length, 0);
  return total ? Math.round((100 * done) / total) : s.pct;
}

export function stepsForPage(s: PipelineState, page: number): ({ id: string; label: string } & StepState)[] {
  if (!s.plan) return [];
  return s.plan.steps.map((id) => {
    const st = (DOC_STEPS.has(id) ? s.doc[id] : s.pages[page]?.[id]) ?? { status: "pending" as const };
    return { id, label: STEP_LABELS[id] ?? id, ...st };
  });
}
