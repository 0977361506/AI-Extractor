# AI-Extractor — Banking IDP Engine

Chuẩn hóa hồ sơ ngân hàng: nhận PDF, ảnh scan, DOCX, PPTX, XLSX, HTML và xuất ra **JSON có toạ độ (bbox)**,
**Markdown** và **chunk cho RAG**, kèm giao diện để RM xem từng bước xử lý và đối chiếu kết quả với bản gốc.
Chạy hoàn toàn on-premise trên CPU. Các vùng khó đọc có thể gửi tới **LLM Gateway nội bộ** (chuẩn OpenAI) nếu được bật.

- [Chạy trên máy không có internet (gói Windows)](#chạy-trên-máy-không-có-internet-gói-windows)
- [Tạo gói Windows](#tạo-gói-windows)
- [Môi trường phát triển](#môi-trường-phát-triển)
- Thiết kế: [docs/plans/2026-10-19-banking-idp-design.md](docs/plans/2026-10-19-banking-idp-design.md) ·
  màn xử lý từng bước: [docs/plans/2026-10-20-pipeline-stepper-design.md](docs/plans/2026-10-20-pipeline-stepper-design.md) ·
  chất lượng trên file mẫu: [docs/output/README.md](docs/output/README.md)

---

## Chạy trên máy không có internet (gói Windows)

Gói `AI-Extractor-win64-<phiên bản>.zip` chứa sẵn Python, toàn bộ thư viện, model và giao diện.
Máy chạy **không cần internet, không cần cài Python/Node, không cần quyền quản trị**.

### Yêu cầu máy

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| Hệ điều hành | Windows 10 / Windows Server 2016, 64-bit | Windows 11 / Server 2022 |
| CPU | x64 hỗ trợ AVX2 (Intel thế hệ 4 / AMD Ryzen trở lên) | 4 nhân trở lên |
| RAM | 8 GB | 16 GB (mỗi hồ sơ xử lý song song dùng 2–3 GB) |
| Ổ đĩa | 4 GB trống + dung lượng hồ sơ | SSD |
| GPU | không cần | — |

### Cài và chạy

1. Chép file zip vào máy. Nếu file được tải từ internet về: chuột phải → **Properties** → tick **Unblock** → **OK**
   trước khi giải nén (để Windows không chặn các file `.dll` bên trong).
2. Giải nén vào một **đường dẫn ngắn**, ví dụ `C:\AI-Extractor`. Tránh thư mục sâu như Desktop của user dài,
   vì vài thư viện có đường dẫn file dài, có thể vượt giới hạn 260 ký tự của Windows.
3. Bấm đúp **`run.bat`**. Lần đầu mất khoảng 30–60 giây để nạp model; khi cửa sổ hiện `Uvicorn running on http://127.0.0.1:8000`
   thì mở trình duyệt tới **http://127.0.0.1:8000**.
4. Kéo hồ sơ vào trang chủ để xem xử lý từng bước, xong bấm **Mở đối chiếu**.
5. Dừng: đóng cửa sổ `run.bat` hoặc nhấn `Ctrl+C` trong đó.

### Cho các máy khác trong mạng nội bộ dùng chung

```bat
run.bat --host 0.0.0.0 --port 8000
```

Sau đó mở cổng 8000 trên Windows Firewall (Inbound rule, TCP 8000) và truy cập `http://<IP máy chủ>:8000`.
Ứng dụng **không có đăng nhập** ở giai đoạn này — chỉ mở trong mạng được phép.

### Cấu hình (không bắt buộc)

Chép `.env.example` thành `.env` (cùng thư mục với `run.bat`) rồi bỏ dấu `#` ở dòng cần đổi:

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `IDP_DATA_DIR` | nơi lưu hồ sơ, kết quả, CSDL SQLite | `data\` trong thư mục gói |
| `IDP_WORKERS` | số hồ sơ xử lý song song | `2` |
| `IDP_RENDER_DPI` | độ phân giải khi chuyển PDF thành ảnh | `300` |
| `IDP_VLM_ENABLED`, `IDP_VLM_BASE_URL`, `IDP_VLM_API_KEY`, `IDP_VLM_MODEL` | kết nối LLM Gateway | tắt |

Kết nối LLM Gateway cũng có thể nhập trên giao diện: **Cài đặt VLM** → **Kiểm tra kết nối** → **Lưu**.

### Dòng lệnh

```bat
idp.bat process "D:\ho_so\giay_de_nghi.pdf" --out "D:\ket_qua"   :: xử lý không cần giao diện
idp.bat vlm-test                                                :: kiểm tra kết nối LLM Gateway
idp.bat --help
```

### Sao lưu và nâng cấp

- Toàn bộ dữ liệu nằm trong `data\` (hoặc thư mục `IDP_DATA_DIR`): sao lưu thư mục này là đủ.
- Nâng cấp: giải nén bản mới ra thư mục mới, chép `data\` và `.env` từ bản cũ sang, rồi chạy `run.bat` của bản mới.
- Gỡ bỏ: xoá thư mục. Gói không ghi gì vào registry hay ngoài thư mục của nó (trừ khi `IDP_DATA_DIR` trỏ ra ngoài).

### Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `run.bat` mở rồi tắt ngay | Mở `cmd`, `cd` vào thư mục gói, chạy `run.bat` để đọc lỗi |
| `address already in use` / `10048` | Cổng đang bận: `run.bat --port 8010` |
| Windows SmartScreen chặn `run.bat` | **More info** → **Run anyway**, hoặc Unblock file zip trước khi giải nén |
| Lỗi `DLL load failed` | Thường do file bị chặn: Unblock zip rồi giải nén lại; hoặc CPU không hỗ trợ AVX2 |
| Xử lý chậm | Giảm `IDP_WORKERS` về `1` trên máy ít RAM; máy nhiều nhân có thể tăng lên |
| Trang web không cập nhật sau khi nâng cấp | Nhấn `Ctrl+F5` |

---

## Tạo gói Windows

Làm trên một máy Windows **có internet** (chỉ cần một lần cho mỗi phiên bản), sau khi đã dựng xong
[môi trường phát triển](#môi-trường-phát-triển):

```bat
cd backend
.venv\Scripts\python -m idp.cli fetch-models      :: tải Heron, VietOCR và model ONNX của RapidOCR
cd ..\frontend
npm ci && npm run build                           :: build giao diện vào frontend\dist
cd ..
backend\.venv\Scripts\python packaging\build_windows.py
```

Kết quả: thư mục `dist\AI-Extractor-win64\` và file `dist\AI-Extractor-win64-<commit>.zip` (khoảng 1 GB).
Script tự kiểm tra gói bằng cách nạp toàn bộ model trong một môi trường giả lập máy không internet
(không có Python của máy build trên PATH, không có cache người dùng, mạng bị chặn) — nếu thiếu gì, build sẽ dừng và báo.

File zip **không đưa vào git** (GitHub giới hạn 100 MB/file). Phát hành bằng một trong hai cách:

- GitHub: vào **Releases** → **Draft a new release** → kéo file zip vào phần đính kèm (tối đa 2 GB/file).
- Chép trực tiếp qua kênh chuyển dữ liệu được phép của ngân hàng.

Gói chứa: Python embeddable chính thức 3.13 (`python\`), thư viện đã cài (`python\Lib\site-packages`),
runtime Visual C++ đặt cạnh `python.exe`, mã nguồn (`backend\idp`), giao diện (`frontend\dist`), model (`models\`).

---

## Môi trường phát triển

Windows, Python 3.13, Node 18+.

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

`vietocr` được cài với `--no-deps` vì nó ghim các phiên bản thư viện cũ, xung đột với torch/numpy mới.

### Sử dụng

```bash
# chạy API + giao diện tại http://127.0.0.1:8000
backend/.venv/Scripts/python -m idp.cli serve

# xử lý bằng dòng lệnh (kết quả + ảnh overlay)
backend/.venv/Scripts/python -m idp.cli process docs/examples/*.pdf --out docs/output

# kiểm tra kết nối LLM Gateway theo cài đặt đã lưu
backend/.venv/Scripts/python -m idp.cli vlm-test

# đo chất lượng so với nhãn đúng
backend/.venv/Scripts/python -m idp.cli eval --gt eval/ground_truth --pred docs/output
```

Biến môi trường (`IDP_*`): `IDP_DATA_DIR`, `IDP_MODELS_DIR`, `IDP_WORKERS`, `IDP_RENDER_DPI`; cấu hình VLM có thể đặt sẵn bằng
`IDP_VLM_BASE_URL`, `IDP_VLM_API_KEY`, `IDP_VLM_MODEL`, `IDP_VLM_ENABLED`.

### Kiểm thử

```bash
cd backend && .venv/Scripts/python -m pytest -m "not slow"   # unit/contract (nhanh)
cd backend && .venv/Scripts/python -m pytest -m slow         # chạy model thật trên file mẫu
cd frontend && npx vitest run
```

### Cấu trúc

```
backend/idp/
  ingest/      nhận diện file, rasterize PDF/ảnh, lớp text PDF, VNI/TCVN3, Office/HTML (+ bản xem trước HTML)
  preprocess/  hướng trang, xoay thẳng, cân bằng sáng, khử chấm bẩn/vệt sọc, tách mực màu
  layout/      Heron (Docling) qua transformers + hậu xử lý vùng
  ocr/         PaddleOCR detector (RapidOCR/ONNX) + VietOCR
  table/       dò lưới bảng có đường kẻ, OCR từng ô, bảng không đường kẻ, số tiền VN, kiểm tra số học
  elements/    checkbox, dấu, vòng khoanh, chữ ký, trường biểu mẫu viết tay
  assemble/    thứ tự đọc, đoạn văn, cấp tiêu đề, ghép bảng qua trang, Markdown, chunk RAG
  pipeline/    điều phối trang/tài liệu, ghi dữ liệu từng bước (trace) cho màn xử lý từng bước
  vlm/         cài đặt, client gateway, định tuyến, hiệu chỉnh, kiểm tra kết nối
  jobs/ api/   SQLite, job runner (ProcessPool), FastAPI + SSE, chỉnh sửa có dấu vết kiểm toán
  evaluation/  CER, TEDS
frontend/src/  React: trang chủ (tiếp nhận + xử lý từng bước), đối chiếu chia đôi màn hình, sửa bảng, cài đặt VLM
packaging/     build_windows.py — tạo gói chạy offline cho Windows
```
