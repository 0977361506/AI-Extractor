# CHI TIẾT EPICS, USER STORIES & TIÊU CHÍ NGHIỆM THU (AGILE BACKLOG)
**Dự án:** Hệ thống Xử lý và Chuẩn hóa Tài liệu Thông minh (Banking-Grade IDP Engine)

---

## EPIC 1: Tầng Tiếp nhận, Phân luồng & Xử lý Nhanh (Ingestion & Fast-Track Parser)
**Mục tiêu:** Tiếp nhận hồ sơ dung lượng lớn từ RM, lưu trữ an toàn vào MinIO, xử lý tức thì các file Office/HTML và phân tích sơ bộ PDF.

* **Story 1.1: API Upload & Claim-Check Pattern với MinIO + Kafka**
  - *Mô tả:* Xây dựng API nhận file đa định dạng, lưu vào MinIO và đẩy metadata vào topic `doc.ingestion`.
  - *Acceptance Criteria (AC):* Tải file 200MB không gây nghẽn RAM của API Gateway; trả về `job_id` dưới 150ms.
* **Story 1.2: Bộ xử lý siêu tốc cho DOCX, PPTX, XLSX, HTML**
  - *Mô tả:* Sử dụng Docling Native kết hợp `python-calamine` (cho Excel) và `trafilatura` (cho HTML) để chuyển thẳng sang cấu trúc AST mà không đi qua OCR.
  - *AC:* Giữ nguyên 100% các ô gộp (`merged cells`) trong Excel/Word; tốc độ `< 500ms/file`.
* **Story 1.3: Bộ kiểm tra Font chữ lịch sử (VNI / TCVN3 Detector & Converter)**
  - *Mô tả:* Kiểm tra lớp text của PDF. Nếu phát hiện bảng mã VNI/TCVN3 thì tự động chuyển mã sang Unicode NFC; nếu font bị hỏng glyph (`□□□`) thì gắn cờ `force_ocr = true`.
  - *AC:* Phát hiện đúng 99% văn bản dùng font `.VnTime` và `VNI-Times`.

---

## EPIC 2: Tiền xử lý Ảnh Chuyên sâu cho Hồ sơ Ngân hàng (Banking Image Pre-processing)
**Mục tiêu:** Làm sạch các bản scan bẩn, ảnh chụp nghiêng bằng điện thoại của RM và xử lý dấu mộc đỏ trước khi đưa vào OCR.

* **Story 2.1: Tự động xoay thẳng (Deskew) và cắt viền đen (Auto-Crop)**
  - *Mô tả:* Dùng OpenCV phát hiện góc nghiêng của văn bản scan và xoay thẳng lại góc 0 độ, loại bỏ nền bàn/viền đen khi RM chụp bằng điện thoại.
  - *AC:* Xử lý được ảnh nghiêng tới 45 độ; thời gian xử lý `< 80ms/trang` trên CPU.
* **Story 2.2: Thuật toán Tách lớp Dấu mộc đỏ (HSV Red-Channel Removal)**
  - *Mô tả:* Tách riêng kênh màu đỏ của con dấu và chữ ký mực đỏ ra khỏi nền chữ đen của Báo cáo tài chính, xuất ra 2 phiên bản ảnh (1 bản gốc để hiển thị UI, 1 bản đã xóa dấu đỏ để đưa vào OCR).
  - *AC:* Chữ và số nằm dưới con dấu đỏ đậm vẫn giữ được nét liền mạch, tăng độ chính xác OCR trên vùng bị đóng dấu từ `< 40%` lên `> 92%`.

---

## EPIC 3: Core Layout Analysis & Local OCR Tiếng Việt (Docling + PaddleOCR)
**Mục tiêu:** Xây dựng khung xương bóc tách bố cục tài liệu và đọc chữ tiếng Việt tốc độ cao trên GPU Tier-1.

* **Story 3.1: Tích hợp Docling Layout (`RT-DETR`) & `TableFormer`**
  - *Mô tả:* Chạy Docling để nhận diện thứ tự đọc (Reading Order) trên trang nhiều cột và tái tạo cấu trúc bảng thành HTML/Markdown.
  - *AC:* Không bị trộn lẫn Header/Footer vào nội dung văn bản; nhận diện đúng các bảng không có đường kẻ dọc.
