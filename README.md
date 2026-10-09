# Thuyết Minh Tự Động Đa Ngôn Ngữ — Chùa Linh Ứng (Backend 3 lớp + CI/CD)

Đồ án môn **Công nghệ phần mềm** — đề tài *"Thuyết minh tự động đa ngôn ngữ"*, **yêu cầu 2: BE Dev theo hướng 3 lớp bao gồm CI/CD**.

Du khách quét QR ở cổng chùa → mua quyền truy cập (online hoặc tiền mặt) → mở bản đồ, đi tới điểm nào thì app **tự phát thuyết minh** bằng ngôn ngữ của họ (16 ngôn ngữ), có **chatbot** hỏi đáp và **gợi ý lộ trình**. Ban quản lý dùng **dashboard** để nhập nội dung tiếng Việt — hệ thống tự dịch và tạo audio.

| Thành phần | Công nghệ |
|---|---|
| Backend | Python 3.11 – 3.14 · FastAPI · Pydantic v2 |
| Database | MongoDB 7 (Motor async) — local, Docker hoặc Atlas |
| Đa ngôn ngữ | deep-translator (Google Translate) · Edge-TTS (giọng đọc Microsoft, miễn phí) |
| Chatbot | AI tạo sinh (Google Gemini miễn phí / Groq / OpenRouter) + RAG trên tài liệu của chùa, chỉ trả lời trong phạm vi Chùa Linh Ứng |
| Frontend | HTML/CSS/JavaScript thuần · Leaflet (bản đồ) |
| CI/CD | GitHub Actions · Docker · GHCR · Render |

## Thành viên

| Thành viên | Phụ trách (đề xuất theo lớp) |
|---|---|
| **Trương Công Danh** | Lớp 1 — Presentation: `app/api/`, `tests/test_api/` |
| **Võ Thành Tài** | Lớp 2 — Business Logic: `app/services/`, `tests/test_services/` |
| **Nguyễn Lê Tấn Phát** | Lớp 3 — Data Access + CI/CD: `app/repositories/`, `app/integrations/`, `.github/workflows/` |

---

## Kiến trúc 3 lớp

```
                ┌──────────────────────────────────────────────┐
 Browser/App ──▶│ LỚP 1 · PRESENTATION   app/api/              │  nhận request, validate (Pydantic),
                │   routers · schemas · deps · errors           │  phân quyền, trả JSON chuẩn
                └───────────────────────┬──────────────────────┘
                                        ▼  chỉ gọi Service
                ┌──────────────────────────────────────────────┐
                │ LỚP 2 · BUSINESS LOGIC  app/services/        │  quy tắc nghiệp vụ: fallback ngôn ngữ,
                │   poi · localization · content · tour ·       │  vòng đời mã truy cập, geofence, RAG...
                │   access · payment · chat · auth · stats      │
                └───────────────────────┬──────────────────────┘
                                        ▼  chỉ gọi Repository / Integration
                ┌──────────────────────────────────────────────┐
                │ LỚP 3 · DATA ACCESS                           │
                │   app/repositories/  → MongoDB (10 collection)│
                │   app/integrations/  → Dịch máy, TTS, LLM,    │
                │                        cổng thanh toán, file  │
                └──────────────────────────────────────────────┘
```

**Quy tắc vàng:** luồng gọi **một chiều** `api → services → repositories`. Router không chứa nghiệp vụ, không chạm DB. Service không biết HTTP (ném `NotFoundError`, lớp API mới đổi thành 404). Chi tiết: [docs/01-kien-truc-3-lop.md](docs/01-kien-truc-3-lop.md).

## Cài đặt & chạy

### Bước 1 — Cài MongoDB (chọn 1 trong 3 cách)

**Cách A — Cài trên Windows (khuyên dùng khi code hằng ngày)**
1. Tải **MongoDB Community Server** (bản `.msi`) tại https://www.mongodb.com/try/download/community
   (hoặc mở PowerShell: `winget install MongoDB.Server`).
2. Khi cài chọn **Complete**, giữ nguyên tick **"Install MongoDB as a Service"** → MongoDB tự chạy mỗi khi bật máy.
   Nên tick thêm **MongoDB Compass** (giao diện xem dữ liệu).
3. Kiểm tra: mở `services.msc` → thấy **MongoDB Server (MongoDB)** ở trạng thái *Running*.
4. Mở Compass → *Connect* `mongodb://localhost:27017` để xem dữ liệu (database `audio_guide`).

