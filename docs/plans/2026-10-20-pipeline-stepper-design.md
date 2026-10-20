# Màn xử lý hồ sơ dạng stepper — thiết kế

Ngày: 2026-10-20 · Trạng thái: đã duyệt

## Mục tiêu

Kéo hồ sơ vào → thấy pipeline chạy **từng bước**, mỗi bước có **kết quả thật của bước đó** bên dưới.
Phục vụ cả RM (mặc định gọn, xong là vào đối chiếu) lẫn demo (bấm mở chi tiết trung gian).

Hướng đã chọn: **backend ghi trace từng bước + event chi tiết** (thay vì chỉ dựng frontend trên dữ liệu cuối,
hay phát lại sau khi chạy xong).

## 1. Màn hình

Thay dropzone ở trang chủ; danh sách hồ sơ cũ giữ nguyên bên dưới.

> Thứ tự bước theo đúng code: bảng được dựng (OCR từng ô) **trước** khi đọc các dòng ngoài bảng, nên
> stepper là `preprocess → layout → tables → ocr → marks → vlm` (thay cho bước gộp "Bảng & dấu" ban đầu).

```
┌ Kéo thả hồ sơ ───────────────────────────────────────────────┐
├ Hàng chờ: [hd.pdf ▓▓▓░ 60%] [bctc.xlsx ✔] [scan.jpg ⏳] ─────┤
├ Stepper:  ✔ Nhận file ─ ✔ Làm sạch ─ ● Bố cục ─ ○ Đọc chữ ─ ○ Bảng & dấu ─ ○ AI ─ ○ Hoàn tất
├ Panel:    BƯỚC 3 · BỐ CỤC        trang [1] 2 3    0,8s · 12 vùng
│           [ảnh trang + kết quả của bước]   │ tóm tắt số liệu
│                                            │ [Mở đối chiếu →]
└──────────────────────────────────────────────────────────────┘
```

- Hàng chờ: thẻ cho từng file vừa thả trong phiên, có mini-progress; chọn thẻ → stepper/panel của file đó.
  Mặc định tự theo file đang chạy.
- Stepper phản ánh **trang đang chọn**; mặc định bám trang đang chạy, người dùng tự chọn trang thì dừng bám.
- Bấm một bước → panel hiện kết quả bước đó; mặc định panel theo bước đang chạy.

| Bước | Thu gọn (RM) | Mở rộng (demo) |
|---|---|---|
| ingest · Nhận file | loại file, số trang, bảng mã | — |
| preprocess · Làm sạch | ảnh gốc → đã xoay thẳng, góc xoay/lệch | ảnh làm sạch cho OCR |
| layout · Bố cục | khung vùng tô màu theo loại + khung dòng chữ phát hiện | độ tin cậy từng vùng |
| tables · Bảng | số bảng / ô | lưới ô, ô sai kiểm tra số học |
| ocr · Đọc chữ | số dòng, độ tin cậy TB | khung dòng OCR thô, hover xem text |
| marks · Dấu & ghép trang | số dấu / chữ ký / checkbox / phần tử | khung vết mực + text đọc được |
| vlm · AI chuyên sâu | số vùng gửi gateway (`skipped` nếu tắt) | danh sách trước → sau |
| assemble · Hoàn tất | số mục cần duyệt, **Mở đối chiếu** | xem nhanh Markdown |

- PDF có lớp chữ: `preprocess`, `ocr` = `skipped` ("đọc trực tiếp từ lớp chữ PDF"); dòng chữ vẫn hiện, nguồn `text_layer`.
- Office/HTML: `ingest → parse → assemble`; panel dùng bản xem trước HTML của file gốc.

## 2. Dữ liệu & API

**PageTrace** (chỉ ghi thêm, không đổi logic): truyền vào `process_page`, mỗi bước bọc `with trace.step("layout"):`
→ đo thời gian, ghi tóm tắt. Mỗi bước xong: phát event `STEP` và ghi đè `pages/N_trace.json` (panel xem được
kết quả bước vừa xong khi trang còn đang chạy).

