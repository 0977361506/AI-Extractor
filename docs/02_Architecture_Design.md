# TÀI LIỆU THIẾT KẾ KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)
**Dự án:** Hệ thống Xử lý và Chuẩn hóa Tài liệu Thông minh (Banking-Grade IDP Engine)

---

## 1. Kiến trúc Tổng thể Đa Ngôn ngữ (Polyglot Microservices)

Hệ thống kết hợp sức mạnh chịu tải I/O của **Golang**, khả năng xử lý ảnh tốc độ cao của **C++/Rust**, và hệ sinh thái AI của **Python**:

* **API Gateway & SSE Streaming Service:** Viết bằng **Golang** (hoặc FastAPI + Uvicorn) để quản lý hàng ngàn kết nối thời gian thực của RM và stream file dung lượng lớn lên MinIO.
* **Event Broker & State Store:** **Apache Kafka** (điều phối sự kiện bất đồng bộ theo mẫu *Claim-Check Pattern*) kết hợp **Redis** (lưu trạng thái gom trang *Scatter-Gather* và Perceptual Hash Cache).
* **Core Document & AI Workers:** Viết bằng **Python 3.11+**, bên trong sử dụng các thư viện bọc lõi C++/Rust (`confluent-kafka`, `PyMuPDF`, `python-calamine`, `orjson`).
* **AI Serving Layer:** **NVIDIA Triton Inference Server** (chạy PaddleOCR/Docling models qua ONNX/TensorRT) và **vLLM** (chạy `Qwen2.5-VL-7B-Instruct` với tính năng *Guided Decoding* & *Prefix Caching*).

---

## 2. Sơ đồ Luồng Sự kiện trên Apache Kafka (Event-Driven Pipeline)

```
[RM Web UI] ──(Upload File)──► [API Gateway (Go/FastAPI)] ──► [MinIO S3 Storage]
     ▲                                  │
     │ (SSE Realtime)                   ▼
     │                         (Topic 1: doc.ingestion)
     │                                  │
     │               ┌──────────────────┴──────────────────┐
     │               ▼ (DOCX/XLSX/PPTX/HTML)               ▼ (PDF / Images)
     │      [CPU Fast-Parser Group]               [CPU Pre-processor Group]
     │      (Docling Native + Calamine)           (Tách trang, Check Font VNI,
     │               │                             Khử nghiêng, Tách dấu đỏ HSV)
     │               │                                     │
     │               │                                     ▼
     │               │                           (Topic 2: page.layout_ocr)
     │               │                                     │
     │               │                                     ▼
     │               │                           [GPU Tier-1: Docling + PaddleOCR]
     │               │                           (RT-DETR Layout + TableFormer + VietOCR)
     │               │                                     │
     │               │                        ┌────────────┴────────────┐
     │               │                        ▼ (Score >= 0.85)         ▼ (Score < 0.85 / Viết tay / Bảng khó)
     │               │                        │               (Topic 3: region.vlm_heavy)
     │               │                        │                         │
     │               │                        │                         ▼
     │               │                        │               [GPU Tier-2: vLLM Qwen2.5-VL]
     │               │                        │               (Chỉ đọc vùng ảnh đã Crop)
     │               └────────────────────────┼─────────────────────────┘
     │                                        ▼
     │                               [Redis State Store] (Đếm số trang hoàn thành)
     │                                        │
     │                                        ▼
     │                              (Topic 4: doc.assembly)
     │                                        │
     │                                        ▼
     │                         [AST Normalizer & RAG Chunker]
     │                         (Chuẩn hóa NFC, Xuất Markdown/JSON, Lưu DB)
     │                                        │
     └──── (Topic 5: job.progress_events) ◄───┘ (Mọi Worker đều bắn tiến độ về đây)
```

---

## 3. Chiến lược "Zero-Waste GPU" (Tối ưu hóa VLM Nội bộ)

1. **Tầng 0 – Fast Bypass (0% GPU):**
   - File `DOCX, PPTX, XLSX, HTML` đi thẳng qua parser cấu trúc cây.
   - Trang PDF có sẵn lớp text Unicode sạch và không chứa bảng phức tạp -> Trích xuất bằng `PyMuPDF` trong 5ms.
2. **Tầng 1 – Tiền xử lý Ảnh Chuyên sâu trên CPU:**
   - **Tách dấu mộc đỏ (Red Stamp Removal):** Chuyển không gian màu sang HSV, lọc dải màu đỏ (`Hue: [0-10] & [160-180]`) để tái tạo lại nét chữ đen bị con dấu đè lên trước khi đưa vào OCR.
   - **Phát hiện Font VNI/TCVN3:** Dùng Regex và từ điển N-gram tiếng Việt kiểm tra lớp text. Nếu phát hiện bảng mã cũ nhưng không lỗi font -> Chuyển mã trực tiếp sang Unicode. Nếu lỗi encoding -> Ép chuyển sang luồng quét ảnh OCR.
3. **Tầng 2 – Layout Analysis & Local OCR (GPU T4/L4 Chi phí thấp):**
   - Sử dụng **Docling** (với model `DocLayNet RT-DETR`) để tìm tọa độ các khối: `Title, Text, Table, Figure, Formula, Stamp, Signature`.
   - Cắm **PaddleOCR + VietOCR** vào làm engine đọc chữ tiếng Việt cho Docling.
4. **Tầng 3 – Smart VLM Fallback (GPU A100/L40S - Chỉ xử lý ~10% vùng dữ liệu):**
   - **Chỉ kích hoạt khi:** (a) Điểm tự tin OCR/Table `< 0.85`, (b) Vùng ảnh có cờ `handwriting = True` (chữ viết tay của RM), hoặc (c) Bảng Báo cáo tài chính bị mất đường kẻ/dấu đỏ đè nặng.
   - **Region Cropping:** Cắt (crop) đúng tọa độ Bounding Box của bảng/đoạn chữ đó (thêm padding 10px) để gửi vào `Qwen2.5-VL-7B`, giúp giảm 80% lượng token ảnh so với gửi cả trang A4.
   - **Perceptual Hash Caching (`pHash`):** Băm vùng ảnh crop và lưu vào Redis. Nếu gặp lại biểu mẫu/logo/header giống hệt trong bộ hồ sơ, lấy kết quả ngay từ Redis trong 1ms.