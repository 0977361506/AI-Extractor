# Thiết kế: Banking IDP Engine — Giai đoạn 1 (Local, ưu tiên chất lượng)

**Ngày:** 2026-10-19
**Trạng thái:** Đã duyệt
**Tài liệu gốc:** `01_BRD_Banking_IDP.md`, `02_Architecture_Design.md`, `03_Data_Contracts_and_Schemas.md`, `04_Epics_and_User_Stories.md`

---

## 0. Bối cảnh & Ràng buộc đã chốt

| Chủ đề | Quyết định |
|---|---|
| Mục tiêu giai đoạn 1 | **Chất lượng trích xuất** trên hồ sơ scan bẩn; chạy được trên máy dev |
| Kafka | **Không dùng.** Một tiến trình FastAPI + process pool; ranh giới các khâu khớp với topic trong tài liệu 02 để cắm Kafka sau |
| Phần cứng dev | i5-9300H (4C/8T), 16GB RAM, GTX 1050 3GB (không dùng cho AI) → **chạy CPU** |
| Python | **3.13** của máy, trong virtualenv riêng `.venv` |
| VLM | **Gọi LLM Gateway MB** (OpenAI-compatible `/v1/chat/completions`, ảnh base64 `image_url`). Không chạy model VLM local |
| Lưu trữ | **File trên đĩa + SQLite**, qua interface `Storage` / `JobStore` |
| UI | **React đầy đủ** (đối chiếu split-screen, sửa bảng, progressive rendering) + **màn hình Cài đặt VLM có test connection** |
| Đăng nhập / phân quyền | **Không có** |
| Dữ liệu đánh giá | 13 trang mẫu `docs/examples/` (gán nhãn tay qua UI) + bộ sinh dữ liệu tổng hợp |

### Điều chỉnh so với tài liệu gốc

1. **pypdfium2 thay PyMuPDF** — PyMuPDF là AGPL, vi phạm ràng buộc giấy phép của BRD.
2. **Không dùng pHash cho cache VLM** — pHash coi hai bảng cùng mẫu khác số là trùng → trả sai số liệu. Dùng **SHA-256** của ảnh crop + phiên bản prompt + model.
3. **Tách mực đa màu** (đỏ, xanh, nâu/vết ố) thay cho chỉ lọc HSV đỏ — bộ mẫu có dấu xanh, vòng bút đỏ khoanh số, vết ố.
4. **Nhận diện hướng trang 0/90/180/270** — bộ mẫu có trang bảng in ngang.
5. **Thêm phần tử** `form_field`, `choice_group`, `diagram`, `stamp`, `signature`, `handwritten_note` vào AST.
6. **Chunk RAG chuyển lên cấp tài liệu** kèm `source_refs[]`.
7. **Ngưỡng tách bạch:** ngưỡng gửi VLM (mặc định 0.90) và ngưỡng tô vàng UI (0.80, theo FR-06), đều cấu hình được.
8. Khi triển khai server sau này: MinIO (AGPL) → SeaweedFS/Ceph; Redis ≥7.4 → Valkey.

### Đặc điểm bộ mẫu (13 trang, tất cả là ảnh scan, không có text layer)

Dấu tròn đỏ/xanh đè chữ ký; dấu chữ nhật đỏ; vòng bút đỏ khoanh số; vết ố nâu đè số liệu; trang xoay 90°; bảng kéo dài qua trang không lặp header; bảng BCTC header nhiều tầng, rowspan, dòng tổng in đậm, số âm trong ngoặc; chữ viết tay xanh (ghi chú, điền form, chữ ký); biểu mẫu có ô kẻ từng ký tự, checkbox, radio; sơ đồ quy trình; nhiễu scan (chấm bẩn, sọc dọc, nếp gấp, bóng tối, hơi nghiêng).

---

## 1. Kiến trúc tổng thể

```
[React UI] ──upload/REST/SSE──► [FastAPI]
                                   │
                         ┌─────────┴──────────┐
                         ▼                    ▼
                  [JobStore: SQLite]   [EventBus nội bộ] ──► SSE (sự kiện lưu SQLite → reconnect được replay)
                         │
                  [Orchestrator (asyncio)]
                         │  tách trang, chạy song song
                         ▼
          [ProcessPool: N worker CPU (mặc định 2)]  — mỗi worker nạp model 1 lần
           preprocess → layout → table → OCR
                         │ vùng khó
                         ▼
          [VlmClient async] ──HTTP──► LLM Gateway MB  (semaphore, retry, circuit breaker)
                         │
                  [Assembler] gom trang → ghép bảng qua trang → breadcrumb → chunk RAG
                         │
                  [Storage: đĩa]  data/{doc_id}/raw|pages|cleaned|crops|ast.json|doc.md
```

