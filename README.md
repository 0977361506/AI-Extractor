# Banking IDP Engine (giai đoạn 1)

Hệ thống chuẩn hóa hồ sơ ngân hàng: nhận PDF/ảnh scan/DOCX/PPTX/XLSX/HTML, xuất ra **JSON AST có bbox**, **Markdown** và **chunk RAG**, kèm giao diện đối chiếu cho RM. Chạy 100% on-premise; vùng khó được gửi tới **LLM Gateway MB** (chuẩn OpenAI).

- Thiết kế: [docs/plans/2026-10-19-banking-idp-design.md](docs/plans/2026-10-19-banking-idp-design.md)
- Roadmap và ghi chú triển khai: [docs/plans/2026-10-19-roadmap.md](docs/plans/2026-10-19-roadmap.md)
- Báo cáo chất lượng trên file mẫu: [docs/output/README.md](docs/output/README.md)

## Cài đặt (Windows, Python 3.13)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install --no-deps vietocr==0.3.13
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m idp.cli fetch-models     # tải model về ../models để chạy offline

cd ../frontend
npm install
npm run build                                    # backend phục vụ frontend/dist
```

## Sử dụng

```bash
# xử lý bằng dòng lệnh (kết quả + ảnh overlay)
backend/.venv/Scripts/python -m idp.cli process docs/examples/*.pdf --out docs/output

# chạy API + giao diện tại http://127.0.0.1:8000
backend/.venv/Scripts/python -m idp.cli serve

# kiểm tra kết nối LLM Gateway theo cài đặt đã lưu
backend/.venv/Scripts/python -m idp.cli vlm-test

# đo chất lượng so với nhãn đúng
backend/.venv/Scripts/python -m idp.cli eval --gt eval/ground_truth --pred docs/output
```

Biến môi trường (`IDP_*`): `IDP_DATA_DIR`, `IDP_MODELS_DIR`, `IDP_WORKERS`, `IDP_RENDER_DPI`; cấu hình VLM có thể đặt sẵn bằng `IDP_VLM_BASE_URL`, `IDP_VLM_API_KEY`, `IDP_VLM_MODEL`, `IDP_VLM_ENABLED`.

## Kiểm thử

```bash
cd backend && .venv/Scripts/python -m pytest -m "not slow"   # unit/contract (nhanh)
cd backend && .venv/Scripts/python -m pytest -m slow         # chạy model thật trên file mẫu
cd frontend && npx vitest run
```

## Cấu trúc

```
backend/idp/
  ingest/      nhận diện file, rasterize PDF/ảnh, lớp text PDF, VNI/TCVN3, Office/HTML
  preprocess/  hướng trang, xoay thẳng, cân bằng sáng, khử chấm bẩn/vệt sọc, tách mực màu
  layout/      Heron (Docling) qua transformers + hậu xử lý vùng
  ocr/         PaddleOCR detector (RapidOCR/ONNX) + VietOCR
  table/       dò lưới bảng có đường kẻ, OCR từng ô, bảng không đường kẻ, số tiền VN, kiểm tra số học
  elements/    checkbox, dấu, vòng khoanh, chữ ký, trường biểu mẫu viết tay
  assemble/    thứ tự đọc, đoạn văn, cấp tiêu đề, ghép bảng qua trang, Markdown, chunk RAG
  vlm/         cài đặt, client gateway, định tuyến, hiệu chỉnh, kiểm tra kết nối
  jobs/ api/   SQLite, job runner (ProcessPool), FastAPI + SSE, chỉnh sửa có dấu vết kiểm toán
  evaluation/  CER, TEDS
frontend/src/  React: danh sách hồ sơ, đối chiếu chia đôi màn hình, sửa bảng, cài đặt VLM
```
