# 🌐 Hệ Thống Thuyết Minh Tự Động Đa Ngôn Ngữ - Backend Service

## 📖 Tổng quan Đề tài
Đồ án **"Thuyết minh tự động đa ngôn ngữ"** được phát triển nhằm cung cấp giải pháp công nghệ backend mạnh mẽ, phục vụ việc quản lý, xử lý và phân phối nội dung thuyết minh tự động bằng nhiều ngôn ngữ khác nhau cho các hệ thống tham quan, bảo tàng và du lịch thông minh.

## ⚙️ Trách nhiệm & Vai trò của Nhóm (Phần 2: Backend Development)
Nhóm chúng tôi chịu trách nhiệm chính trong việc phát triển và vận hành hệ thống Backend theo các tiêu chuẩn kỹ thuật sau:
* **Kiến trúc 3 lớp (3-Tier Architecture):** Xây dựng mã nguồn phân tầng rõ ràng (Presentation/Controller Layer, Business Logic Layer, Data Access Layer) giúp mã nguồn dễ bảo trì, mở rộng và tách biệt các tầng xử lý dữ liệu.
* **Quy trình CI/CD:** Tích hợp tự động hóa quy trình kiểm thử, build và triển khai ứng dụng, đảm bảo tính ổn định và tốc độ cập nhật mã nguồn liên tục lên môi trường chạy thực tế.
* **Xử lý API & Dữ liệu đa ngôn ngữ:** Thiết kế các API RESTful hiệu suất cao phục vụ việc tra cứu, đồng bộ hóa nội dung thuyết minh và quản lý thông tin đa ngôn ngữ cho hệ thống client.

## 📂 Cấu Trúc Thư Mục

```mermaid
multilingual-audio-guide/
├── .github/workflows/
│   ├── ci.yml                      # [C] lint + test mỗi lần push/PR
│   └── cd.yml                      # [C] build Docker image + triển khai
├── app/
│   ├── main.py                     # [A] khởi tạo FastAPI, gắn router
│   ├── core/                       # [C] dùng chung
│   │   ├── config.py               #     đọc biến môi trường (.env)
│   │   └── exceptions.py           #     lỗi nghiệp vụ: NotFoundError, ...
│   ├── models/                     # [CẢ NHÓM] thực thể nghiệp vụ (Pydantic)
│   │   ├── poi.py
│   │   ├── translation.py
│   │   └── language.py
│   ├── api/                        # ===== LỚP 1: Presentation [A] =====
│   │   ├── deps.py                 #     inject service vào router
│   │   ├── error_handlers.py       #     đổi lỗi nghiệp vụ → HTTP 404/422/...
│   │   └── v1/
│   │       ├── router.py
│   │       ├── pois.py
│   │       ├── translations.py
│   │       ├── languages.py
│   │       └── health.py
│   ├── schemas/                    # [A] request/response DTO của API
│   ├── services/                   # ===== LỚP 2: Business Logic [B] =====
│   │   ├── poi_service.py
│   │   ├── translation_service.py
│   │   ├── audio_service.py
│   │   └── providers/              #     gọi dịch vụ ngoài
│   │       ├── translator.py       #     dịch (LLM/OpenRouter)
│   │       └── tts.py              #     edge-tts → file mp3
│   ├── repositories/               # ===== LỚP 3: Data Access [C] =====
│   │   ├── poi_repository.py
│   │   ├── translation_repository.py
│   │   └── language_repository.py
│   └── db/                         # [C]
│       ├── mongo.py                #     kết nối MongoDB
│       ├── indexes.py              #     tạo index khi khởi động
│       └── seed.py                 #     nạp danh sách ngôn ngữ mẫu
├── tests/
│   ├── test_api/                   # [A] mock Service
│   ├── test_services/              # [B] mock Repository + provider
│   └── test_repositories/          # [C] chạy với MongoDB thật (Docker)
├── frontend/                       # HTML/CSS/JS demo (làm sau, cả nhóm)
├── storage/audio/                  # file mp3 sinh ra — phải nằm trong .gitignore
├── docs/                           # sơ đồ kiến trúc, ERD, API, báo cáo
├── Dockerfile                      # [C]
├── docker-compose.yml              # [C] app + MongoDB
├── requirements.txt
├── .env.example                    # KHÔNG commit .env thật
└── README.md
```


## 📂 Cấu Trúc Thư Mục Backend (3 Lớp & CI/CD)
* `/src/main/java/controller` (Presentation Layer): Tiếp nhận HTTP Request từ client và trả về kết quả API.
* `/src/main/java/service` (Business Logic Layer): Xử lý toàn bộ logic nghiệp vụ của hệ thống thuyết minh tự động.
* `/src/main/java/dao` (Data Access Layer): Chứa các thành phần kết nối và truy vấn cơ sở dữ liệu.
* `.github/workflows`: Chứa các file cấu hình tự động hóa CI/CD (GitHub Actions).
* `/docs`: Lưu trữ tài liệu thiết kế và báo cáo đồ án của nhóm.

## ERD
```
erDiagram
  USER ||--o{ POI : "tạo"
  USER ||--o{ PROCESSING_JOB : "kích hoạt"
  CATEGORY ||--o{ POI : "phân loại"
  LANGUAGE ||--o{ POI : "ngôn ngữ gốc của"
  LANGUAGE ||--o{ TRANSLATION : "ngôn ngữ đích của"
  POI ||--o{ TRANSLATION : "có"
  TRANSLATION ||--o{ AUDIO_FILE : "được đọc thành"
  TRANSLATION ||--o{ PROCESSING_JOB : "được theo dõi bởi"

  USER {
    objectid id PK
    string username UK
    string email UK
    string password_hash
    string role "admin hoặc editor"
    boolean is_active
    datetime created_at
  }
  LANGUAGE {
    string code PK "vi, en, ja, ko"
    string name
    string tts_voice
    boolean is_active
  }
  CATEGORY {
    objectid id PK
    string name UK
    string description
  }
  POI {
    objectid id PK
    string name
    string source_text
    string source_lang FK
    objectid category_id FK
    objectid created_by FK
    float latitude
    float longitude
    datetime created_at
    datetime updated_at
  }
  TRANSLATION {
    objectid id PK
    objectid poi_id FK, UK
    string lang FK, UK
    string translated_name
    string translated_text
    string status "pending, done, failed"
    string origin "auto hoặc manual"
    datetime updated_at
  }
  AUDIO_FILE {
    objectid id PK
    objectid translation_id FK
    string voice
    string file_path
    string format
    int duration_sec
    int size_bytes
    string status "pending, done, failed"
    datetime created_at
  }
  PROCESSING_JOB {
    objectid id PK
    objectid translation_id FK
    objectid triggered_by FK
    string job_type "translate hoặc tts"
    string status "pending, running, done, failed"
    string error_message
    datetime started_at
    datetime finished_at
  }
  ```

## 👥 Thành Viên Nhóm
* **Trương Công Danh**
* **Võ Thành Tài**
* **Nguyễn Lê Tấn Phát**