### Cấu trúc thư mục

```
mb-ocr/
├─ backend/
│  ├─ pyproject.toml
│  └─ idp/
│     ├─ api/            FastAPI: upload, documents, pages, SSE, corrections, settings, export
│     ├─ core/           AST (Pydantic), config, interface từng khâu
│     ├─ ingest/         phân loại file; Office fast-path; PDF→ảnh (pypdfium2); VNI/TCVN3
│     ├─ preprocess/     orientation, deskew, crop, chuẩn hóa sáng, tách mực màu
│     ├─ layout/         engine bố cục (Docling | PP-DocLayout)
│     ├─ table/          engine bảng (TableFormer | Paddle) + kiểm tra số học
│     ├─ ocr/            detector (PaddleOCR/RapidOCR) + recognizer (VietOCR | PP-OCRv5)
│     ├─ vlm/            client gateway, prompts, schema đầu ra, cache, test connection
│     ├─ router/         luật định tuyến vùng sang VLM
│     ├─ assemble/       reading order, breadcrumb, ghép bảng, hậu xử lý số/NFC, chunker
│     ├─ storage/        Storage (đĩa)
│     ├─ jobs/           JobStore (SQLite), orchestrator, worker pool, event bus
│     └─ cli.py          idp process | idp eval | idp synth | idp serve
├─ frontend/             React + Vite + TypeScript
├─ eval/
│  ├─ ground_truth/      nhãn đúng (AST đã duyệt)
│  ├─ synth/             template + bộ làm nhiễu
│  └─ reports/
└─ docs/
```

### Sẵn sàng chuyển Kafka

| Ranh giới nội bộ | Topic tương ứng (tài liệu 02) |
|---|---|
| Upload → Orchestrator | `doc.ingestion` |
| Preprocess → Layout/OCR | `page.layout_ocr` |
| Router → VlmClient | `region.vlm_heavy` |
| Page done → Assembler | `doc.assembly` |
| EventBus | `job.progress_events` |

Message giữa các khâu dùng đúng payload trong tài liệu 03.

---

## 2. Schema AST

Kế thừa tài liệu 03; mọi chuỗi chuẩn hóa **Unicode NFC**.

### Document
- `document_id`, `job_id`, `status` (`PENDING|IN_PROGRESS|COMPLETED|PARTIAL|FAILED`)
- `metadata`: filename, file_type, total_pages, detected_charset, has_red_stamp, processing_time_ms, vlm_invocations_count, engine_versions
- `pages[]`, `logical_tables[]`, `chunks[]`

### Page
- `page_number`, `dimensions`, `status`
- `images`: `raw_uri`, `display_uri` (đã xoay hướng + deskew, giữ màu), `ocr_uri` (đã làm sạch, tách mực)
- `orientation_applied` (0/90/180/270), `deskew_angle`
- `elements[]`
- **Mọi `bbox_normalized` = `[x0, y0, x1, y1]` trong [0,1] theo ảnh `display`.**

### Element — trường chung
`element_id`, `type`, `reading_order`, `bbox_normalized`, `hierarchy_breadcrumb[]`, `content_markdown`, `text`, `confidence_score`, `needs_human_review`, `review_reasons[]`, `extraction_engine`, `human_corrected`, `lines[]` (`text`, `bbox`, `confidence`).

### Kiểu element

| `type` | Trường riêng |
|---|---|
| `title`, `heading` | `level` |
| `paragraph`, `list_item`, `caption`, `page_header`, `page_footer`, `formula` (`latex`), `figure` | — |
| `table` | `cells[]`: `row`, `col`, `rowspan`, `colspan`, `is_header`, `text`, `numeric_value?`, `bbox`, `confidence`, `check_failed?`; `content_html`/`content_markdown` sinh từ `cells`; `continues_from?`, `continues_to?` |
| `form_field` | `label`, `value`, `value_type` (`text|date|id_number|phone|email|number`), `bbox_label`, `bbox_value`, `is_handwritten` |
| `choice_group` | `question`, `multi_select`, `options[]`: `label`, `checked`, `bbox`, `confidence` |
| `diagram` | `mermaid`, `description` |
| `stamp` | `color`, `shape`, `text` |
| `signature` | `signer_name?` |
| `handwritten_note` | `text`, `ink_color`, `attached_to?` (element_id) |

