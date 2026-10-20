import { type ReactNode, useEffect, useState } from "react";
import { api } from "../api";
import type { BBox, PageTrace } from "../types";
import { formatMs, type StepItem } from "./Stepper";

const LABEL_VI: Record<string, string> = {
  title: "Tiêu đề", section_header: "Đề mục", text: "Đoạn văn", list_item: "Danh sách", table: "Bảng", picture: "Hình",
  caption: "Chú thích", page_header: "Đầu trang", page_footer: "Chân trang", footnote: "Chú thích chân", formula: "Công thức",
  checkbox_selected: "Ô đã chọn", checkbox_unselected: "Ô trống", form: "Biểu mẫu", key_value_region: "Cặp khóa–giá trị",
  code: "Mã", document_index: "Mục lục",
};
const KIND_VI: Record<string, string> = { pdf: "PDF", image: "Ảnh scan", docx: "Word", pptx: "PowerPoint", xlsx: "Excel", html: "HTML" };
const INK_VI: Record<string, string> = { stamp: "Con dấu", mark: "Đánh dấu", handwriting: "Chữ viết tay" };
const LOW = 0.8;
const DETAIL_KEY = "idp.stepper.detail";

interface Props {
  documentId: string;
  page: number;
  step: StepItem;
  trace: PageTrace | null;
  traceMissing: boolean;
  onOpenVerify: () => void;
  native?: boolean;
}