`pages/N_trace.json` — toạ độ chuẩn hoá theo ảnh `display` (đã xoay thẳng):

```json
{ "page": 1, "steps": {
  "preprocess": { "status": "done", "ms": 420, "summary": { "rotation": 90, "skew": 1.2 } },
  "layout":     { "status": "done", "ms": 810, "summary": { "regions": 12, "by_label": { "table": 2 } },
                  "regions": [ { "label": "table", "score": 0.93, "bbox": [0.1, 0.2, 0.9, 0.5] } ] },
  "ocr":        { "status": "running" } } }
```

- `ocr`: `lines: [{text, conf, bbox, source}]`; `structure`: lưới ô từng bảng, ô sai số học, vết mực
  (loại/màu/bbox/text), nhóm checkbox; `vlm`: `changes: [{element_id, before, after}]` — diff text/ô
  chụp trước và sau `refine_page` (không sửa module `vlm`).
- Trạng thái bước: `pending | running | done | skipped | failed`. ~10–30 KB/trang, xoá cùng hồ sơ.

**Event SSE** (mở rộng event hiện có, UI cũ không đổi):
- `PLAN` (đầu tiên): `{kind, total_pages, steps: [...]}`.
- `STEP`: `{page, step, status, ms, summary, error?}`; bước cấp tài liệu (`ingest`, `parse`, `assemble`) có `page = null`.
- SSE đã phát lại từ đầu → mở giữa chừng / F5 dựng lại đúng stepper.

**API mới**: `GET /api/v1/documents/{id}/pages/{n}/trace` — trace hiện có (kể cả dở); 404 với hồ sơ cũ
→ panel lui về chế độ "chỉ xem kết quả cuối".

CLI `process` cũng ghi trace (soi chất lượng offline).

**Frontend**: `usePipeline(docId)` = reducer thuần trên event SSE → `{plan, docSteps, pages: {n: {step: state}}}`;
panel tải trace qua react-query, khoá theo số bước `done` để tự tải lại.

## 3. Lỗi, hiệu năng, test

- Bước lỗi → `failed` + thông báo tiếng Việt (stack ở phần mở rộng); các bước sau của trang → `skipped`;
  trang `FAILED`, trang khác chạy tiếp; panel nhảy tới bước lỗi.
- Gateway không gọi được → `vlm` `done` + cảnh báo vàng (vùng đã gắn cần duyệt), không phải lỗi.
- Ghi trace lỗi → log và bỏ qua; **trace không bao giờ làm hỏng xử lý hồ sơ**.
- Server khởi động lại → job chạy lại, `PLAN` mới reset stepper của hồ sơ đó.
- Panel chỉ tải trace trang đang xem; ảnh dùng lại `display.jpg` / `ocr.png`; overlay bằng SVG.

Test: `PageTrace` (trạng thái, thời gian, lỗi kéo bước sau thành `skipped`, lỗi ghi không lan ra);
thứ tự `PLAN`/`STEP` với model giả; Office 3 bước; API `/trace` (dở dang, 404 hồ sơ cũ); diff VLM;
slow test trên file mẫu thật (có vùng, dòng, lưới, bbox trong [0,1]); frontend: reducer (phát lại cho
cùng kết quả), stepper 4 trạng thái + bám trang, panel từng bước, fallback hồ sơ cũ.
Kiểm tra cuối trên app thật: PDF scan, PDF số, ảnh, XLSX.

Ngoài phạm vi: tạm dừng / chạy lại từng bước, so sánh hai lần chạy, xuất trace ra báo cáo.

## Thứ tự triển khai (TDD, commit theo từng mốc)

1. `idp/pipeline/trace.py`: `PageTrace` + ghi file an toàn.
2. Gắn trace vào `process_page` (scan + PDF số) và `process_document` (PLAN, ingest, vlm diff, assemble, Office).
3. API `/pages/{n}/trace`.
4. Frontend: `usePipeline` reducer → `Stepper` → panel từng bước → hàng chờ + thay dropzone trang chủ.
5. Kiểm tra trên app thật, chụp màn hình từng bước.
