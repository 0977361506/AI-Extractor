import { fireEvent, render, screen } from "@testing-library/react";
import type { PageTrace } from "../types";
import { StepPanel } from "./StepPanel";

const trace: PageTrace = {
  page: 1,
  steps: {
    preprocess: { status: "done", ms: 400, summary: { rotation: 90, skew: 1.2, width: 1000, height: 1400 } },
    layout: {
      status: "done", ms: 800, summary: { regions: 2, by_label: { table: 1, text: 1 }, text_boxes: 3 },
      regions: [{ label: "table", score: 0.93, bbox: [0.1, 0.2, 0.9, 0.5] }, { label: "text", score: 0.88, bbox: [0.1, 0.6, 0.9, 0.7] }],
      text_boxes: [[0.1, 0.1, 0.5, 0.12], [0.1, 0.62, 0.8, 0.65], [0.1, 0.66, 0.7, 0.69]],
    },
    tables: { status: "done", summary: { tables: 1, cells: 2, check_failed: 1 },
      tables: [{ bbox: [0.1, 0.2, 0.9, 0.5], cells: [
        { row: 0, col: 0, text: "Tổng", conf: 0.9, bbox: [0.1, 0.2, 0.5, 0.3], check_failed: false },
        { row: 0, col: 1, text: "1.200", conf: 0.7, bbox: [0.5, 0.2, 0.9, 0.3], check_failed: true }] }] },
    ocr: { status: "done", summary: { lines: 2, mean_conf: 0.9, low_conf: 1 },
      lines: [{ text: "Hợp đồng tín dụng", conf: 0.97, bbox: [0.1, 0.62, 0.8, 0.65], source: "ocr" },
        { text: "S0 tiền", conf: 0.6, bbox: [0.1, 0.66, 0.7, 0.69], source: "ocr" }] },
    marks: { status: "running" },
    vlm: { status: "done", summary: { calls: 1, cache_hits: 0, failed: 0, changed: 1 },
      changes: [{ element_id: "el_p1_002", before: "S0 tiền", after: "Số tiền" }] },
  },
};

const base = { documentId: "doc_1", page: 1, trace, traceMissing: false, onOpenVerify: () => {} };

describe("StepPanel", () => {
  it("preprocess compares the original page with the straightened one", () => {
    render(<StepPanel {...base} step={{ id: "preprocess", label: "Làm sạch ảnh", status: "done", ms: 400, summary: trace.steps.preprocess.summary }} />);
    const srcs = screen.getAllByRole("img").map((i) => i.getAttribute("src"));
    expect(srcs).toContain("/api/v1/documents/doc_1/pages/1/image?kind=raw");
    expect(srcs).toContain("/api/v1/documents/doc_1/pages/1/image?kind=display");
    expect(screen.getByText(/xoay 90°/)).toBeInTheDocument();
  });

  it("layout draws one box per region, labelled by type", () => {
    const { container } = render(<StepPanel {...base} step={{ id: "layout", label: "Bố cục", status: "done", summary: trace.steps.layout.summary }} />);
    expect(container.querySelectorAll("rect.region")).toHaveLength(2);
    expect(container.querySelector("rect.region.l-table")).toBeInTheDocument();
    expect(screen.getByText(/Bảng: 1/)).toBeInTheDocument();
  });

  it("tables flags cells that fail the arithmetic check", () => {
    const { container } = render(<StepPanel {...base} step={{ id: "tables", label: "Bảng", status: "done", summary: trace.steps.tables.summary }} />);
    expect(container.querySelectorAll("rect.cell")).toHaveLength(2);
    expect(container.querySelectorAll("rect.cell.bad")).toHaveLength(1);
  });

  it("ocr lines carry their text; details list low-confidence lines", () => {
    const { container } = render(<StepPanel {...base} step={{ id: "ocr", label: "Đọc chữ", status: "done", summary: trace.steps.ocr.summary }} />);
    expect(container.querySelectorAll("rect.line")).toHaveLength(2);
    expect(container.querySelector("rect.line.low title")?.textContent).toContain("S0 tiền");
    fireEvent.click(screen.getByLabelText("Chi tiết"));
    expect(screen.getByText("Hợp đồng tín dụng")).toBeInTheDocument();
  });

  it("vlm lists what the AI changed", () => {
    render(<StepPanel {...base} step={{ id: "vlm", label: "AI chuyên sâu", status: "done", summary: trace.steps.vlm.summary }} />);
    expect(screen.getByText("S0 tiền")).toBeInTheDocument();
    expect(screen.getByText("Số tiền")).toBeInTheDocument();
  });

  it("skipped and failed steps explain why", () => {
    const { rerender } = render(<StepPanel {...base} step={{ id: "ocr", label: "Đọc chữ", status: "skipped", reason: "Đọc trực tiếp từ lớp chữ PDF" }} />);
    expect(screen.getByText(/lớp chữ PDF/)).toBeInTheDocument();
    rerender(<StepPanel {...base} step={{ id: "layout", label: "Bố cục", status: "failed", error: "RuntimeError: model crashed" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("model crashed");
  });

  it("documents processed before traces existed fall back to the final result", () => {
    const onOpen = vi.fn();
    render(<StepPanel {...base} trace={null} traceMissing onOpenVerify={onOpen} step={{ id: "layout", label: "Bố cục", status: "pending" }} />);
    expect(screen.getByText(/chưa có dữ liệu từng bước/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Mở đối chiếu/ }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("assemble summarises the document and opens verification", () => {
    const onOpen = vi.fn();
    render(<StepPanel {...base} onOpenVerify={onOpen} step={{ id: "assemble", label: "Hoàn tất", status: "done", summary: { pages: 2, elements: 30, needs_review: 3, chunks: 5 } }} />);
    expect(screen.getByText(/3 mục cần duyệt/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Mở đối chiếu/ }));
    expect(onOpen).toHaveBeenCalled();
  });
});