function readDetail(): boolean {
  try {
    return localStorage.getItem(DETAIL_KEY) === "1";
  } catch {
    return false;
  }
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

function Overlay({ src, aspect, children }: { src: string; aspect: number; children: ReactNode }) {
  return (
    <div className="trace-canvas" style={{ paddingTop: `${aspect * 100}%` }}>
      <img src={src} alt="Trang" draggable={false} />
      <svg viewBox="0 0 1 1" preserveAspectRatio="none">{children}</svg>
    </div>
  );
}

function Box({ b, className, title }: { b: BBox; className: string; title?: string }) {
  return (
    <rect className={className} x={b[0]} y={b[1]} width={Math.max(0.001, b[2] - b[0])} height={Math.max(0.001, b[3] - b[1])} vectorEffect="non-scaling-stroke">
      {title && <title>{title}</title>}
    </rect>
  );
}

function Facts({ items }: { items: [ReactNode, string][] }) {
  return (
    <ul className="facts">
      {items.map(([v, label]) => (
        <li key={label}>
          <b>{v}</b> {label}
        </li>
      ))}
    </ul>
  );
}

export function StepPanel({ documentId, page, step, trace, traceMissing, onOpenVerify, native }: Props) {
  const [detail, setDetail] = useState(readDetail);
  const toggle = (on: boolean) => {
    setDetail(on);
    try {
      localStorage.setItem(DETAIL_KEY, on ? "1" : "0");
    } catch {
      /* per-viewer convenience only */
    }
  };
  const data = trace?.steps[step.id];
  // free-form numbers / strings per step (see backend idp/pipeline/page.py _trace_*)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const s = (step.summary ?? data?.summary ?? {}) as Record<string, any>;
  const pre = trace?.steps.preprocess?.summary as { width?: number; height?: number } | undefined;
  const aspect = pre?.width && pre?.height ? pre.height / pre.width : 1.414;
  const img = (kind: "raw" | "display" | "ocr") => api.imageUrl(documentId, page, kind);
  const pageLevel = !["ingest", "parse", "assemble"].includes(step.id);

  let body: ReactNode = null;
  if (pageLevel && traceMissing) {
    body = (
      <div className="fallback">
        <p>Trang này chưa có dữ liệu từng bước — hồ sơ được xử lý trước khi có tính năng này.</p>
        <button type="button" className="primary" onClick={onOpenVerify}>Mở đối chiếu →</button>
      </div>
    );
  } else if (step.id === "ingest") {
    body = <Facts items={[[KIND_VI[String(s.kind)] ?? String(s.kind ?? "—"), "loại tệp"], [s.pages || "—", "trang"], [s.size_bytes ? `${Math.round(Number(s.size_bytes) / 1024)} KB` : "—", "dung lượng"]]} />;
  } else if (step.id === "parse") {
    body = (
      <>
        <Facts items={[[s.pages ?? "—", native ? "trang / sheet" : "trang"], [s.elements ?? "—", "phần tử đọc được"]]} />
        {step.status === "done" && <iframe className="preview-frame small" title="Bản gốc" src={api.previewUrl(documentId, page)} sandbox="allow-same-origin" />}
      </>
    );
  } else if (step.id === "preprocess" && step.status !== "skipped") {
    body = data?.status === "done" && (
      <>
        <p className="muted">{`xoay ${s.rotation ?? 0}° · lệch ${String(s.skew ?? 0).replace(".", ",")}°`}</p>
        <div className="compare">
          <figure><img src={img("raw")} alt="Ảnh gốc" /><figcaption>Ảnh gốc</figcaption></figure>
          <figure><img src={img("display")} alt="Đã xoay thẳng" /><figcaption>Đã xoay thẳng</figcaption></figure>
          {detail && <figure><img src={img("ocr")} alt="Ảnh làm sạch" /><figcaption>Làm sạch cho OCR (bỏ màu dấu, vệt sọc)</figcaption></figure>}
        </div>
      </>
    );
  } else if (step.id === "layout" && data?.regions) {
    const byLabel = (s.by_label ?? {}) as Record<string, number>;
    body = (
      <>
        <Facts items={[[s.regions ?? data.regions.length, "vùng bố cục"], [s.text_boxes ?? 0, "dòng chữ phát hiện"]]} />
        <ul className="legend">{Object.entries(byLabel).map(([k, v]) => <li key={k} className={`l-${k}`}>{`${LABEL_VI[k] ?? k}: ${v}`}</li>)}</ul>
        <Overlay src={img("display")} aspect={aspect}>
          {detail && data.text_boxes?.map((b, i) => <Box key={`t${i}`} b={b} className="tbox" />)}
          {data.regions.map((r, i) => <Box key={i} b={r.bbox} className={`region l-${r.label}`} title={`${LABEL_VI[r.label] ?? r.label} · ${pct(r.score)}`} />)}
        </Overlay>
      </>
    );
  } else if (step.id === "tables" && data?.tables) {
    body = (
      <>
        <Facts items={[[s.tables ?? 0, "bảng"], [s.cells ?? 0, "ô"], [s.check_failed ?? 0, "ô lệch kiểm tra số học"]]} />
        <Overlay src={img("display")} aspect={aspect}>
          {data.tables.map((t, i) => <Box key={`t${i}`} b={t.bbox} className="tbl" />)}
          {data.tables.flatMap((t, i) =>
            t.cells.filter((c) => c.bbox).map((c) => (
              <Box key={`${i}-${c.row}-${c.col}`} b={c.bbox!} className={`cell ${c.check_failed ? "bad" : ""}`} title={`${c.text} · ${pct(c.conf)}`} />
            )),
          )}
        </Overlay>
        {detail && (
          <ul className="list">
            {data.tables.flatMap((t) => t.cells.filter((c) => c.check_failed)).map((c) => (
              <li key={`${c.row}-${c.col}`} className="bad">{`Hàng ${c.row + 1}, cột ${c.col + 1}: ${c.text}`}</li>
            ))}
          </ul>
        )}
      </>
    );
  } else if (step.id === "ocr" && data?.lines) {
    body = (
      <>
        <Facts items={[[s.lines ?? data.lines.length, "dòng"], [s.mean_conf != null ? pct(Number(s.mean_conf)) : "—", "độ tin cậy TB"], [s.low_conf ?? 0, "dòng tin cậy thấp"]]} />
        <Overlay src={img("display")} aspect={aspect}>
          {data.lines.map((ln, i) => <Box key={i} b={ln.bbox} className={`line ${ln.conf < LOW ? "low" : ""}`} title={`${ln.text} · ${pct(ln.conf)}`} />)}
        </Overlay>
        {detail && (
          <table className="lines">
            <tbody>
              {data.lines.map((ln, i) => (
                <tr key={i} className={ln.conf < LOW ? "low" : ""}>
                  <td>{ln.text}</td>
                  <td className="num">{pct(ln.conf)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </>
    );
  } else if (step.id === "marks" && data?.ink) {
    body = (
      <>
        <Facts items={[[s.stamps ?? 0, "con dấu"], [s.signatures ?? 0, "chữ ký"], [s.handwriting ?? 0, "ghi chú tay"], [s.checkbox_groups ?? 0, "nhóm checkbox"], [s.elements ?? 0, "phần tử"], [s.needs_review ?? 0, "cần duyệt"]]} />
        <Overlay src={img("display")} aspect={aspect}>
          {data.ink.map((b, i) => <Box key={i} b={b.bbox} className={`ink k-${b.kind}`} title={`${INK_VI[b.kind] ?? b.kind} (${b.color})${b.text ? ` · ${b.text}` : ""}`} />)}
        </Overlay>
      </>
    );
  } else if (step.id === "vlm" && step.status === "done") {
    const changes = data?.changes ?? [];
    body = (
      <>
        <Facts items={[[s.calls ?? 0, "lần gọi AI"], [s.cache_hits ?? 0, "dùng lại kết quả"], [s.changed ?? changes.length, "chỗ được sửa"]]} />
        {Number(s.failed) > 0 && <p className="warn">{`${s.failed} vùng không gọi được AI — đã đánh dấu cần duyệt.`}</p>}
        {changes.length ? (
          <ul className="diff">
            {changes.map((c, i) => (
              <li key={i}>
                <del>{c.before}</del> → <ins>{c.after}</ins>
                {c.cell && <span className="muted">{` (ô ${c.cell[0] + 1},${c.cell[1] + 1})`}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">AI không thay đổi nội dung nào.</p>
        )}
      </>
    );
  } else if (step.id === "assemble" && step.status === "done") {
    body = <Assemble documentId={documentId} s={s} detail={detail} onOpenVerify={onOpenVerify} />;
  } else if (step.status === "running") {
    body = <div className="skeleton">Đang chạy…</div>;
  }

  return (
    <section className="step-panel">
      <header>
        <h3>{step.label}</h3>
        <span className={`pill st-${step.status}`}>{STATUS_VI[step.status]}</span>
        {step.ms != null && <span className="muted">{formatMs(step.ms)}</span>}
        <span className="spacer" />
        <label className="chip">
          <input type="checkbox" checked={detail} onChange={(e) => toggle(e.target.checked)} /> Chi tiết
        </label>
      </header>
      {step.status === "failed" && (
        <div role="alert" className="error">
          {step.error ?? data?.error ?? "Bước này bị lỗi"}
        </div>
      )}
      {step.status === "skipped" && <p className="muted">{`Bỏ qua: ${step.reason ?? data?.reason ?? ""}`}</p>}
      {body}
    </section>
  );
}

const STATUS_VI: Record<string, string> = { pending: "Chờ", running: "Đang chạy", done: "Xong", skipped: "Bỏ qua", failed: "Lỗi" };

function Assemble({ documentId, s, detail, onOpenVerify }: { documentId: string; s: Record<string, unknown>; detail: boolean; onOpenVerify: () => void }) {
  const [md, setMd] = useState<string | null>(null);
  useEffect(() => {
    if (!detail || md !== null) return;
    fetch(api.exportUrl(documentId, "md"))
      .then((r) => (r.ok ? r.text() : ""))
      .then(setMd)
      .catch(() => setMd(""));
  }, [detail, documentId, md]);
  return (
    <>
      <Facts items={[[String(s.pages ?? "—"), "trang"], [String(s.elements ?? "—"), "phần tử"], [String(s.chunks ?? "—"), "chunk RAG"]]} />
      <p className={Number(s.needs_review) ? "warn" : "ok"}>
        {Number(s.needs_review) ? `${s.needs_review} mục cần duyệt` : "Không có mục nào cần duyệt"}
      </p>
      <button type="button" className="primary" onClick={onOpenVerify}>Mở đối chiếu →</button>
      {detail && md && <pre className="md-preview">{md}</pre>}
    </>
  );
}
