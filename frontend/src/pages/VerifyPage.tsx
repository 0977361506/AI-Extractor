import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ElementCard } from "../components/ElementCard";
import { PageViewer } from "../components/PageViewer";
import { useDocumentEvents } from "../hooks/useDocumentEvents";
import { nextIssue } from "../lib/review";
import type { BBox, DocumentDetail, Element, Page } from "../types";

const FINAL = new Set(["COMPLETED", "PARTIAL", "FAILED"]);
const LAYERS: [string, string[]][] = [
  ["Con dấu", ["stamp"]],
  ["Chữ viết tay", ["handwritten_note", "signature"]],
  ["Đầu/chân trang", ["page_header", "page_footer"]],
];

export function VerifyPage({ documentId }: { documentId: string }) {
  const qc = useQueryClient();
  const doc = useQuery({ queryKey: ["doc", documentId], queryFn: () => api.getDocument(documentId) });
  const vlm = useQuery({ queryKey: ["vlm-settings"], queryFn: api.getVlmSettings });
  const uiThreshold = vlm.data?.ui_threshold ?? 0.8;

  const [pageNo, setPageNo] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null);
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [imageKind, setImageKind] = useState<"display" | "ocr">("display");
  const [zoom, setZoom] = useState(1);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState("");

  const running = !!doc.data && !FINAL.has(doc.data.status);
  const progress = useDocumentEvents(
    documentId,
    running,
    () => qc.invalidateQueries({ queryKey: ["doc", documentId] }),
    () => qc.invalidateQueries({ queryKey: ["doc", documentId] }),
  );

  const pages: Page[] = useMemo(() => doc.data?.ast?.pages ?? doc.data?.partial_pages ?? [], [doc.data]);
  const total = doc.data?.ast?.metadata.total_pages ?? doc.data?.total_pages ?? pages.length;
  const page = pages.find((p) => p.page_number === pageNo) ?? pages[0];
  const elements = useMemo(() => [...(page?.elements ?? [])].sort((a, b) => a.reading_order - b.reading_order), [page]);
  const selected = elements.find((e) => e.element_id === selectedId) ?? null;
  const editable = !!doc.data?.ast;

  const highlight: BBox | null = useMemo(() => {
    if (!selected || !selectedCell || selected.type !== "table") return null;
    return selected.cells?.find((c) => c.row === selectedCell.row && c.col === selectedCell.col)?.bbox ?? null;
  }, [selected, selectedCell]);

  const replaceElement = useCallback(
    (updated: Element) => {
      qc.setQueryData<DocumentDetail>(["doc", documentId], (old) => {
        if (!old?.ast) return old;
        return {
          ...old,
          ast: {
            ...old.ast,
            pages: old.ast.pages.map((p) => ({ ...p, elements: p.elements.map((e) => (e.element_id === updated.element_id ? updated : e)) })),
          },
        };
      });
    },
    [qc, documentId],
  );

  const correct = useCallback(
    async (elementId: string, path: string, value: unknown) => {
      if (!editable) {
        setNotice("Tài liệu đang xử lý — chỉ sửa được khi đã xong.");
        return;
      }
      try {
        const { element } = await api.correct(documentId, elementId, path, value);
        replaceElement(element);
        setNotice("");
      } catch (e) {
        setNotice(String(e));
      }
    },
    [documentId, editable, replaceElement],
  );

  const goNext = useCallback(() => {
    const next = nextIssue(pages, selectedId);
    if (next) {
      setPageNo(next.page);
      setSelectedId(next.elementId);
      setSelectedCell(null);
    } else setNotice("Không còn mục cần duyệt 🎉");
  }, [pages, selectedId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        goNext();
      } else if (e.key === "Enter" && selected?.needs_human_review) {
        e.preventDefault();
        correct(selected.element_id, "review", true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, correct, selected]);

  if (doc.isLoading) return <div className="card">Đang tải tài liệu…</div>;
  if (doc.error || !doc.data) return <div className="card error">Không tải được tài liệu: {String(doc.error)}</div>;

  const issues = pages.reduce((n, p) => n + p.elements.filter((e) => e.needs_human_review).length, 0);
  const shown = onlyIssues ? elements.filter((e) => e.needs_human_review) : elements;

  return (
    <div className="verify">
      <div className="verify-bar">
        <strong className="fname">{doc.data.filename}</strong>
        <span className={`status s-${doc.data.status}`}>{doc.data.status}</span>
        {running && progress && (
          <span className="live">
            <span className="bar"><span style={{ width: `${progress.progress_percentage}%` }} /></span> {progress.message_vi}
          </span>
        )}
        <span className="issues">{issues} mục cần duyệt</span>
        <button type="button" onClick={goNext} title="Phím N">Lỗi tiếp theo (N)</button>
        <label className="chip"><input type="checkbox" checked={onlyIssues} onChange={(e) => setOnlyIssues(e.target.checked)} /> Chỉ mục cần duyệt</label>
        <span className="spacer" />
        {editable && (
          <>
            <a className="btn ghost" href={api.exportUrl(documentId, "json")}>JSON</a>
            <a className="btn ghost" href={api.exportUrl(documentId, "md")}>Markdown</a>
            <a className="btn ghost" href={api.exportUrl(documentId, "jsonl")}>Chunks RAG</a>
            <button
              type="button"
              className="primary"
              onClick={async () => setNotice(`Đã lưu nhãn đúng: ${(await api.saveGroundTruth(documentId)).path}`)}
            >
              Lưu làm nhãn đúng
            </button>
          </>
        )}
      </div>
      {notice && <div className="notice">{notice}</div>}

      <div className="split">
        <div className="left">
          <div className="pager">
            {Array.from({ length: total }, (_, i) => i + 1).map((n) => {
              const ready = pages.some((p) => p.page_number === n);
              const failed = pages.find((p) => p.page_number === n)?.status === "FAILED";
              return (
                <button
                  key={n}
                  type="button"
                  disabled={!ready}
                  className={`page-btn ${n === (page?.page_number ?? 1) ? "active" : ""} ${ready ? "" : "pending"} ${failed ? "failed" : ""}`}
                  onClick={() => {
                    setPageNo(n);
                    setSelectedId(null);
                  }}
                >
                  {n}
                </button>
              );
            })}
            <span className="spacer" />
            <select value={imageKind} onChange={(e) => setImageKind(e.target.value as "display" | "ocr")} aria-label="Ảnh">
              <option value="display">Ảnh gốc</option>
              <option value="ocr">Ảnh đã làm sạch</option>
            </select>
            {LAYERS.map(([label, types]) => (
              <label key={label} className="chip">
                <input
                  type="checkbox"
                  checked={!types.some((t) => hidden.has(t))}
                  onChange={(e) => {
                    const next = new Set(hidden);
                    types.forEach((t) => (e.target.checked ? next.delete(t) : next.add(t)));
                    setHidden(next);
                  }}
                />
                {label}
              </label>
            ))}
            <button type="button" className="ghost" onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}>−</button>
            <span>{Math.round(zoom * 100)}%</span>
            <button type="button" className="ghost" onClick={() => setZoom(Math.min(3, zoom + 0.25))}>+</button>
          </div>
          {page ? (
            <PageViewer
              imageUrl={api.imageUrl(documentId, page.page_number, imageKind)}
              page={page}
              selectedId={selectedId}
              uiThreshold={uiThreshold}
              highlight={highlight}
              zoom={zoom}
              hiddenTypes={hidden}
              onSelect={(id) => {
                setSelectedId(id);
                setSelectedCell(null);
              }}
            />
          ) : (
            <div className="skeleton">Trang đang được xử lý…</div>
          )}
          {page?.error && <pre className="error">{page.error}</pre>}
        </div>

        <div className="right">
          {shown.map((el) => (
            <ElementCard
              key={el.element_id}
              el={el}
              selected={el.element_id === selectedId}
              uiThreshold={uiThreshold}
              selectedCell={selectedCell}
              onSelect={() => setSelectedId(el.element_id)}
              onSelectCell={(row, col) => setSelectedCell({ row, col })}
              onCorrect={(path, value) => correct(el.element_id, path, value)}
            />
          ))}
          {!shown.length && <div className="muted pad">{page ? "Không có phần tử." : "Đang chờ trang đầu tiên…"}</div>}
        </div>
      </div>
    </div>
  );
}
