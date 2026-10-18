# ĐẶC TẢ DỮ LIỆU & GIAO TIẾP (DATA CONTRACTS & SCHEMAS)
**Dự án:** Hệ thống Xử lý và Chuẩn hóa Tài liệu Thông minh (Banking-Grade IDP Engine)

---

## 1. Cấu trúc JSON Đầu ra Chuẩn hóa (Unified Document AST)
Cấu trúc này phục vụ đồng thời 2 mục đích: (1) Vẽ khung tọa độ đối chiếu trên Web UI cho RM và (2) Làm đầu vào giàu ngữ cảnh cho hệ thống RAG. Mọi chuỗi ký tự đều bắt buộc chuẩn hóa **Unicode NFC**.

```json
{
  "document_id": "doc_bctc_2025_001",
  "job_id": "job_998877",
  "metadata": {
    "filename": "BCTC_KiemToan_2025_CongTyABC.pdf",
    "file_type": "application/pdf",
    "total_pages": 32,
    "detected_charset": "UNICODE_NFC",
    "has_red_stamp": true,
    "processing_time_ms": 4250,
    "vlm_invocations_count": 2
  },
  "pages": [
    {
      "page_number": 1,
      "dimensions": { "width": 595.0, "height": 842.0 },
      "original_image_s3_uri": "s3://idp-bank/raw/doc_bctc_2025_001/page_1.png",
      "cleaned_image_s3_uri": "s3://idp-bank/cleaned/doc_bctc_2025_001/page_1_nostamp.png",
      "elements": [
        {
          "element_id": "el_p1_001",
          "type": "heading_1",
          "hierarchy_breadcrumb": ["BÁO CÁO TÀI CHÍNH", "BẢNG CÂN ĐỐI KẾ TOÁN"],
          "bbox_normalized": [0.12, 0.08, 0.88, 0.14],
          "content_markdown": "# BẢNG CÂN ĐỐI KẾ TOÁN",
          "confidence_score": 0.99,
          "needs_human_review": false,
          "extraction_engine": "docling_paddle_ocr"
        },
        {
          "element_id": "el_p1_002",
          "type": "table",
          "hierarchy_breadcrumb": ["BÁO CÁO TÀI CHÍNH", "BẢNG CÂN ĐỐI KẾ TOÁN", "TÀI SẢN NGẮN HẠN"],
          "bbox_normalized": [0.08, 0.18, 0.92, 0.65],
          "content_markdown": "| Chỉ tiêu | Mã số | Số cuối năm (VNĐ) |\n|---|---|---|\n| I. Tiền và tương đương tiền | 110 | 15.250.000.000 |",
          "content_html": "<table><thead><tr><th>Chỉ tiêu</th><th>Mã số</th><th>Số cuối năm (VNĐ)</th></tr></thead><tbody><tr><td>I. Tiền và tương đương tiền</td><td>110</td><td data-bbox='[0.65,0.22,0.90,0.25]' data-conf='0.78'>15.250.000.000</td></tr></tbody></table>",
          "rag_contextual_chunks": [
            "[Bối cảnh: BCTC Công ty ABC > Bảng cân đối kế toán > Tài sản ngắn hạn]\n| Chỉ tiêu | Mã số | Số cuối năm (VNĐ) |\n|---|---|---|\n| I. Tiền và tương đương tiền | 110 | 15.250.000.000 |"
          ],
          "confidence_score": 0.78,
          "needs_human_review": true,
          "review_reason": "RED_STAMP_OVERLAP_ON_NUMBERS",
          "extraction_engine": "vlm_qwen2.5_vl_7b_cropped"
        }
      ]
    }
  ]
}
```

---

## 2. Đặc tả Kafka Message Payloads

### A. Topic `page.layout_ocr` (Từ CPU Pre-processor gửi sang GPU Tier-1)
```json
{
  "job_id": "job_998877",
  "document_id": "doc_bctc_2025_001",
  "page_number": 1,
  "total_pages": 32,
  "s3_original_uri": "s3://idp-bank/raw/doc_bctc_2025_001/page_1.png",
  "s3_nostamp_uri": "s3://idp-bank/cleaned/doc_bctc_2025_001/page_1_nostamp.png",
  "force_ocr": true,
  "detected_legacy_font": "VNI-Times",
  "timestamp": 1710000000
}
```

### B. Topic `region.vlm_heavy` (Từ GPU Tier-1 gửi sang GPU Tier-2 vLLM)
```json
{
  "job_id": "job_998877",
  "document_id": "doc_bctc_2025_001",
  "page_number": 1,
  "element_id": "el_p1_002",
  "region_type": "table",
  "s3_cropped_image_uri": "s3://idp-bank/crops/doc_bctc_2025_001/p1_el_002.png",
  "fallback_reason": "LOW_CONFIDENCE_AND_STAMP_OVERLAP",
  "tier1_confidence": 0.62,
  "tier1_draft_html": "<table>...</table>"
}
```

### C. Topic `job.progress_events` (Gửi về API Gateway để đẩy SSE lên Web UI)
```json
{
  "job_id": "job_998877",
  "document_id": "doc_bctc_2025_001",
  "status": "IN_PROGRESS",
  "progress_percentage": 45,
  "current_stage": "VLM_TABLE_EXTRACTION",
  "message_vi": "Đang dùng AI chuyên sâu đọc Bảng cân đối kế toán trang 1 (có dấu đỏ đè)...",
  "completed_page_preview": {
    "page_number": 1,
    "is_ready": true,
    "api_fetch_url": "/api/v1/documents/doc_bctc_2025_001/pages/1"
  }
}
```