* **Story 3.2: Viết Custom OCR Plugin ghép PaddleOCR + VietOCR vào Docling**
  - *Mô tả:* Thay thế OCR mặc định của Docling bằng `PaddleOCR` (Text Detection) và `VietOCR/PP-OCRv4` (Recognition) chạy trên ONNX Runtime / Triton Server.
  - *AC:* Đọc chính xác văn bản pha trộn Tiếng Việt có dấu và thuật ngữ Tiếng Anh tài chính; tốc độ `< 0.5s/trang` trên GPU T4/L4.
* **Story 3.3: Bộ hậu xử lý Số liệu Kế toán Việt Nam (Financial Post-Processor)**
  - *Mô tả:* Chuẩn hóa toàn bộ văn bản về Unicode `NFC`. Tự động sửa lỗi nhận diện ký tự trong các cột số tiền (ví dụ: `15.O00.00O` -> `15.000.000`).
  - *AC:* 100% chuỗi đầu ra đạt chuẩn Unicode NFC.

---

## EPIC 4: Smart VLM Router & Tầng Xử lý Hạng nặng (vLLM Qwen2.5-VL)
**Mục tiêu:** Giải quyết các bảng biểu siêu khó và chữ viết tay của RM với chi phí GPU thấp nhất.

* **Story 4.1: Logic Phân luồng Thông minh (Confidence & Heuristic Router)**
  - *Mô tả:* Đánh giá kết quả từ Epic 3. Nếu `confidence < 0.85`, HTML bảng bị lỗi thẻ đóng/mở, hoặc phát hiện vùng chữ viết tay -> Cắt (crop) đúng tọa độ Bounding Box đó và đẩy vào Kafka topic `region.vlm_heavy`.
  - *AC:* Giảm tối thiểu 85% số lượng trang/vùng phải gọi tới VLM.
* **Story 4.2: Bộ nhớ đệm Băm Hình ảnh (Perceptual Hash Cache trên Redis)**
  - *Mô tả:* Tính mã băm `pHash` cho mỗi bức ảnh crop trước khi gọi VLM. Nếu đã tồn tại trong Redis, trả về kết quả ngay lập tức.
  - *AC:* Giảm 100% thời gian gọi VLM cho các biểu mẫu/header lặp lại.
* **Story 4.3: Triển khai vLLM với Qwen2.5-VL-7B-Instruct & Guided Decoding**
  - *Mô tả:* Dựng server vLLM nội bộ, cấu hình *Prefix Caching* cho System Prompt chuyên đọc BCTC và ép đầu ra tuân thủ chặt chẽ JSON/HTML Schema.
  - *AC:* VLM không bao giờ sinh văn bản thừa ngoài cấu trúc bảng/JSON yêu cầu; đọc được chữ viết tay tiếng Việt của RM.

---

## EPIC 5: Gom mảnh Dữ liệu, Chuẩn hóa RAG & Giao diện Đối chiếu Thời gian thực
**Mục tiêu:** Đem lại trải nghiệm mượt mà cho RM trên Web UI và cung cấp dữ liệu sạch nhất cho hệ thống RAG.

* **Story 5.1: Bộ gom trang Bất đồng bộ (Scatter-Gather Assembler với Redis)**
  - *Mô tả:* Lắng nghe kết quả từ các trang chạy song song, lưu vào Redis Hash và ghép lại thành đối tượng `DoclingDocument` hoàn chỉnh ngay khi đủ số trang.
  - *AC:* Đảm bảo thứ tự trang từ 1 đến N luôn chính xác tuyệt đối dù trang sau xử lý xong trước trang đầu.
* **Story 5.2: Bộ cắt Chunk Có Ngữ cảnh (Contextual RAG Chunker)**
  - *Mô tả:* Cắt tài liệu thành các chunk cho Vector DB. Tự động đính kèm đường dẫn tiêu đề cha (`Breadcrumbs`) và lặp lại dòng Header cho các bảng dài bị cắt qua nhiều trang.
  - *AC:* Mọi chunk bảng biểu đều có đầy đủ dòng tiêu đề cột để LLM không hiểu sai số liệu.
* **Story 5.3: Streaming Tiến độ qua SSE & Giao diện Split-Screen Verification**
  - *Mô tả:* Đẩy sự kiện từ topic `job.progress_events` qua SSE lên trình duyệt. Xây dựng giao diện chia đôi màn hình: Click vào ô dữ liệu bên phải sẽ tự động cuộn và tô sáng (highlight) tọa độ BBox trên ảnh PDF gốc bên trái; tô màu vàng cảnh báo các ô có `confidence < 0.80`.
  - *AC:* Hiển thị ngay trang vừa xử lý xong (Progressive Rendering) mà không cần đợi toàn bộ file hoàn tất.