**Cách B — Docker:** `docker compose up --build` (chạy cả MongoDB + backend, mở http://localhost:8000).
Chỉ muốn MongoDB trong Docker: `docker compose up -d mongo` rồi đặt `MONGO_URI=mongodb://localhost:27018` trong `.env`
(dùng cổng 27018 để không đụng MongoDB đã cài sẵn trên máy ở cổng 27017). Dữ liệu trong Docker tách riêng với MongoDB trên máy.

**Cách C — MongoDB Atlas (cloud, miễn phí, cả nhóm dùng chung 1 DB):** tạo cluster M0 theo
[docs/05-ci-cd.md](docs/05-ci-cd.md#bước-3--tạo-database-mongodb-atlas-free-m0), rồi đặt `MONGO_URI=mongodb+srv://...` trong `.env`.

### Bước 2 — Chạy backend

```bash
# Tạo + kích hoạt môi trường ảo
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate

# Cài thư viện (mọi thư viện đều có bản cài sẵn, không cần Visual C++/Rust)
pip install -r requirements-dev.txt

# Tạo file cấu hình (mặc định MONGO_URI=mongodb://localhost:27017)
copy .env.example .env        # macOS/Linux: cp .env.example .env

# Chạy server
uvicorn app.main:app --reload
```

Thấy dòng `Đã kết nối MongoDB` là thành công. Nếu MongoDB chưa chạy, server dừng ngay và in hướng dẫn khắc phục.

| Địa chỉ | Nội dung |
|---|---|
| http://localhost:8000 | App du khách (mở bằng điện thoại hoặc DevTools chế độ mobile) |
| http://localhost:8000/admin/ | Dashboard quản trị — `admin` / `admin123` |
| http://localhost:8000/docs | Swagger — thử trực tiếp các API |

Lần đầu chạy, hệ thống tự tạo 16 ngôn ngữ, tài khoản admin và **dữ liệu mẫu** (6 điểm tham quan, 2 lộ trình, 6 bài viết cho chatbot) — **chỉ một lần**, các lần sau dữ liệu được giữ nguyên.

### Thông tin chi tiết từng điểm (giống Google Maps)

Mỗi điểm tham quan có: **giờ mở cửa theo từng ngày** (nhiều khung/ngày, vd nghỉ trưa), trạng thái **Đang mở cửa / Sắp đóng cửa / Đã đóng cửa**, vé vào cửa, thời gian tham quan gợi ý, tiện ích & quy định, lưu ý (tự dịch 16 ngôn ngữ), biểu đồ **khung giờ đông khách**, nút **Chỉ đường**. Admin nhập ở form sửa điểm tham quan.

- Database tạo từ bản cũ? Lần khởi động sau, hệ thống **tự bổ sung** thông tin mẫu cho 6 điểm mẫu (không đụng điểm admin đã nhập).
- Biểu đồ đông khách tính từ lượt ghé thăm thật. Muốn demo khi chưa có khách: `python -m app.db.demo_events` (tạo 4 tuần dữ liệu **giả lập**), xóa bằng `python -m app.db.demo_events --clear`.

> Mẹo: Không ở chùa? Trong app tick ô **Giả lập GPS** rồi bấm lên bản đồ để **giả lập vị trí GPS** — đi vào vòng tròn của một điểm, sau ~3 giây app tự mở và phát thuyết minh.

### Bật chatbot AI tạo sinh (khuyên dùng)

1. Vào https://aistudio.google.com/apikey → đăng nhập Google → **Create API key** (miễn phí).
2. Dán vào file `.env`: `LLM_API_KEY=<key vừa tạo>` (không dấu nháy) rồi khởi động lại server.
   Key Google có thể bắt đầu bằng `AIza` hoặc dạng khác — đều dùng được. Muốn chắc chắn thì thêm `LLM_PROVIDER=gemini`.
3. Log khởi động có dòng `Chatbot dùng AI tạo sinh: gemini / gemini-3.8-flash` là đã bật.

Chatbot sẽ trả lời tự nhiên mọi câu hỏi về Chùa Linh Ứng (lịch sử, kiến trúc, Phật giáo, tham quan, đường đi...), nhớ ngữ cảnh vài câu trước, ưu tiên tài liệu do admin nhập, và **từ chối lịch sự** câu hỏi ngoài phạm vi. Không có key thì chatbot vẫn chạy ở chế độ trích đoạn tài liệu.

### Dữ liệu được lưu ở đâu?

Mọi thứ nằm trong **MongoDB** — tắt server, khởi động lại hay deploy lên cloud đều không mất:

| Dữ liệu | Collection |
|---|---|
| Điểm tham quan, bản dịch, lộ trình, ngôn ngữ | `pois`, `poi_localizations`, `tours`, `languages` |
| **File audio mp3** | `media_files` (đặt `MEDIA_STORAGE=local` nếu muốn lưu ra thư mục) |
| Tài khoản, mã truy cập, thanh toán | `admin_users`, `access_sessions`, `payments` |
| Chatbot: kiến thức, lịch sử, **cache câu trả lời** (tự hết hạn) | `knowledge_articles`, `chat_logs`, `chat_cache` |
| Nhãn giao diện đã dịch, thống kê | `ui_translations`, `visit_events` |

Server tắt khi đang dịch? Lần khởi động sau sẽ **tự chạy tiếp** các bản dịch còn dở.

Muốn xóa sạch để demo lại từ đầu: `python -m app.db.reset --yes`

## Kiểm thử

```bash
pytest                              # toàn bộ test (không cần MongoDB: dùng DB giả lập trong RAM)
pytest tests/test_api               # lớp 1 - API (mock Service)
pytest tests/test_services          # lớp 2 - nghiệp vụ
pytest tests/test_repositories      # lớp 3 - truy vấn DB
pytest tests/test_e2e.py            # tích hợp đầu-cuối theo kịch bản PRD
# Chạy toàn bộ test trên MongoDB thật (CI làm vậy):
#   Windows: $env:TEST_MONGO_URI="mongodb://localhost:27017"; pytest
pytest --cov                        # đo độ phủ (hiện ~89%)
ruff check . && ruff format --check .   # kiểm tra style
```

## CI/CD

```
push / PR ─▶ CI: lint ─▶ unit test (Py 3.11 + 3.12, coverage ≥ 80%) ─▶ build Docker + smoke test
                     └─▶ integration test trên MongoDB 7 thật ──────┘
merge main ─▶ CD: build image ─▶ push ghcr.io ─▶ Render deploy hook ─▶ kiểm tra /health/ready
```

Hướng dẫn bật CD lên Render + MongoDB Atlas (miễn phí): [docs/05-ci-cd.md](docs/05-ci-cd.md).

## Cấu trúc thư mục

```
app/
├── main.py                 # khởi tạo app, gắn router, khởi động/seed dữ liệu
├── core/                   # cấu hình, bảo mật (JWT, bcrypt, HMAC), ngoại lệ nghiệp vụ
├── models/                 # domain model (ERD) + view model của Service
├── api/          ◀ LỚP 1   # deps.py (DI), errors.py (xử lý lỗi tập trung), schemas/, v1/endpoints/
├── services/     ◀ LỚP 2   # nghiệp vụ
├── repositories/ ◀ LỚP 3   # truy cập MongoDB
├── integrations/ ◀ LỚP 3   # dịch máy, TTS, LLM, cổng thanh toán, lưu file
└── db/                     # kết nối, index, dữ liệu khởi tạo
frontend/                   # app du khách + admin/ (HTML/CSS/JS thuần)
tests/                      # test_api/ · test_services/ · test_repositories/ · test_e2e.py
docs/                       # tài liệu thiết kế, ERD, use case, API, CI/CD, quy ước, kịch bản demo
.github/workflows/          # ci.yml · cd.yml
```

## Tài liệu

1. [Kiến trúc 3 lớp](docs/01-kien-truc-3-lop.md)
2. [ERD — thiết kế dữ liệu](docs/02-erd.md)
3. [Use Case](docs/03-use-case.md)
4. [Danh sách API](docs/04-api-endpoints.md)
5. [CI/CD & triển khai](docs/05-ci-cd.md)
6. [Quy ước làm việc nhóm trên GitHub](docs/06-quy-uoc-github.md)
7. [Kịch bản demo (giữa kỳ / cuối kỳ)](docs/07-kich-ban-demo.md)
8. [So sánh với project ban đầu (Gap Analysis)](docs/08-gap-analysis.md)

## Lưu ý

- **Dữ liệu mẫu** (tọa độ, nội dung, giờ mở cửa) chỉ để minh họa — cần đo tọa độ thật tại chùa và đối chiếu nội dung với tài liệu chính thức trước khi demo.
- **Thanh toán** dùng cổng giả lập (không trừ tiền thật) thay cho Payoo trong PRD.
- Dịch máy và Edge-TTS cần Internet; mất mạng thì app tự lùi về tiếng Anh/tiếng Việt và giọng đọc của trình duyệt.
