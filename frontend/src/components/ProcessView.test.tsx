import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api";
import type { PageTrace, ProgressEvent } from "../types";
import { ProcessView } from "./ProcessView";

class FakeES {
  static last: FakeES | null = null;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;
  constructor(public url: string) {
    FakeES.last = this;
  }
  addEventListener(type: string, fn: (e: MessageEvent) => void) {
    (this.listeners[type] ??= []).push(fn);
  }
  close() {
    this.closed = true;
  }
  emit(ev: ProgressEvent) {
    act(() => this.listeners.progress?.forEach((fn) => fn({ data: JSON.stringify(ev) } as MessageEvent)));
  }
}

const STEPS = ["ingest", "preprocess", "layout", "tables", "ocr", "marks", "vlm", "assemble"];
const ev = (extra: Partial<ProgressEvent>): ProgressEvent => ({ status: "IN_PROGRESS", progress_percentage: 20, message_vi: "…", ...extra });
const step = (page: number | null, name: string, status: string, more: object = {}) =>
  ev({ current_stage: "STEP", step: { page, step: name, status, ...more } as never });

const trace: PageTrace = {
  page: 1,
  steps: {
    preprocess: { status: "done", summary: { rotation: 0, skew: 0, width: 100, height: 140 } },
    layout: { status: "done", summary: { regions: 1, by_label: { table: 1 } }, regions: [{ label: "table", score: 0.9, bbox: [0.1, 0.1, 0.9, 0.5] }] },
  },
};

function setup() {
  vi.stubGlobal("EventSource", FakeES);
  const getTrace = vi.spyOn(api, "getTrace").mockResolvedValue(trace);
  const onOpen = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ProcessView documentId="doc_1" filename="hd.pdf" onOpen={onOpen} />
    </QueryClientProvider>,
  );
  const es = FakeES.last!;
  return { es, getTrace, onOpen };
}

afterEach(() => vi.unstubAllGlobals());

describe("ProcessView", () => {
  it("subscribes to the document's events and follows the running step", async () => {
    const { es } = setup();
    expect(es.url).toBe("/api/v1/documents/doc_1/events");
    es.emit(ev({ current_stage: "PLAN", plan: { kind: "pdf", total_pages: 2, steps: STEPS } }));
    es.emit(step(null, "ingest", "done"));
    es.emit(step(1, "preprocess", "done"));
    es.emit(step(1, "layout", "running"));
    expect(screen.getByRole("button", { name: /Bố cục/ })).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("heading", { name: "Bố cục" })).toBeInTheDocument();
    es.emit(step(1, "layout", "done", { summary: { regions: 1, by_label: { table: 1 } } }));
    es.emit(step(1, "tables", "running"));
    expect(screen.getByRole("heading", { name: "Bảng" })).toBeInTheDocument();
  });

  it("choosing a step stops following and shows that step's result from the trace", async () => {
    const { es, getTrace } = setup();
    es.emit(ev({ current_stage: "PLAN", plan: { kind: "pdf", total_pages: 2, steps: STEPS } }));
    es.emit(step(1, "preprocess", "done"));
    es.emit(step(1, "layout", "done", { summary: { regions: 1, by_label: { table: 1 } } }));
    es.emit(step(1, "tables", "running"));
    fireEvent.click(screen.getByRole("button", { name: /Bố cục/ }));
    await waitFor(() => expect(document.querySelectorAll("rect.region")).toHaveLength(1));
    expect(getTrace).toHaveBeenCalledWith("doc_1", 1);
    es.emit(step(1, "ocr", "running"));
    expect(screen.getByRole("heading", { name: "Bố cục" })).toBeInTheDocument();
  });

  it("switches pages and opens verification when done", async () => {
    const { es, onOpen } = setup();
    es.emit(ev({ current_stage: "PLAN", plan: { kind: "pdf", total_pages: 2, steps: STEPS } }));
    es.emit(step(2, "preprocess", "running"));
    expect(screen.getByRole("button", { name: "Trang 2" })).toHaveClass("active");
    fireEvent.click(screen.getByRole("button", { name: "Trang 1" }));
    expect(screen.getByRole("button", { name: "Trang 1" })).toHaveClass("active");
    es.emit(step(null, "assemble", "done", { summary: { pages: 2, elements: 9, needs_review: 0, chunks: 2 } }));
    es.emit(ev({ status: "COMPLETED", progress_percentage: 100, current_stage: "DONE" }));
    fireEvent.click(screen.getByRole("button", { name: /Mở đối chiếu/ }));
    expect(onOpen).toHaveBeenCalledWith("doc_1");
  });

  it("documents processed before the stepper existed get a plain fallback", () => {
    const { es } = setup();
    es.emit(ev({ status: "COMPLETED", progress_percentage: 100, current_stage: "DONE" }));
    expect(screen.getByText(/trước khi có quy trình từng bước/)).toBeInTheDocument();
  });
});
