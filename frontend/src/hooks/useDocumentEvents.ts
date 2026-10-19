import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ProgressEvent } from "../types";

const FINAL = new Set(["COMPLETED", "PARTIAL", "FAILED"]);

/** Subscribe to a document's SSE progress stream; ``onPageReady`` fires for progressive rendering. */
export function useDocumentEvents(documentId: string | null, enabled: boolean, onPageReady?: (page: number) => void, onDone?: () => void) {
  const [last, setLast] = useState<ProgressEvent | null>(null);
  const pageCb = useRef(onPageReady);
  const doneCb = useRef(onDone);
  pageCb.current = onPageReady;
  doneCb.current = onDone;

  useEffect(() => {
    if (!documentId || !enabled) return;
    const es = new EventSource(api.eventsUrl(documentId));
    es.addEventListener("progress", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as ProgressEvent;
      setLast(ev);
      if (ev.completed_page_preview?.is_ready) pageCb.current?.(ev.completed_page_preview.page_number);
      if (FINAL.has(ev.status)) doneCb.current?.();
    });
    es.addEventListener("end", () => {
      es.close();
      doneCb.current?.();
    });
    return () => es.close();
  }, [documentId, enabled]);

  return last;
}
