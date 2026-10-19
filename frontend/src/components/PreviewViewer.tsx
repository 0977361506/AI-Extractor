import { useCallback, useEffect, useRef, useState } from "react";
import type { Page } from "../types";

type Cell = { row: number; col: number };

interface Props {
  url: string;
  page: Page;
  selectedId: string | null;
  selectedCell: Cell | null;
  uiThreshold: number;
  onSelect: (id: string, cell: Cell | null) => void;
  zoom?: number;
}

/**
 * Office/HTML files have no page image: the backend renders the original file to HTML where every element
 * block carries `data-el` and every table cell `data-r`/`data-c`. The frame is sandboxed without scripts;
 * `allow-same-origin` only lets this page reach into it to sync selection.
 */
export function PreviewViewer({ url, page, selectedId, selectedCell, uiThreshold, onSelect, zoom = 1 }: Props) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [doc, setDoc] = useState<Document | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;

  const onLoad = useCallback(() => {
    const d = frame.current?.contentDocument ?? null;
    d?.addEventListener("click", (ev) => {
      const target = ev.target as HTMLElement | null;
      const block = target?.closest?.("[data-el]");
      if (!block) return;
      const td = target?.closest?.("td[data-r]");
      const cell = td ? { row: Number(td.getAttribute("data-r")), col: Number(td.getAttribute("data-c")) } : null;
      select.current(block.getAttribute("data-el")!, cell);
    });
    setDoc(d);
  }, []);

  useEffect(() => setDoc(null), [url]);

  useEffect(() => {
    if (!doc) return;
    for (const el of page.elements) {
      const block = doc.querySelector(`[data-el="${el.element_id}"]`);
      block?.classList.toggle("rev", el.needs_human_review || el.confidence_score < uiThreshold);
    }
  }, [doc, page, uiThreshold]);

  useEffect(() => {
    if (!doc) return;
    doc.querySelectorAll(".sel, .cell-hl").forEach((n) => n.classList.remove("sel", "cell-hl"));
    const block = selectedId ? doc.querySelector(`[data-el="${selectedId}"]`) : null;
    if (!block) return;
    block.classList.add("sel");
    const td = selectedCell ? block.querySelector(`td[data-r="${selectedCell.row}"][data-c="${selectedCell.col}"]`) : null;
    td?.classList.add("cell-hl");
    (td ?? block).scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "smooth" });
  }, [doc, selectedId, selectedCell]);

  useEffect(() => {
    if (doc?.body) doc.body.style.zoom = String(zoom);
  }, [doc, zoom]);

  return (
    <div className="page-viewer">
      <iframe ref={frame} className="preview-frame" title={`Bản gốc trang ${page.page_number}`} src={url} sandbox="allow-same-origin" onLoad={onLoad} />
    </div>
  );
}
