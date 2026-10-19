import { fireEvent, render } from "@testing-library/react";
import type { Element, Page } from "../types";
import { PageViewer } from "./PageViewer";

const E = (id: string, extra: Partial<Element> = {}): Element => ({
  element_id: id, type: "paragraph", reading_order: 0, bbox_normalized: [0.1, 0.1, 0.5, 0.2], hierarchy_breadcrumb: [],
  text: "", content_markdown: "", confidence_score: 0.95, needs_human_review: false, review_reasons: [],
  extraction_engine: "", human_corrected: false, ...extra,
});

const page: Page = {
  page_number: 1, status: "DONE", width: 1000, height: 1400, orientation_applied: 0, deskew_angle: 0,
  elements: [E("a"), E("b", { needs_human_review: true, bbox_normalized: [0.1, 0.3, 0.9, 0.5] }), E("c", { bbox_normalized: null })],
};

describe("PageViewer", () => {
  it("draws one box per located element, coloured by status, and selects on click", () => {
    const onSelect = vi.fn();
    const { container } = render(<PageViewer imageUrl="x.jpg" page={page} selectedId="a" uiThreshold={0.8} onSelect={onSelect} />);
    const rects = container.querySelectorAll("rect.el");
    expect(rects.length).toBe(2);
    expect(container.querySelector('rect[data-id="a"]')).toHaveClass("sel");
    expect(container.querySelector('rect[data-id="b"]')).toHaveClass("st-review");
    fireEvent.click(container.querySelector('rect[data-id="b"]')!);
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("highlights the selected table cell", () => {
    const { container } = render(
      <PageViewer imageUrl="x.jpg" page={page} selectedId="a" uiThreshold={0.8} onSelect={() => {}} highlight={[0.2, 0.2, 0.3, 0.25]} />,
    );
    expect(container.querySelector("rect.cell-hl")).not.toBeNull();
  });
});
