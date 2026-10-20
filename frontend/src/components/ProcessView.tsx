import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { usePipeline } from "../hooks/usePipeline";
import { progressOf, stepsForPage, type PipelineState } from "../lib/pipeline";
import { FileBadge, Seal } from "./Marks";
import { StepPanel } from "./StepPanel";
import { Stepper } from "./Stepper";

const STATUS_VI: Record<string, string> = {
  PENDING: "Đang chờ", IN_PROGRESS: "Đang xử lý", COMPLETED: "Hoàn tất", PARTIAL: "Xong một phần", FAILED: "Lỗi",
};

function pageState(p: PipelineState, n: number): string {
  const st = Object.values(p.pages[n] ?? {}).map((s) => s.status);
  if (st.includes("failed")) return "failed";
  if (st.includes("running")) return "running";
  return st.length && st.every((s) => s !== "pending") ? "done" : st.length ? "running" : "wait";
}

/** Live, step-by-step view of one document: stepper on top, the selected step's result below. */
export function ProcessView({ documentId, filename, onOpen }: { documentId: string; filename: string; onOpen: (id: string) => void }) {
  const p = usePipeline(documentId);
  const [pageChoice, setPageChoice] = useState<number | null>(null);
  const [stepChoice, setStepChoice] = useState<string | null>(null);

  const native = p.plan?.steps.includes("parse") ?? false;
  const total = p.plan?.total_pages ?? (Number(p.doc.parse?.summary?.pages) || 1);
  const page = Math.min(pageChoice ?? p.focus?.page ?? 1, Math.max(1, total));
  const steps = stepsForPage(p, page);
  const stepId = stepChoice ?? p.focus?.step ?? steps.find((s) => s.status !== "pending")?.id ?? steps[0]?.id;
  const step = steps.find((s) => s.id === stepId);
  const version = steps.map((s) => s.status).join(",");

  const trace = useQuery({
    queryKey: ["trace", documentId, page, version],
    queryFn: () => api.getTrace(documentId, page),
    enabled: !!p.plan && !native,
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[2] === page ? prev : undefined),
  });
  const following = pageChoice == null && stepChoice == null;

  return (
    <section className="card process">
      <div className="process-head">
        <FileBadge filename={filename} />
        <strong className="fname">{filename}</strong>
        <span className={`status s-${p.status}`}>{STATUS_VI[p.status] ?? p.status}</span>
        <span className="bar"><span style={{ width: `${progressOf(p)}%` }} /></span>
        <span className="pct num">{`${progressOf(p)}%`}</span>
        <span className="muted small msg">{p.message}</span>
        <span className="spacer" />
        {!following && !p.final && (
          <button type="button" className="ghost" onClick={() => { setPageChoice(null); setStepChoice(null); }}>
            Theo dõi bước đang chạy
          </button>
        )}
        {p.final && p.status === "COMPLETED" && <Seal />}
      </div>

      {!p.plan ? (
        p.final ? (
          <div className="fallback">
            <p>Hồ sơ này được xử lý trước khi có quy trình từng bước — chỉ xem được kết quả cuối.</p>
            <button type="button" className="primary" onClick={() => onOpen(documentId)}>Mở đối chiếu →</button>
          </div>
        ) : (
          <div className="skeleton">Đang chờ bắt đầu xử lý…</div>
        )
      ) : (
        <>
          <Stepper steps={steps} selected={stepId ?? null} onSelect={setStepChoice} />
          {total > 1 && (
            <div className="pager">
              {Array.from({ length: total }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-label={`Trang ${n}`}
                  className={`page-btn ${n === page ? "active" : ""} ps-${pageState(p, n)}`}
                  onClick={() => setPageChoice(n)}
                >
                  {n}
                </button>
              ))}
            </div>
          )}
          {step && (
            <StepPanel
              documentId={documentId}
              page={page}
              step={step}
              trace={trace.data ?? null}
              traceMissing={trace.data === null && p.final}
              native={native}
              onOpenVerify={() => onOpen(documentId)}
            />
          )}
        </>
      )}
    </section>
  );
}
