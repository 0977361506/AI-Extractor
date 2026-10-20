import { useEffect, useReducer } from "react";
import { api } from "../api";
import { initialPipeline, reducePipeline } from "../lib/pipeline";
import type { ProgressEvent } from "../types";

/** Stepper state of one document, rebuilt from its SSE stream (the server replays every event from the start). */
export function usePipeline(documentId: string) {
  const [state, dispatch] = useReducer(reducePipeline, initialPipeline);
  useEffect(() => {
    const es = new EventSource(api.eventsUrl(documentId));
    es.addEventListener("progress", (e) => dispatch(JSON.parse((e as MessageEvent).data) as ProgressEvent));
    es.addEventListener("end", () => es.close());
    return () => es.close();
  }, [documentId]);
  return state;
}