Số tiền: giữ chuỗi gốc (`"(1.290)"`) + `numeric_value` (`-1290`).

### Logical table (cấp tài liệu)
`logical_table_id`, `header_rows`, `cells[]` (đã ghép), `content_html`, `content_markdown`, `parts[]`: `page_number`, `element_id`, `row_range`.

### Chunk RAG (cấp tài liệu)
`chunk_id`, `type` (`text|table`), `breadcrumb[]`, `text` (tiền tố `[Bối cảnh: ...]`, bảng lặp header cột), `source_refs[]`: `page_number`, `element_id`, `bbox`.

### Corrections (audit trail)
Bảng SQLite riêng, **không ghi đè output engine**: `id`, `document_id`, `element_id`, `path` (vd `cells[3][2].text`), `old_value`, `new_value`, `editor`, `created_at`. Export AST áp corrections và đặt `human_corrected = true`. Bản đã duyệt = nhãn đúng cho eval.

### Review reasons (mã + nhãn tiếng Việt)
`LOW_CONFIDENCE`, `STAMP_OVERLAP`, `INK_OVERLAP`, `HANDWRITING`, `OCR_VLM_MISMATCH`, `ARITHMETIC_CHECK_FAILED`, `TABLE_STRUCTURE_INVALID`, `VLM_UNAVAILABLE`, `VLM_OUTPUT_INVALID`.

---

## 3. Pipeline xử lý

### Bước 0 — Tiếp nhận
- Nhận diện loại file bằng magic bytes.
- DOCX/PPTX/HTML → Docling native backend; XLSX → `python-calamine` (+ openpyxl cho merged ranges). Không OCR, `bbox = null`.
- PDF: kiểm tra text layer từng trang (pypdfium2). Unicode sạch → trích trực tiếp; VNI/TCVN3 → chuyển mã; glyph hỏng hoặc không có text → render 300 DPI → OCR.
- Ảnh/TIFF nhiều trang → tách trang.

### Bước 1 — Tiền xử lý (OpenCV)
1. **Orientation 0/90/180/270:** PP-LCNet doc orientation classifier (ONNX).
2. **Deskew** (±45°) bằng phân tích dòng text; crop viền/nền.
3. **Chuẩn hóa sáng:** chia cho nền đã blur (khử bóng); lọc chấm bẩn theo diện tích connected component; khử sọc dọc.
4. **Tách mực:** phân loại pixel thành đen-in / đỏ / xanh / nâu-vàng.
   - Ảnh `ocr`: giữ mực đen; vùng chữ đen bị mực màu đè được khôi phục từ kênh màu bổ trợ (vd kênh R cho dấu đỏ).
   - **Mực màu không bị vứt:** mỗi vùng mực màu thành ứng viên `handwritten_note` / `stamp` (theo màu + hình tròn/chữ nhật) / giá trị `form_field`.

### Bước 2 — Bố cục
Docling layout → vùng text/table/figure/title/header/footer. Hợp nhất với vùng tự phát hiện: stamp, mực viết tay, **checkbox/radio** (contour vuông/tròn nhỏ + tỉ lệ tô), ô kẻ từng ký tự.

### Bước 3 — Trích xuất theo vùng
- **Chữ in:** PaddleOCR detector (qua RapidOCR/ONNX) → VietOCR recognizer theo dòng. Eval so sánh với PP-OCRv5.
- **Bảng:** TableFormer cấu trúc ô → gán text OCR vào ô → hậu xử lý số (O→0, l→1 trong cột số; số âm trong ngoặc).
- **form / diagram / chữ ký:** chuyển VLM.

