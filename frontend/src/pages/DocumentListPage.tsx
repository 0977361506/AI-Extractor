import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { FileBadge, Seal } from "../components/Marks";
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
const FORMATS = ["PDF", "Ảnh scan", "Word", "Excel", "PowerPoint", "HTML"];

function Row({ doc, onOpen, onProcess, onDelete }: { doc: DocumentRow; onOpen: () => void; onProcess: () => void; onDelete: () => void }) {
  const qc = useQueryClient();
  const live = useDocumentEvents(doc.document_id, !FINAL.has(doc.status), undefined, () => qc.invalidateQueries({ queryKey: ["docs"] }));
  const pct = FINAL.has(doc.status) ? 100 : live?.progress_percentage ?? 0;
  const total = Math.max(doc.total_pages, doc.done_pages);
  return (
    <tr className={`s-${doc.status}`}>
      <td>
        <div className="file-cell">
          <FileBadge filename={doc.filename} />
          <div className="file-meta">
            <button type="button" className="link file-name" onClick={onOpen} title={doc.filename}>{doc.filename}</button>
            <span className="when">{new Date(doc.created_at * 1000).toLocaleString("vi-VN")}</span>
          </div>
        </div>
      </td>
      <td><span className={`status s-${doc.status}`}>{STATUS_VI[doc.status] ?? doc.status}</span></td>
      <td className="progress-cell">
        <div className="progress-line">
          <span className="bar"><span style={{ width: `${pct}%` }} /></span>
          {total > 0 && <span className="pages num">{`${doc.done_pages}/${total} trang`}</span>}
        </div>
        <div className="muted small">{FINAL.has(doc.status) ? doc.error ?? "" : live?.message_vi ?? "Đang chờ…"}</div>
      </td>
      <td className="row-actions">
        <button type="button" className="ghost" onClick={onProcess}>Quy trình</button>
        <button type="button" className="open" onClick={onOpen}>Đối chiếu</button>
        <button type="button" className="ghost danger" onClick={onDelete}>Xóa</button>
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

  const rows = docs.data ?? [];
  const running = rows.filter((d) => !FINAL.has(d.status)).length;
  const failed = rows.filter((d) => d.status === "FAILED").length;

  return (
    <div className={`list-page home ${queue.length ? "has-queue" : ""}`}>
      <section className="intake">
        <div className="intake-copy">
          <h1>Tiếp nhận hồ sơ</h1>
          <p className="lede">Hệ thống đọc từng trang, dựng lại bảng, nhận diện con dấu và chữ ký, rồi chuyển hồ sơ sang bước đối chiếu.</p>
        </div>
        <label
          className={`dropzone tray ${drag ? "drag" : ""}`}
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
          <span className="tray-art" aria-hidden>
            <i />
            <i />
            <i />
          </span>
          <span className="tray-text">
            <strong>{drag ? "Thả để tải lên" : "Kéo thả hồ sơ vào đây"}</strong>
            <span>
              hoặc <span className="pick">chọn tệp từ máy</span> — chọn được nhiều tệp cùng lúc
            </span>
          </span>
          <ul className="formats" aria-label="Định dạng hỗ trợ">
            {FORMATS.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </label>
      </section>

      {msg && <div className="notice" role="status">{msg}</div>}

      {queue.length > 0 && (
        <ul className="queue" aria-label="Hàng chờ">
          {queue.map((it) => {
            const d = docs.data?.find((x) => x.document_id === it.id);
            const status = d?.status ?? "PENDING";
            const final = FINAL.has(status);
            const pct = final ? 100 : d && d.total_pages ? Math.round((100 * d.done_pages) / d.total_pages) : 0;
            return (
              <li key={it.id}>
                <button type="button" aria-pressed={it.id === active} className={`q-card s-${status}`} onClick={() => setActive(it.id)}>
                  <span className="q-top">
                    <FileBadge filename={it.filename} />
                    <span className="q-name" title={it.filename}>{it.filename}</span>
                  </span>
                  <span className="bar"><span style={{ width: `${pct}%` }} /></span>
                  <span className="q-status">{STATUS_VI[status]}</span>
                  {status === "COMPLETED" && <Seal />}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {active && (
        <ProcessView key={active} documentId={active} filename={queue.find((q) => q.id === active)?.filename ?? ""} onOpen={onOpen} />
      )}

      <section className="card docs-card">
        <header className="docs-head">
          <h2>Hồ sơ đã tải lên</h2>
          {rows.length > 0 && (
            <span className="muted small">
              {`${rows.length} hồ sơ`}
              {running > 0 && ` · ${running} đang xử lý`}
              {failed > 0 && ` · ${failed} lỗi`}
            </span>
          )}
        </header>
        {rows.length ? (
          <table className="docs">
            <thead>
              <tr><th>Tệp</th><th>Trạng thái</th><th>Tiến độ</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((d) => (
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
          <p className="empty">{docs.isLoading ? "Đang tải danh sách…" : "Chưa có hồ sơ nào. Kéo tệp vào khung phía trên để bắt đầu."}</p>
        )}
      </section>
    </div>
  );
}
