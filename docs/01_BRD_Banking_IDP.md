# TÀI LIỆU YÊU CẦU NGHIỆP VỤ (BRD)
**Dự án:** Hệ thống Xử lý và Chuẩn hóa Tài liệu Thông minh (Banking-Grade IDP Engine)  
**Phiên bản:** 1.0  
**Môi trường triển khai:** 100% On-Premise (Air-gapped Mạng nội bộ Ngân hàng)

---

## 1. Bối cảnh & Mục tiêu Dự án (Executive Summary)
Cán bộ Quan hệ Khách hàng (RM) và Chuyên viên Thẩm định Tín dụng hàng ngày phải xử lý hàng ngàn trang hồ sơ vay vốn, báo cáo tài chính (BCTC), hợp đồng kinh tế, hồ sơ pháp lý và biên bản kiểm tra thực địa. Dữ liệu đầu vào rất đa dạng và có độ nhiễu cao (ảnh chụp điện thoại, bản scan mờ, dấu mộc đỏ đè lên số liệu, font chữ cũ VNI/TCVN3, chữ viết tay).

### Mục tiêu cốt lõi:
1. **Chuẩn hóa Đa định dạng:** Chuyển đổi chính xác các định dạng `PDF, DOCX, PPTX, XLSX, HTML, Image` sang **Markdown** và **JSON chuẩn hóa**.
2. **Phục vụ Kép (Dual-Purpose Output):**
   - Cung cấp dữ liệu kèm tọa độ (Bounding Box) để hiển thị lên **Giao diện Đối chiếu (Split-Screen Verification Web UI)** cho RM kiểm tra.
   - Cung cấp các gói dữ liệu phân mảnh có ngữ cảnh (**Contextual Chunks**) để nạp vào hệ thống **RAG / LLM Search** nội bộ.
3. **Tối ưu Tài nguyên GPU (Zero-Waste VLM):** Giảm 85%–90% tải trên VLM bằng kiến trúc phân tầng thông minh, chỉ đẩy các vùng dữ liệu thực sự khó (bảng rách, dấu đỏ đè chữ, chữ viết tay) lên VLM.
4. **Tuân thủ Bảo mật Ngân hàng:** Chạy 100% On-Premise, không gọi API ra ngoài Internet, sử dụng các phần mềm mã nguồn mở có giấy phép thương mại an toàn (MIT / Apache 2.0).

---

## 2. Đối tượng Sử dụng (Stakeholders & Personas)
1. **RM (Relationship Manager):** Tải hồ sơ khách hàng lên hệ thống, theo dõi tiến độ xử lý theo thời gian thực, đối chiếu và chỉnh sửa nhanh các trường thông tin có độ tự tin thấp trên giao diện Web.
2. **Chuyên viên Thẩm định / Phê duyệt Tín dụng:** Tra cứu thông tin chéo trên toàn bộ bộ hồ sơ thông qua hệ thống RAG Chatbot và xem trực tiếp nguồn trích dẫn (highlight trên file gốc).
3. **Hệ thống Downstream (RAG Engine, Core Banking, LOS):** Nhận dữ liệu JSON chuẩn hóa qua Kafka/API để tự động điền form hoặc lập chỉ mục Vector.

---

## 3. Phạm vi Nghiệp vụ & Yêu cầu Chức năng (Functional Requirements)

| Mã YC | Nhóm chức năng | Mô tả chi tiết | Độ ưu tiên |
| :--- | :--- | :--- | :--- |
| **FR-01** | Tiếp nhận đa định dạng | Hỗ trợ tải lên đơn lẻ hoặc hàng loạt (batch) các định dạng: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.jpg`, `.png`, `.tiff`. | Bắt buộc (P0) |
| **FR-02** | Xử lý đặc thù Hồ sơ Việt Nam | Nhận diện chính xác Tiếng Việt có dấu xen lẫn Tiếng Anh. Tự động phát hiện và chuyển mã font VNI/TCVN3 sang Unicode chuẩn NFC. | Bắt buộc (P0) |
| **FR-03** | Xử lý nhiễu thị giác Ngân hàng | Tự động xoay thẳng trang nghiêng (deskew), khử viền đen, tách lớp dấu mộc đỏ (Red Stamp Removal) để đọc rõ con số bên dưới mà vẫn giữ ảnh gốc để đối chiếu. | Bắt buộc (P0) |
| **FR-04** | Trích xuất Bảng & Công thức | Giữ nguyên cấu trúc bảng phức tạp (merged cells `rowspan`/`colspan`, bảng nhiều trang, bảng không đường kẻ) xuất ra HTML/Markdown và JSON. Chuyển công thức sang LaTeX. | Bắt buộc (P0) |
| **FR-05** | Theo dõi tiến độ Thời gian thực | Hiển thị tiến độ chi tiết từng trang/giai đoạn qua SSE. Hỗ trợ **Progressive Rendering**: Trang nào xử lý xong đẩy lên UI cho RM xem ngay, không cần chờ xong cả file. | Bắt buộc (P0) |
| **FR-06** | Giao diện Đối chiếu (Web UI) | Màn hình chia đôi: Bên trái là tài liệu gốc có vẽ khung tọa độ (BBox), bên phải là Markdown/Bảng cho phép RM sửa trực tiếp các ô được cảnh báo màu vàng/đỏ (`confidence < 0.80`). | Cao (P1) |
| **FR-07** | Chuẩn hóa đầu ra cho RAG | Tự động gắn đường dẫn ngữ cảnh cha-con (Breadcrumbs) và lặp lại dòng tiêu đề bảng (Table Header) khi cắt chunk cho các bảng kéo dài nhiều trang. | Bắt buộc (P0) |

---

## 4. Yêu cầu Phi chức năng & SLA (Non-Functional Requirements)

* **Bảo mật & Tuân thủ (Security & Compliance):**
  - Toàn bộ dữ liệu lưu trữ trên MinIO (S3 nội bộ) phải được mã hóa.
  - Tuyệt đối không sử dụng các thư viện dính giấy phép AGPLv3 (như MinerU gốc). Chỉ sử dụng MIT/Apache 2.0 (`Docling`, `PaddleOCR`, `Qwen2.5-VL`, `vLLM`).
* **Hiệu năng & Tốc độ (SLA):**
  - Tài liệu Office/HTML (`DOCX, XLSX, PPTX, HTML`): Thời gian xử lý trung bình `< 1 giây / file`.
  - Tài liệu PDF/Scan thông thường (Tầng 1 & 2 - OCR Local): `< 0.8 giây / trang`.
  - Tài liệu PDF/Scan có bảng khó/viết tay gọi VLM (Tầng 3): `< 3.5 giây / vùng crop`.
  - Độ trễ cập nhật trạng thái tiến độ lên màn hình RM: `< 200ms`.
* **Độ chính xác mục tiêu (Accuracy KPIs):**
  - Văn bản in máy tiếng Việt: CER (Character Error Rate) `< 1%`.
  - Cấu trúc bảng biểu tài chính (TEDS - Tree-Edit-Distance-Based Similarity): `> 94%`.
  - Số liệu tài chính bị đóng dấu đỏ đè lên: Độ chính xác trích xuất `> 92%`.