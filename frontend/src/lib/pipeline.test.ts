import type { ProgressEvent } from "../types";
import { initialPipeline, progressOf, reducePipeline, stepsForPage } from "./pipeline";

const plan = (steps = ["ingest", "preprocess", "layout", "tables", "ocr", "marks", "vlm", "assemble"], total = 2): ProgressEvent => ({
  status: "IN_PROGRESS", progress_percentage: 1, current_stage: "PLAN", message_vi: "Bắt đầu",
  plan: { kind: "pdf", total_pages: total, steps },
});
const step = (page: number | null, name: string, status: string, extra: object = {}): ProgressEvent => ({
  status: "IN_PROGRESS", progress_percentage: 30, current_stage: "STEP", message_vi: `${name} ${status}`,
  step: { page, step: name, status, ...extra } as never,
});

const run = (events: ProgressEvent[]) => events.reduce(reducePipeline, initialPipeline);

describe("pipeline reducer", () => {
  it("tracks document-level and page-level steps in plan order", () => {
    const s = run([plan(), step(null, "ingest", "done", { ms: 5 }), step(1, "preprocess", "done", { ms: 400, summary: { rotation: 90 } }), step(1, "layout", "running")]);
    const p1 = stepsForPage(s, 1);
    expect(p1.map((x) => x.id)).toEqual(["ingest", "preprocess", "layout", "tables", "ocr", "marks", "vlm", "assemble"]);
    expect(p1.map((x) => x.status)).toEqual(["done", "done", "running", "pending", "pending", "pending", "pending", "pending"]);
    expect(p1[1].ms).toBe(400);
    expect(p1[1].summary).toEqual({ rotation: 90 });
    expect(stepsForPage(s, 2).map((x) => x.status).slice(0, 3)).toEqual(["done", "pending", "pending"]);
  });

  it("focuses on the latest active page and step", () => {
    const s = run([plan(), step(1, "marks", "done"), step(1, "vlm", "skipped"), step(2, "preprocess", "running")]);
    expect(s.focus).toEqual({ page: 2, step: "preprocess" });
    const failed = reducePipeline(s, step(2, "preprocess", "failed", { error: "boom" }));
    expect(failed.focus).toEqual({ page: 2, step: "preprocess" });
    expect(stepsForPage(failed, 2)[1].error).toBe("boom");
  });

  it("ends on the assemble step when the document finishes", () => {
    const s = run([plan(["ingest", "parse", "assemble"], 0), step(null, "parse", "done"), step(null, "assemble", "done"),
      { status: "COMPLETED", progress_percentage: 100, current_stage: "DONE", message_vi: "Hoàn tất" }]);
    expect(s.final).toBe(true);
    expect(s.focus).toEqual({ page: 1, step: "assemble" });
    expect(stepsForPage(s, 1).map((x) => x.status)).toEqual(["pending", "done", "done"]);
  });

  it("a new PLAN (job restarted) resets progress, and replaying events gives the same state", () => {
    const events = [plan(), step(1, "preprocess", "done"), plan(), step(1, "preprocess", "running")];
    const s = run(events);
    expect(stepsForPage(s, 1)[1].status).toBe("running");
    expect(run(events)).toEqual(s);
  });

  it("progress counts finished steps across all pages, not just finished pages", () => {
    const s = run([plan(undefined, 2), step(null, "ingest", "done"), step(1, "preprocess", "done"), step(1, "layout", "skipped"), step(1, "tables", "running")]);
    // 2 doc steps + 6 page steps x 2 pages = 14; ingest + preprocess + layout finished
    expect(progressOf(s)).toBe(Math.round((100 * 3) / 14));
    expect(progressOf(run([plan(undefined, 2), { status: "COMPLETED", progress_percentage: 100, message_vi: "" }]))).toBe(100);
  });

  it("ignores unrelated events and knows nothing before a plan", () => {
    const s = run([{ status: "PENDING", progress_percentage: 0, message_vi: "Đang chờ" }]);
    expect(s.plan).toBeNull();
    expect(s.message).toBe("Đang chờ");
    expect(stepsForPage(s, 1)).toEqual([]);
  });
});
