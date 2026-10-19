import { fireEvent, render } from "@testing-library/react";
import type { Element, Page } from "../types";
import { PreviewViewer } from "./PreviewViewer";

const E = (id: string, extra: Partial<Element> = {}): Element => ({
  element_id: id, type: "paragraph", reading_order: 0, bbox_normalized: null, hierarchy_breadcrumb: [],
  text: "", content_markdown: "", confidence_score: 1, needs_human_review: false, review_reasons: [],
  extraction_engine: "native", human_corrected: false, ...extra,
});

const page: Page = {
  page_number: 1, status: "DONE", width: 0, height: 0, orientation_applied: 0, deskew_angle: 0,
  elements: [E("a"), E("t", { type: "table", needs_human_review: true })],
};

const ORIGINAL = `<div class="blk" data-el="a"><p>Hợp đồng</p></div>
<div class="blk" data-el="t"><table><tr><td data-r="0" data-c="0">A</td><td data-r="0" data-c="1">B</td></tr></table></div>`;

function setup(props: Partial<Parameters<typeof PreviewViewer>[0]> = {}) {
  const onSelect = vi.fn();
  const utils = render(<PreviewViewer url="/p/1" page={page} selectedId={null} selectedCell={null} uiThreshold={0.8} onSelect={onSelect} {...props} />);
  const frame = utils.container.querySelector("iframe")!;
  const d = frame.contentDocument!; // jsdom does not fetch the src: write the original in directly
  d.open();
  d.write(`<!DOCTYPE html><html><body>${ORIGINAL}</body></html>`);
  d.close();
  fireEvent.load(frame);
  return { ...utils, frame, onSelect, doc: frame.contentDocument! };
}

describe("PreviewViewer", () => {
  it("loads the original in a sandboxed frame without scripts", () => {
    const { frame } = setup();
    expect(frame.getAttribute("src")).toBe("/p/1");
    expect(frame.getAttribute("sandbox")).toBe("allow-same-origin");
  });

  it("clicking a block or a cell in the original selects it", () => {
    const { doc, onSelect } = setup();
    fireEvent.click(doc.querySelector("p")!);
    expect(onSelect).toHaveBeenLastCalledWith("a", null);
    fireEvent.click(doc.querySelector('td[data-c="1"]')!);
    expect(onSelect).toHaveBeenLastCalledWith("t", { row: 0, col: 1 });
  });

  it("marks the selected block, the selected cell and blocks needing review", () => {
    const { doc, rerender, frame } = setup();
    expect(doc.querySelector('[data-el="t"]')).toHaveClass("rev");
    rerender(
      <PreviewViewer url="/p/1" page={page} selectedId="t" selectedCell={{ row: 0, col: 1 }} uiThreshold={0.8} onSelect={() => {}} />,
    );
    expect(frame.contentDocument!.querySelector('[data-el="t"]')).toHaveClass("sel");
    expect(doc.querySelector('[data-el="a"]')).not.toHaveClass("sel");
    expect(doc.querySelector('td[data-c="1"]')).toHaveClass("cell-hl");
    expect(doc.querySelector('td[data-c="0"]')).not.toHaveClass("cell-hl");
  });
});
