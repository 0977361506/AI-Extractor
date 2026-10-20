// Mirrors backend/idp/core/ast.py (Unified Document AST).
export type BBox = [number, number, number, number];

export type ElementType =
  | "title" | "heading" | "paragraph" | "list_item" | "caption" | "page_header" | "page_footer"
  | "formula" | "figure" | "table" | "form_field" | "choice_group" | "diagram" | "stamp"
  | "signature" | "handwritten_note";

export interface TableCell {
  row: number;
  col: number;
  rowspan: number;
  colspan: number;
  is_header: boolean;
  text: string;
  numeric_value?: number | null;
  bbox?: BBox | null;
  confidence: number;
  check_failed: boolean;
  alt_text?: string | null;
}

export interface ChoiceOption {
  label: string;
  checked: boolean;
  bbox?: BBox | null;
  confidence: number;
}

export interface Element {
  element_id: string;
  type: ElementType;
  reading_order: number;
  bbox_normalized?: BBox | null;
  hierarchy_breadcrumb: string[];
  text: string;
  content_markdown: string;
  confidence_score: number;
  needs_human_review: boolean;
  review_reasons: string[];
  extraction_engine: string;
  human_corrected: boolean;
  level?: number | null;
  cells?: TableCell[];
  content_html?: string | null;
  continues_from?: string | null;
  continues_to?: string | null;
  label?: string | null;
  value?: string | null;
  value_type?: string | null;
  is_handwritten?: boolean;
  question?: string | null;
  multi_select?: boolean;
  options?: ChoiceOption[];
  mermaid?: string | null;
  description?: string | null;
  color?: string | null;
  shape?: string | null;
  signer_name?: string | null;
  ink_color?: string | null;
  attached_to?: string | null;
}

export interface Page {
  page_number: number;
  status: string;
  width: number;
  height: number;
  orientation_applied: number;
  deskew_angle: number;
  elements: Element[];
  error?: string | null;
}

export interface Document {
  document_id: string;
  job_id: string;
  status: string;
  metadata: { filename: string; file_type?: string; total_pages: number; has_red_stamp: boolean; processing_time_ms: number; vlm_invocations_count: number };
  pages: Page[];
}

export interface DocumentRow {
  document_id: string;
  job_id: string;
  filename: string;
  status: string;
  total_pages: number;
  done_pages: number;
  error?: string | null;
  created_at: number;
}

export interface DocumentDetail extends DocumentRow {
  ast: Document | null;
  partial_pages: Page[];
}

export interface ProgressEvent {
  event_id?: number;
  status: string;
  progress_percentage: number;
  current_stage?: string;
  message_vi: string;
  completed_page_preview?: { page_number: number; is_ready: boolean; api_fetch_url: string };
  plan?: { kind: string; total_pages: number | null; steps: string[] };
  step?: StepEvent;
}

export type StepStatus = "pending" | "running" | "done" | "skipped" | "failed";

export interface StepEvent {
  page: number | null;
  step: string;
  status: StepStatus;
  ms?: number;
  summary?: Record<string, unknown>;
  error?: string;
  reason?: string;
}

export interface TraceBox {
  bbox: BBox;
}

/** backend pages/N_trace.json: per-step results; boxes are normalised to the display image. */
export interface PageTrace {
  page: number;
  steps: Record<
    string,
    {
      status: StepStatus;
      ms?: number;
      summary?: Record<string, unknown>;
      error?: string;
      reason?: string;
      regions?: { label: string; score: number; bbox: BBox }[];
      text_boxes?: BBox[];
      tables?: { bbox: BBox; cells: { row: number; col: number; text: string; conf: number; bbox: BBox | null; check_failed: boolean }[] }[];
      lines?: { text: string; conf: number; bbox: BBox; source: string }[];
      ink?: { kind: string; color: string; bbox: BBox; text: string }[];
      changes?: { element_id: string; cell?: [number, number]; before: string; after: string }[];
    }
  >;
}

export interface VlmSettings {
  enabled: boolean;
  base_url: string;
  api_key: string;
  api_key_set?: boolean;
  headers: Record<string, string>;
  verify_ssl: boolean;
  ca_bundle: string;
  proxy: string;
  model: string;
  temperature: number;
  max_tokens: number;
  structured_output: "auto" | "json_schema" | "guided_json" | "prompt_only";
  detected_mode?: string | null;
  timeout_s: number;
  max_concurrency: number;
  retries: number;
  max_image_side: number;
  vlm_threshold: number;
  ui_threshold: number;
  always_types: string[];
  max_calls_per_page: number;
}

export interface TestStep {
  name: string;
  ok: boolean;
  latency_ms: number;
  detail: string;
  hint: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  steps: TestStep[];
  detected_mode: string | null;
  recommended_concurrency: number;
}
