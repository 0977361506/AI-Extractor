import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { useDocumentEvents } from "../hooks/useDocumentEvents";
import type { DocumentRow } from "../types";

const FINAL = new Set(["COMPLETED", "PARTIAL", "FAILED"]);
const STATUS_VI: Record<string, string> = {
  PENDING: "Đang chờ",
  IN_PROGRESS: "Đang xử lý",
  COMPLETED: "Hoàn tất",
  PARTIAL: "Xong một phần",
  FAILED: "Lỗi",
};

function Row({ doc, onOpen, onDelete }: { doc: DocumentRow; onOpen: () => void; onDelete: () => void }) {
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

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setMsg(`Đang tải lên ${files.length} tệp…`);
    try {
      const r = await api.upload(files);
      const errors = r.documents.filter((d) => d.error);
      setMsg(errors.length ? errors.map((d) => `${d.filename}: ${d.error}`).join(" · ") : `Đã tiếp nhận ${r.documents.length} tệp.`);
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
