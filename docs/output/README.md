# Báo cáo chất lượng — 4 file mẫu (`docs/examples/`)

**Ngày chạy:** 2026-10-19
**Lệnh:** `idp process docs/examples/*.pdf --out docs/output`
**Cấu hình:** chỉ CPU (i5-9300H), **không bật VLM** (chưa cấu hình LLM Gateway MB). Mọi kết quả dưới đây là của tầng OCR cục bộ (Tầng 0–2).

Mỗi thư mục có:
- `ast.json`: AST đầy đủ, có bbox, độ tự tin, cờ cần duyệt.
- `doc.md`: Markdown; bảng có ô gộp được xuất dạng HTML.
- `chunks.jsonl`: các chunk RAG.
- `pages/*_overlay.jpg`: ảnh vẽ khung các phần tử. Đỏ là cần duyệt, vàng là độ tự tin thấp; ô bảng sai kiểm tra số học có viền đỏ.

## Tổng quan

| File | Trang | Thời gian/trang | Phần tử | Cần duyệt | Ghi chú chính |
|---|---|---|---|---|---|
| `scan_test_2_bang_phuc_tap` | 3 | ~30 s | 30 | 11 | BCTC đúng gần như toàn bộ; trang xoay 90° được dựng thẳng; dòng tô dạ quang đọc đúng |
| `scan_test_3_so_do` | 3 | ~17 s | 15 | 3 | Sơ đồ giữ chữ trong hình (cần VLM để ra Mermaid); dấu "BẢN SAO" đọc đúng 100% |
| `scan_test_4_bieu_mau_hon_hop` | 3 | ~34 s | 47 | 13 | 9 trường biểu mẫu và 4 nhóm checkbox được ghép đúng nhãn |
| `scan_test_hard` | 4 | ~23 s | 78 | 18 | Bảng hợp đồng được ghép qua 2 trang; dấu xanh được tách khỏi ghi chú tay |

Chưa có số đo CER/TEDS vì chưa có nhãn đúng (xem mục "Cách đo định lượng").

## Đạt được (đã kiểm tra bằng mắt so với ảnh gốc)

**Bảng biểu**
- BCTC B02-DN (trang 1, file bảng): tiêu đề 2 tầng (`NĂM 2026` gộp 3 cột, `CHỈ TIÊU` gộp 2 hàng) được dựng đúng. **67/68 số liệu đọc đúng** (đã so từng ô với ảnh gốc), kể cả các số nằm dưới vết ố cà phê. Ô sai duy nhất là `(610)` bị đọc thành `1610)`, và ô này đã được **tự gắn cờ đỏ** vì sai định dạng số. Cả 6 công thức `(10 = 01 - 02)`… được nhận ra và đều qua kiểm tra số học.
- Bảng phân bổ in ngang: trang được **xoay 90° tự động**. Tiêu đề "ĐƠN VỊ SỬ DỤNG", 13 hàng × 8 cột và các dòng "Cộng nhóm" / "TỔNG CỘNG" đều đúng.
- Bảng kê chứng từ: 18 dòng, STT 1–18 đầy đủ. Dòng 4 bị tô dạ quang vàng vẫn đọc đúng hoàn toàn.
- Hợp đồng: Bảng 1 ở trang 2 (dòng 1–7) và trang 3 (dòng 8–12 cùng 3 dòng tổng) được **ghép thành một bảng logic**. `Thành tiền = SL × Đơn giá`, `Cộng tiền hàng`, `Thuế GTGT 10%` và `TỔNG CỘNG` đều qua kiểm tra số học trên bảng đã ghép.

**Mực màu, dấu, chữ viết tay**
- Dấu chữ nhật đọc đúng nguyên văn: "ĐÃ KIỂM TRA 16/10/2026", "BẢN SAO Hà Nội 12/10/2026", "ĐÃ TIẾP NHẬN 15/10/2026" (dấu này còn bị nghiêng).
- Dấu tròn xanh "NHA TRANG MST 4201234567" được **tách riêng khỏi ghi chú tay chồng lên nó**. Ghi chú đọc được: "Đã đối chiếu - OK Chuyển khoản đợt 1 ngày 15/1…".
- Vòng bút đỏ khoanh số được nhận là `handwritten_note` "Khoanh tròn đánh dấu" và gắn `attached_to` vào bảng.

