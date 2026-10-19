import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../api";
import type { DocumentDetail, Element } from "../types";
import { VerifyPage } from "./VerifyPage";

const E = (id: string, extra: Partial<Element> = {}): Element => ({
  element_id: id, type: "paragraph", reading_order: 0, bbox_normalized: [0.1, 0.1, 0.5, 0.2], hierarchy_breadcrumb: [],
  text: id, content_markdown: id, confidence_score: 0.95, needs_human_review: false, review_reasons: [],
  extraction_engine: "", human_corrected: false, ...extra,
});

const detail: DocumentDetail = {
  document_id: "doc_1", job_id: "j", filename: "hd.pdf", status: "COMPLETED", total_pages: 1, done_pages: 1, created_at: 0,
  partial_pages: [],
  ast: {
    document_id: "doc_1", job_id: "j", status: "COMPLETED",
    metadata: { filename: "hd.pdf", total_pages: 1, has_red_stamp: false, processing_time_ms: 1, vlm_invocations_count: 0 },
    pages: [
      {
        page_number: 1, status: "DONE", width: 1000, height: 1400, orientation_applied: 0, deskew_angle: 0,
        elements: [
          E("el_a", { reading_order: 0, text: "Hôm nay" }),
          E("el_b", { reading_order: 1, text: "Mờ", needs_human_review: true, review_reasons: ["LOW_CONFIDENCE"], bbox_normalized: [0.1, 0.3, 0.9, 0.4] }),
        ],
      },
    ],
  },
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <VerifyPage documentId="doc_1" />
    </QueryClientProvider>,
  );
}

describe("VerifyPage", () => {
  beforeEach(() => {
    vi.spyOn(api, "getDocument").mockResolvedValue(detail);
    vi.spyOn(api, "getVlmSettings").mockResolvedValue({ ui_threshold: 0.8 } as never);
  });

  it("N jumps to the next issue and Enter confirms it", async () => {
    const correct = vi.spyOn(api, "correct").mockResolvedValue({
      correction_id: 1,
      element: { ...detail.ast!.pages[0].elements[1], needs_human_review: false, review_reasons: [], human_corrected: true },
    });
    renderPage();
    await screen.findByText("Hôm nay");
    expect(screen.getByText("Độ tự tin thấp")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "n" });
    await waitFor(() => expect(document.querySelector('[data-element="el_b"]')).toHaveClass("selected"));
    fireEvent.keyDown(window, { key: "Enter" });
    await waitFor(() => expect(correct).toHaveBeenCalledWith("doc_1", "el_b", "review", true));
  });

  it("editing a paragraph posts a text correction", async () => {
    const correct = vi.spyOn(api, "correct").mockResolvedValue({ correction_id: 2, element: { ...detail.ast!.pages[0].elements[0], text: "Hôm nay, ngày 12" } });
    renderPage();
    fireEvent.doubleClick(await screen.findByText("Hôm nay"));
    const box = screen.getByDisplayValue("Hôm nay");
    fireEvent.change(box, { target: { value: "Hôm nay, ngày 12" } });
    fireEvent.click(screen.getByRole("button", { name: /lưu sửa/i }));
    await waitFor(() => expect(correct).toHaveBeenCalledWith("doc_1", "el_a", "text", "Hôm nay, ngày 12"));
  });

  it("clicking a box on the page selects the element in the panel", async () => {
    renderPage();
    await screen.findByText("Hôm nay");
    fireEvent.click(document.querySelector('rect[data-id="el_b"]')!);
    await waitFor(() => expect(document.querySelector('[data-element="el_b"]')).toHaveClass("selected"));
  });
});
