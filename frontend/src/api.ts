import type { ConnectionTestResult, DocumentDetail, DocumentRow, Element, Page, PageTrace, VlmSettings } from "./types";

const BASE = "/api/v1";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not json */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listDocuments: () => fetch(`${BASE}/documents`).then((r) => json<DocumentRow[]>(r)),
  getDocument: (id: string) => fetch(`${BASE}/documents/${id}`).then((r) => json<DocumentDetail>(r)),
  getPage: (id: string, n: number) => fetch(`${BASE}/documents/${id}/pages/${n}`).then((r) => json<Page>(r)),
  deleteDocument: (id: string) => fetch(`${BASE}/documents/${id}`, { method: "DELETE" }).then((r) => json<unknown>(r)),
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return fetch(`${BASE}/documents`, { method: "POST", body: form }).then((r) =>
      json<{ documents: { document_id?: string; filename: string; status?: string; error?: string }[] }>(r),
    );
  },
  correct: (id: string, element_id: string, path: string, value: unknown) =>
    fetch(`${BASE}/documents/${id}/corrections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ element_id, path, value }),
    }).then((r) => json<{ correction_id: number; element: Element }>(r)),
  saveGroundTruth: (id: string) => fetch(`${BASE}/documents/${id}/ground-truth`, { method: "POST" }).then((r) => json<{ path: string }>(r)),
  imageUrl: (id: string, n: number, kind: "display" | "ocr" | "raw" = "display") => `${BASE}/documents/${id}/pages/${n}/image?kind=${kind}`,
  /** ``null`` when the page has no trace (not started yet, or processed before traces existed). */
  getTrace: (id: string, n: number) =>
    fetch(`${BASE}/documents/${id}/pages/${n}/trace`).then((r) => (r.status === 404 ? null : json<PageTrace>(r))),
  previewUrl:(id: string, n: number) => `${BASE}/documents/${id}/pages/${n}/preview`,
  exportUrl:(id: string, format: "json" | "md" | "jsonl") => `${BASE}/documents/${id}/export?format=${format}`,
  eventsUrl: (id: string) => `${BASE}/documents/${id}/events`,
  getVlmSettings: () => fetch(`${BASE}/settings/vlm`).then((r) => json<VlmSettings>(r)),
  saveVlmSettings: (s: Partial<VlmSettings>) =>
    fetch(`${BASE}/settings/vlm`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(s) }).then((r) =>
      json<VlmSettings>(r),
    ),
  testVlm: (s: Partial<VlmSettings>) =>
    fetch(`${BASE}/settings/vlm/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(s) }).then((r) =>
      json<ConnectionTestResult>(r),
    ),
  vlmTests: () => fetch(`${BASE}/settings/vlm/tests`).then((r) => json<{ id: number; created_at: number; result: ConnectionTestResult }[]>(r)),
  vlmModels: () => fetch(`${BASE}/settings/vlm/models`).then((r) => json<string[]>(r)),
};