**Biểu mẫu**
- Các trường đọc đúng: Họ tên `LÊ HOANG MINH` (thiếu dấu huyền), Ngày sinh `15/03/1992`, CCCD `001234567890`, Địa chỉ 2 dòng, Mã hồ sơ, Cán bộ tiếp nhận, Ngày tiếp nhận.
- Cả 4 nhóm checkbox/radio đúng trạng thái, gồm Giới tính, Gói dịch vụ và Kênh thông báo (chọn nhiều).
- Chữ ký nhận đúng tên người ký viết tay "Lê Hoàng Minh".

**Tiêu đề và RAG**
- Cấp tiêu đề và breadcrumb được dựng đúng ("ĐIỀU 1…ĐIỀU 9", "3.1", "a)").
- Chunk bảng lặp lại dòng tiêu đề cột và có tiền tố `[Bối cảnh: …]`.

## Lỗi còn lại

Phần lớn các lỗi dưới đây thuộc loại cần tầng VLM hoặc người duyệt. Hệ thống đã gắn cờ `needs_human_review` cho chúng.

| Loại | Ví dụ | Cờ trên UI |
|---|---|---|
| Chữ chạy vòng cung trên dấu tròn | "GIÁI CONG TY THING HÀ NỘI MST 0109876543" | Cần VLM |
| Chữ số viết tay sửa đè lên số in bị gạch | Bảng kê dòng 5: OCR đọc "1900" | ✅ Ô tổng 1.851.222.000 bị gắn **sai tổng cộng** |
| Chấm bẩn / ngoặc đọc sai trong số | `1211.567` (đúng là `1.567`), `1610)` (đúng là `(610)`) | ✅ Ô bị gắn **số sai định dạng** |
| Ô ký tự viết tay | SĐT `091133406186` (đúng là `0912345678`); email `minh. Jegexample vn` | ✅ HANDWRITING |
| Dấu ở chữ in đậm/nghiêng | "Bền B" thay cho "Bên B", "Tràng 3/4" thay cho "Trang 3/4" | Một phần có cờ LOW_CONFIDENCE |
| Ô nhãn gộp hàng | "Chi phí khác" bị tách làm 2 phần vì một vệt scan chéo cắt qua ô | Không có cờ |
| Sơ đồ / biểu đồ | Mới ra `figure` kèm chữ OCR, chưa có Mermaid | Cần VLM |
| Nhãn checkbox nằm ngoài khung ô | "Kết quả: ☑ Hợp lệ ☐ Bổ sung": nhãn lựa chọn trống | Cần VLM |

## Cách đo định lượng (CER / TEDS)

1. Mở UI (`idp serve`), duyệt và sửa từng file, rồi bấm **"Lưu làm nhãn đúng"**. Bản đã sửa được ghi vào `eval/ground_truth/<tên file>/ast.json`. Có thể dùng `idp gt-init <tên file>` để tạo bản nháp sửa tay.
2. Chạy `idp eval --gt eval/ground_truth --pred docs/output`. Lệnh in CER và TEDS cho từng trang, đồng thời ghi `eval/reports/report.json`.

## Bước tiếp theo để nâng chất lượng

- **Bật VLM:** vào màn hình *Cài đặt VLM*, nhập base_url, API key và model của LLM Gateway MB, bấm **Kiểm tra kết nối** (6 bước), rồi Lưu. Các vùng có cờ ở bảng trên sẽ tự được gửi VLM ở lần chạy sau. Kết quả VLM được đối chiếu chéo với OCR; số liệu lệch nhau sẽ có cờ `OCR_VLM_MISMATCH`.
- **Hiệu chỉnh ngưỡng `vlm_threshold`** (mặc định 0.85) sau khi có nhãn đúng: độ tự tin của VietOCR dồn quanh 0.85–0.91 kể cả với dòng đọc đúng.
