import type { StepState } from "../lib/pipeline";

export type StepItem = { id: string; label: string } & StepState;

const ICON: Record<string, string> = { done: "✓", failed: "✕", skipped: "–" };

export function formatMs(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
}

export function Stepper({ steps, selected, onSelect }: { steps: StepItem[]; selected: string | null; onSelect: (id: string) => void }) {
  return (
    <ol className="stepper">
      {steps.map((s, i) => (
        <li key={s.id} className={`st-${s.status}`}>
          <button
            type="button"
            data-status={s.status}
            aria-current={s.id === selected ? "step" : undefined}
            className={s.id === selected ? "sel" : ""}
            disabled={s.status === "pending"}
            title={s.error ?? s.reason ?? undefined}
            onClick={() => onSelect(s.id)}
          >
            <span className="dot" aria-hidden>{ICON[s.status] ?? (s.status === "running" ? "" : i + 1)}</span>
            <span className="lbl">{s.label}</span>
            {s.ms != null && <span className="ms">{formatMs(s.ms)}</span>}
          </button>
        </li>
      ))}
    </ol>
  );
}
