import type { Element, Page } from "../types";
import { elementStatus, nextIssue, REASON_VI } from "./review";

const E = (id: string, extra: Partial<Element> = {}): Element => ({
  element_id: id, type: "paragraph", reading_order: 0, hierarchy_breadcrumb: [], text: "", content_markdown: "",
  confidence_score: 0.95, needs_human_review: false, review_reasons: [], extraction_engine: "", human_corrected: false, ...extra,
});

const P = (n: number, elements: Element[]): Page => ({ page_number: n, status: "DONE", width: 1, height: 1, orientation_applied: 0, deskew_angle: 0, elements });

describe("review helpers", () => {
  it("classifies element status by review flag and confidence", () => {
    expect(elementStatus(E("a", { needs_human_review: true }), 0.8)).toBe("review");
    expect(elementStatus(E("b", { confidence_score: 0.7 }), 0.8)).toBe("low");
    expect(elementStatus(E("c"), 0.8)).toBe("ok");
    expect(elementStatus(E("d", { confidence_score: 0.5, human_corrected: true }), 0.8)).toBe("ok");
  });

  it("finds the next element needing review across pages, wrapping around", () => {
    const pages = [P(1, [E("a"), E("b", { needs_human_review: true })]), P(2, [E("c", { needs_human_review: true })])];
    expect(nextIssue(pages, null)).toEqual({ page: 1, elementId: "b" });
    expect(nextIssue(pages, "b")).toEqual({ page: 2, elementId: "c" });
    expect(nextIssue(pages, "c")).toEqual({ page: 1, elementId: "b" });
    expect(nextIssue([P(1, [E("a")])], null)).toBeNull();
  });

  it("has Vietnamese labels for review reasons", () => {
    expect(REASON_VI.OCR_VLM_MISMATCH).toContain("khác");
  });
});
