import type { Element, Page } from "../types";

export type Status = "review" | "low" | "ok";

export const REASON_VI: Record<string, string> = {
  LOW_CONFIDENCE: "Độ tự tin thấp",
  STAMP_OVERLAP: "Dấu mộc đè lên nội dung",
  INK_OVERLAP: "Mực màu / vết bẩn đè",
  HANDWRITING: "Chữ viết tay",
  OCR_VLM_MISMATCH: "OCR và AI đọc khác nhau",
  ARITHMETIC_CHECK_FAILED: "Sai tổng cộng / công thức",
  TABLE_STRUCTURE_INVALID: "Cấu trúc bảng không hợp lệ",
  VLM_UNAVAILABLE: "Không gọi được AI",
  VLM_OUTPUT_INVALID: "AI trả sai định dạng",
};

export const TYPE_VI: Record<string, string> = {
  title: "Tiêu đề", heading: "Đề mục", paragraph: "Đoạn văn", list_item: "Mục liệt kê", caption: "Chú thích",
  page_header: "Đầu trang", page_footer: "Chân trang", formula: "Công thức", figure: "Hình", table: "Bảng",
  form_field: "Trường biểu mẫu", choice_group: "Ô chọn", diagram: "Sơ đồ", stamp: "Con dấu", signature: "Chữ ký",
  handwritten_note: "Ghi chú tay",
};

export function elementStatus(el: Element, uiThreshold: number): Status {
  if (el.human_corrected && !el.needs_human_review) return "ok";
  if (el.needs_human_review) return "review";
  if (el.confidence_score < uiThreshold) return "low";
  return "ok";
}

export function nextIssue(pages: Page[], currentId: string | null): { page: number; elementId: string } | null {
  const flat = pages.flatMap((p) =>
    [...p.elements].sort((a, b) => a.reading_order - b.reading_order).map((el) => ({ page: p.page_number, el })),
  );
  const issues = flat.filter((x) => x.el.needs_human_review);
  if (!issues.length) return null;
  const idx = currentId ? flat.findIndex((x) => x.el.element_id === currentId) : -1;
  const after = flat.slice(idx + 1).find((x) => x.el.needs_human_review) ?? issues[0];
  return { page: after.page, elementId: after.el.element_id };
}