### Bước 4 — Router VLM
Gửi vùng sang gateway khi:
- `confidence < vlm_threshold` (mặc định 0.90);
- vùng có mực màu đè;
- type ∈ {`form_field`, `choice_group`, `diagram`, `handwritten_note`, tên `signature`} (danh sách cấu hình được);
- bảng không qua kiểm tra: HTML hỏng, số cột không nhất quán, **sai kiểm tra số học** (công thức kiểu "(10 = 01 − 02)", dòng "Cộng nhóm"/"TỔNG CỘNG" = tổng con, Thành tiền = SL × Đơn giá).

Cách gọi:
- Gửi crop (+ padding) **kèm bản nháp OCR**, yêu cầu sửa và trả JSON theo schema.
- Validate bằng Pydantic; sai → retry tối đa 2 lần; vẫn sai → giữ kết quả OCR + `VLM_OUTPUT_INVALID`.
- **Đối chiếu chéo:** VLM và OCR lệch số liệu → `needs_human_review` + `OCR_VLM_MISMATCH` (không tự chọn bên đúng).
- **Cache:** SHA-256(crop bytes) + prompt_version + model, lưu SQLite.

### Bước 5 — Ghép & chuẩn hóa
Reading order; tách header/footer khỏi nội dung; breadcrumb từ cấp tiêu đề (nhận "ĐIỀU 3", "3.1", "I.", "1."); **ghép bảng qua trang** (bảng cuối trang N + bảng đầu trang N+1 cùng số cột/căn lề, hoặc caption "tiếp theo") → `logical_tables`; NFC.

### Bước 6 — Chunk RAG
Theo mục, ~500–800 token; bảng chia theo nhóm hàng, mỗi chunk lặp header cột + breadcrumb.

### Xử lý lỗi
- Lỗi trang cô lập: trang `FAILED`, tài liệu `PARTIAL`, trang khác tiếp tục.
- Gateway sập: circuit breaker → vùng chờ VLM giữ kết quả OCR + `VLM_UNAVAILABLE`; job vẫn hoàn tất.
- Kết quả trang lưu ngay; khởi động lại thì chạy tiếp từ trang chưa xong.
- Mỗi bước phát sự kiện tiến độ; `page_ready` khi trang xong.

### Hiệu năng kỳ vọng
~5–15 giây/trang scan trên CPU máy dev (chưa tính thời gian gateway). SLA BRD (<0.8s/trang) chỉ áp dụng cho server GPU.

---

## 4. Giao diện (React)

**Stack:** React + Vite + TypeScript, TanStack Query, `EventSource` (SSE), `mermaid`. Ảnh trang lấy từ backend (`display`), bbox vẽ bằng SVG overlay. Không pdf.js.

**Không có đăng nhập/phân quyền.** Tên người sửa lấy từ config local.

### Màn hình 1 — Danh sách hồ sơ
Kéo-thả upload đơn/hàng loạt; thanh tiến độ realtime + thông điệp tiếng Việt; lưới trang thu nhỏ với trạng thái từng trang.

### Màn hình 2 — Đối chiếu split-screen
- **Trái:** ảnh trang (zoom/pan), bbox 🔴 cần duyệt / 🟡 `confidence < ui_threshold` (0.80) / 🟢 ổn; bật/tắt lớp: ảnh gốc ↔ ảnh làm sạch, lớp dấu, lớp chữ viết tay.
- **Phải:** nội dung theo reading order, editor theo type:
  - đoạn/tiêu đề: sửa text;
  - **bảng:** lưới sửa từng ô, màu theo confidence, thêm/xóa hàng-cột, gộp/tách ô, đánh dấu ô sai kiểm tra số học;
  - `form_field`: key-value; `choice_group`: checkbox bấm được;
  - `diagram`: Mermaid render + editor mã;
  - `stamp`/`signature`/`handwritten_note`: thẻ thông tin.
- **Đồng bộ hai chiều** giữa ô/đoạn bên phải và bbox bên trái.
- **Hàng đợi duyệt:** "Lỗi tiếp theo" (`N`), lọc chỉ mục cần duyệt, "Xác nhận đúng" (`Enter`), huy hiệu lý do tiếng Việt.
- **Progressive rendering:** trang chưa xong hiển thị skeleton; nhận `page_ready` thì tải ngay.

### Màn hình 3 — Xuất
Tải JSON AST (đã áp corrections), Markdown, chunks JSONL. Nút **"Lưu làm nhãn đúng"** → `eval/ground_truth/`.

### Màn hình 4 — Cài đặt VLM

