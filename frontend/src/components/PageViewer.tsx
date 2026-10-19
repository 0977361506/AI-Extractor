import { useEffect, useRef } from "react";
import { elementStatus } from "../lib/review";
import type { BBox, Page } from "../types";

interface Props {
  imageUrl: string;
  page: Page;
  selectedId: string | null;
  uiThreshold: number;
  onSelect: (id: string) => void;
  highlight?: BBox | null;
  zoom?: number;
  hiddenTypes?: Set<string>;
}

export function PageViewer({ imageUrl, page, selectedId, uiThreshold, onSelect, highlight, zoom = 1, hiddenTypes }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const aspect = page.width && page.height ? page.height / page.width : 1.414;

  // keep the selected element / cell in view
  useEffect(() => {
    const box = highlight ?? page.elements.find((e) => e.element_id === selectedId)?.bbox_normalized;
    const el = scroller.current;
    if (!box || !el) return;
    const inner = el.firstElementChild as HTMLElement | null;
    if (!inner) return;
    const top = box[1] * inner.clientHeight - el.clientHeight / 3;
    const left = box[0] * inner.clientWidth - el.clientWidth / 4;
    el.scrollTo?.({ top: Math.max(0, top), left: Math.max(0, left), behavior: "smooth" });
  }, [selectedId, highlight, page]);

  return (
    <div className="page-viewer" ref={scroller}>
      <div className="page-canvas" style={{ width: `${zoom * 100}%`, paddingTop: `${aspect * zoom * 100}%` }}>
        <img src={imageUrl} alt={`Trang ${page.page_number}`} draggable={false} />
        <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Khung tọa độ">
          {page.elements
            .filter((e) => e.bbox_normalized && !hiddenTypes?.has(e.type))
            .map((e) => {
              const [x0, y0, x1, y1] = e.bbox_normalized!;
              const st = elementStatus(e, uiThreshold);
              return (
                <rect
                  key={e.element_id}
                  data-id={e.element_id}
                  className={`el st-${st} t-${e.type} ${e.element_id === selectedId ? "sel" : ""}`}
                  x={x0}
                  y={y0}
                  width={Math.max(0.001, x1 - x0)}
                  height={Math.max(0.001, y1 - y0)}
                  vectorEffect="non-scaling-stroke"
                  onClick={() => onSelect(e.element_id)}
                >
                  <title>{e.type}</title>
                </rect>
              );
            })}
          {highlight && (
            <rect
              className="cell-hl"
              x={highlight[0]}
              y={highlight[1]}
              width={highlight[2] - highlight[0]}
              height={highlight[3] - highlight[1]}
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>
      </div>
    </div>
  );
}
