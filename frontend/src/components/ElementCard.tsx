import { useEffect, useRef, useState } from "react";
import { REASON_VI, TYPE_VI, elementStatus } from "../lib/review";
import type { Element, TableCell } from "../types";
import { TableEditor } from "./editors/TableEditor";

interface Props {
  el: Element;
  selected: boolean;
  uiThreshold: number;
  selectedCell: { row: number; col: number } | null;
  onSelect: () => void;
  onSelectCell: (row: number, col: number) => void;
  onCorrect: (path: string, value: unknown) => void;
}

function Mermaid({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
        const { svg } = await mermaid.render(`m${Math.random().toString(36).slice(2)}`, code);
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, [code]);
  return error ? <pre className="error">{error}</pre> : <div className="mermaid" ref={ref} />;
}

function TextBlock({ value, multiline, onSave }: { value: string; multiline?: boolean; onSave: (v: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  if (draft === null)
    return (
      <div className="text-view" title="Nhấp đúp để sửa" onDoubleClick={() => setDraft(value)}>
        {value || <em className="muted">(trống)</em>}
      </div>
    );
  return (
    <div className="text-edit">
      {multiline ? (
        <textarea autoFocus rows={Math.min(10, Math.max(2, draft.split("\n").length + 1))} value={draft} onChange={(e) => setDraft(e.target.value)} />
      ) : (
        <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} />
      )}
      <div className="row-actions">
        <button
          type="button"
          className="primary"
          onClick={() => {
            onSave(draft);
            setDraft(null);
          }}
        >
          Lưu sửa
        </button>
        <button type="button" className="ghost" onClick={() => setDraft(null)}>Hủy</button>
      </div>
    </div>
  );
}

export function ElementCard({ el, selected, uiThreshold, selectedCell, onSelect, onSelectCell, onCorrect }: Props) {
  const status = elementStatus(el, uiThreshold);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [selected]);

  let body: JSX.Element;
  switch (el.type) {
    case "table":
      body = (
        <TableEditor
          cells={el.cells ?? []}
          uiThreshold={uiThreshold}
          selected={selected ? selectedCell : null}
          onSelectCell={(r, c) => {
            onSelect();
            onSelectCell(r, c);
          }}
          onEditCell={(r, c, text) => onCorrect(`cells[${r}][${c}].text`, text)}
          onStructure={(cells: TableCell[]) => onCorrect("cells", cells)}
        />
      );
      break;
    case "form_field":
      body = (
        <div className="kv">
          <TextBlock value={el.label ?? ""} onSave={(v) => onCorrect("label", v)} />
          <TextBlock value={el.value ?? ""} onSave={(v) => onCorrect("value", v)} />
          {el.value_type && <span className="tag">{el.value_type}</span>}
        </div>
      );
      break;
    case "choice_group":
      body = (
        <div className="choices">
          {el.question && <div className="question">{el.question}</div>}
          {(el.options ?? []).map((o, i) => (
            <label key={i} className="choice">
              <input type="checkbox" checked={o.checked} onChange={(e) => onCorrect(`options[${i}].checked`, e.target.checked)} />
              <TextBlock value={o.label} onSave={(v) => onCorrect(`options[${i}].label`, v)} />
            </label>
          ))}
        </div>
      );
      break;
    case "diagram":
      body = (
        <div>
          {el.description && <p className="muted">{el.description}</p>}
          {el.mermaid && <Mermaid code={el.mermaid} />}
          <TextBlock value={el.mermaid ?? ""} multiline onSave={(v) => onCorrect("mermaid", v)} />
        </div>
      );
      break;
    case "stamp":
      body = (
        <div className="info">
          <span className={`dot ${el.color ?? ""}`} /> Dấu {el.shape === "round" ? "tròn" : el.shape === "rectangle" ? "chữ nhật" : ""} {el.color ?? ""}
          <TextBlock value={el.text} onSave={(v) => onCorrect("text", v)} />
        </div>
      );
      break;
    case "signature":
      body = (
        <div className="info">
          ✍ Chữ ký — người ký: <TextBlock value={el.signer_name ?? ""} onSave={(v) => onCorrect("signer_name", v)} />
        </div>
      );
      break;
    case "handwritten_note":
      body = (
        <div className="info">
          {el.description && <span className="muted">{el.description}</span>}
          <TextBlock value={el.text} onSave={(v) => onCorrect("text", v)} />
          {el.attached_to && <span className="tag">gắn với {el.attached_to}</span>}
        </div>
      );
      break;
    case "figure":
      body = (
        <div className="info">
          {el.description && <p className="muted">{el.description}</p>}
          <TextBlock value={el.text} multiline onSave={(v) => onCorrect("text", v)} />
        </div>
      );
      break;
    default:
      body = <TextBlock value={el.text} multiline={el.type === "paragraph" || el.type === "list_item"} onSave={(v) => onCorrect("text", v)} />;
  }

  return (
    <div ref={ref} data-element={el.element_id} className={`element-card st-${status} t-${el.type} ${selected ? "selected" : ""}`} onClick={onSelect}>
      <div className="card-head">
        <span className="type">{TYPE_VI[el.type] ?? el.type}</span>
        {el.type === "heading" && el.level != null && <span className="tag">cấp {el.level}</span>}
        <span className="conf">{(el.confidence_score * 100).toFixed(0)}%</span>
        {el.human_corrected && <span className="tag ok">đã duyệt</span>}
        {el.continues_to && <span className="tag">tiếp trang sau</span>}
        {el.continues_from && <span className="tag">tiếp trang trước</span>}
        {el.review_reasons.map((r) => (
          <span key={r} className="badge">{REASON_VI[r] ?? r}</span>
        ))}
        {el.needs_human_review && (
          <button
            type="button"
            className="confirm"
            title="Xác nhận đúng (Enter)"
            onClick={(e) => {
              e.stopPropagation();
              onCorrect("review", true);
            }}
          >
            ✓ Xác nhận
          </button>
        )}
      </div>
      {el.hierarchy_breadcrumb.length > 0 && <div className="crumb">{el.hierarchy_breadcrumb.join(" › ")}</div>}
      {body}
    </div>
  );
}