| Nhóm | Trường |
|---|---|
| Kết nối | bật/tắt VLM, `base_url`, `api_key` (chỉ hiển thị dạng mask, không trả full về trình duyệt), header tùy chỉnh (key/value) |
| TLS/Mạng | verify SSL on/off, đường dẫn CA bundle nội bộ, proxy |
| Model | model (chọn từ `/v1/models` hoặc nhập tay), `temperature`, `max_tokens` |
| Structured output | `auto` / `json_schema` / `guided_json` / `prompt_only` (+ tự validate) |
| Hiệu năng | timeout, max concurrency, retries, cạnh ảnh dài tối đa |
| Định tuyến | `vlm_threshold` (0.90), `ui_threshold` (0.80), danh sách type luôn gửi VLM |

Lưu SQLite; biến môi trường có thể ghi đè.

**Test connection** (chạy được trên cấu hình chưa lưu; lịch sử test được lưu). Mỗi bước hiện ✅/❌, latency, chi tiết lỗi (HTTP status, đoạn body) và gợi ý sửa:
1. **Mạng:** DNS → TCP → TLS handshake (lỗi chứng chỉ → gợi ý CA bundle).
2. **Xác thực & model:** `GET /v1/models`; phân biệt 401/403 với 404; cảnh báo nếu model không có trong danh sách.
3. **Chat text:** prompt ngắn, kiểm tra phản hồi hợp lệ.
4. **Vision:** backend sinh ảnh có chữ tiếng Việt + số đã biết (vd "Kiểm tra MB-OCR 2026: 15.250.000"), so khớp kết quả — xác nhận model đọc được ảnh và giữ đúng dấu.
5. **Structured output:** thử `json_schema` rồi `guided_json`, validate schema; tự điền chế độ được hỗ trợ.
6. **Tổng kết:** latency trung bình, đề xuất concurrency.

---

## 5. Đánh giá chất lượng & Kiểm thử

### Bộ dữ liệu
- **Thật:** 13 trang `docs/examples/` → chạy pipeline → duyệt/sửa trên UI → "Lưu làm nhãn đúng". Mở rộng dần.
- **Tổng hợp (`idp synth`):** template HTML (BCTC, hợp đồng, biểu mẫu, bảng gộp ô, bảng qua trang) có nhãn đúng 100%, cộng bộ làm nhiễu có cường độ cấu hình: nghiêng 0–45° và 90/180°, bóng tối, chấm bẩn, sọc dọc, nếp gấp, blur, nén JPEG; chèn dấu tròn đỏ/xanh, dấu chữ nhật, vòng bút khoanh số, vết ố, chữ ký.

### Chỉ số (`idp eval` → báo cáo HTML + JSON, chia theo loại tài liệu/loại nhiễu)

| Chỉ số | Mục tiêu |
|---|---|
| CER chữ in tiếng Việt | < 1% |
| TEDS cấu trúc bảng | > 94% |
| Độ chính xác số liệu bị dấu/vòng khoanh/vết ố đè | > 92% |
| Độ chính xác form field & checkbox | đặt sau lần đo đầu |
| Orientation đúng | 100% |
| Tỉ lệ vùng gửi VLM, số lần gọi, thời gian/trang | theo dõi |

**Chế độ so sánh engine** (VietOCR vs PP-OCRv5, TableFormer vs Paddle table…) trên cùng bộ dữ liệu → bảng so sánh làm căn cứ chọn engine.

### Kiểm thử phần mềm
- **pytest unit:** tách mực, orientation, VNI/TCVN3, hậu xử lý số, kiểm tra số học BCTC, ghép bảng qua trang, chunker, NFC.
- **Contract test:** schema AST, schema đầu ra VLM.
- **Mock VLM server** (OpenAI-compatible) cho test, gồm kịch bản gateway sập / JSON sai / chậm.
- **Regression chất lượng:** `idp eval` trên bộ nhỏ; CER/TEDS giảm quá ngưỡng → fail.
- **Vitest (UI):** editor bảng, đồng bộ bbox hai chiều.

---

## 6. Ngoài phạm vi giai đoạn 1
Kafka, Triton, MinIO/S3, Redis, Go gateway, đăng nhập/phân quyền, đạt SLA tốc độ của BRD, tích hợp Core Banking/LOS.
