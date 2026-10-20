import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { ProcessView } from "../components/ProcessView";
import { useDocumentEvents } from "../hooks/useDocumentEvents";
import type { DocumentRow } from "../types";

type QueueItem = { id: string; filename: string };

const FINAL = new Set(["COMPLETED", "PARTIAL", "FAILED"]);
const STATUS_VI: Record<string, string> = {
  PENDING: "Đang chờ",
  IN_PROGRESS: "Đang xử lý",
  COMPLETED: "Hoàn tất",
  PARTIAL: "Xong một phần",
  FAILED: "Lỗi",
};

function Row({ doc, onOpen, onProcess, onDelete }: { doc: DocumentRow; onOpen: () => void; onProcess: () => void; onDelete: () => void }) {
  const qc = useQueryClient();
  const live = useDocumentEvents(doc.document_id, !FINAL.has(doc.status), undefined, () => qc.invalidateQueries({ queryKey: ["docs"] }));
  const pct = FINAL.has(doc.status) ? 100 : live?.progress_percentage ?? 0;
  const total = Math.max(doc.total_pages, doc.done_pages);
  return (
    <tr>
      <td>
        <button type="button" className="link" onClick={onOpen}>{doc.filename}</button>
        <div className="muted small">{new Date(doc.created_at * 1000).toLocaleString("vi-VN")}</div>
      </td>
      <td><span className={`status s-${doc.status}`}>{STATUS_VI[doc.status] ?? doc.status}</span></td>
      <td className="progress-cell">
        <span className="bar"><span style={{ width: `${pct}%` }} /></span>
        <div className="muted small">{FINAL.has(doc.status) ? doc.error ?? "" : live?.message_vi ?? "Đang chờ…"}</div>
        {total > 0 && (
          <div className="page-dots" aria-label="Trạng thái từng trang">
            {Array.from({ length: total }, (_, i) => (
              <span key={i} className={i < doc.done_pages ? "done" : "wait"} title={`Trang ${i + 1}`} />
            ))}
          </div>
        )}
      </td>
      <td className="row-actions">
        <button type="button" className="ghost" onClick={onProcess}>Quy trình</button>
        <button type="button" onClick={onOpen}>Đối chiếu</button>
        <button type="button" className="ghost" onClick={onDelete}>Xóa</button>
      </td>
    </tr>
  );
}

export function DocumentListPage({ onOpen }: { onOpen: (id: string) => void }) {
  const qc = useQueryClient();
  const docs = useQuery({ queryKey: ["docs"], queryFn: api.listDocuments, refetchInterval: 4000 });
  const [drag, setDrag] = useState(false);
  const [msg, setMsg] = useState("");
  // files dropped in this session; the active one is shown step by step
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [active, setActive] = useState<string | null>(null);

  const enqueue = (items: QueueItem[]) => {
    if (!items.length) return;
    setQueue((q) => [...q, ...items.filter((it) => !q.some((x) => x.id === it.id))]);
    setActive(items[0].id);
  };

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setMsg(`Đang tải lên ${files.length} tệp…`);
    try {
      const r = await api.upload(files);
      const errors = r.documents.filter((d) => d.error);
      setMsg(errors.length ? errors.map((d) => `${d.filename}: ${d.error}`).join(" · ") : `Đã tiếp nhận ${r.documents.length} tệp.`);
      enqueue(r.documents.filter((d) => d.document_id).map((d) => ({ id: d.document_id!, filename: d.filename })));
      qc.invalidateQueries({ queryKey: ["docs"] });
    } catch (e) {
      setMsg(String(e));
    }
  };

  return (
    <div className="list-page">
      <label
        className={`dropzone ${drag ? "drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          upload(Array.from(e.dataTransfer.files));
        }}
      >
        <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.docx,.pptx,.xlsx,.html,.htm" onChange={(e) => upload(Array.from(e.target.files ?? []))} />
        <strong>Kéo thả hồ sơ vào đây</strong>
        <span>hoặc bấm để chọn — PDF, ảnh scan, DOCX, PPTX, XLSX, HTML (nhiều tệp cùng lúc)</span>
      </label>
      {msg && <div className="notice">{msg}</div>}
      {queue.length > 0 && (
        <ul className="queue" aria-label="Hàng chờ">
          {queue.map((it) => {
            const d = docs.data?.find((x) => x.document_id === it.id);
            const final = !!d && FINAL.has(d.status);
            const pct = final ? 100 : d && d.total_pages ? Math.round((100 * d.done_pages) / d.total_pages) : 0;
            return (
              <li key={it.id}>
                <button type="button" aria-pressed={it.id === active} className={`q-card s-${d?.status ?? "PENDING"}`} onClick={() => setActive(it.id)}>
                  <span className="q-name">{it.filename}</span>
                  <span className="bar"><span style={{ width: `${pct}%` }} /></span>
                  <span className="muted small">{STATUS_VI[d?.status ?? "PENDING"]}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {active && (
        <ProcessView key={active} documentId={active} filename={queue.find((q) => q.id === active)?.filename ?? ""} onOpen={onOpen} />
      )}
      <section className="card">
        <h2>Hồ sơ</h2>
        {docs.data?.length ? (
          <table className="docs">
            <thead>
              <tr><th>Tệp</th><th>Trạng thái</th><th>Tiến độ</th><th /></tr>
            </thead>
            <tbody>
              {docs.data.map((d) => (
                <Row
                  key={d.document_id}
                  doc={d}
                  onOpen={() => onOpen(d.document_id)}
                  onProcess={() => {
                    enqueue([{ id: d.document_id, filename: d.filename }]);
                    window.scrollTo?.({ top: 0, behavior: "smooth" });
                  }}
                  onDelete={async () => {
                    if (confirm(`Xóa ${d.filename}?`)) {
                      await api.deleteDocument(d.document_id);
                      qc.invalidateQueries({ queryKey: ["docs"] });
                    }
                  }}
                />
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">{docs.isLoading ? "Đang tải…" : "Chưa có hồ sơ nào."}</p>
        )}
      </section>
    </div>
  );
}
