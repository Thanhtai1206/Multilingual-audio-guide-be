# 2. ERD — Thiết kế dữ liệu (MongoDB, 13 collection)

MongoDB không có khóa ngoại thật; quan hệ được thể hiện bằng trường `*_id` và được **lớp Service** đảm bảo (ví dụ: xóa POI thì Service xóa luôn bản dịch và gỡ POI khỏi các tour).

```mermaid
erDiagram
    LANGUAGES ||--o{ POI_LOCALIZATIONS : "lang"
    POIS ||--o{ POI_LOCALIZATIONS : "poi_id"
    POIS }o--o{ TOURS : "poi_ids[]"
    POIS ||--o{ VISIT_EVENTS : "poi_id"
    ADMIN_USERS ||--o{ ACCESS_SESSIONS : "created_by (tiền mặt)"
    ACCESS_SESSIONS ||--o| PAYMENTS : "session_id (online)"
    ACCESS_SESSIONS ||--o{ CHAT_LOGS : "session_id"
    ACCESS_SESSIONS ||--o{ VISIT_EVENTS : "session_id"
    KNOWLEDGE_ARTICLES }o--o{ CHAT_LOGS : "source_ids[]"

    LANGUAGES {
        ObjectId _id
        string code UK "vi, en, zh..."
        string name
        string native_name
        string translator_code "zh-CN cho Google"
        string tts_voice "vi-VN-HoaiMyNeural"
        bool is_active
        int sort_order
    }
    POIS {
        ObjectId _id
        string code UK
        string name "tiếng Việt gốc"
        string description "tiếng Việt gốc"
        string category
        float latitude
        float longitude
        int trigger_radius_m "bán kính geofence"
        int priority
        string thumbnail_url
        string[] image_urls
        int sort_order
        bool is_active
        datetime created_at
        datetime updated_at
    }
    POI_LOCALIZATIONS {
        ObjectId _id
        string poi_id FK
        string lang FK
        string name
        string description
        string audio_url
        string status "pending|processing|ready|failed|outdated"
        string translated_by "source|machine|manual"
        string source_hash "MD5 nội dung gốc lúc dịch"
        string error
        datetime updated_at
    }
    TOURS {
        ObjectId _id
        string code UK
        string name
        string description
        string[] poi_ids "có thứ tự"
        int estimated_minutes
        object translations "{lang: {name, description}}"
        object translation_requested_at "{lang: datetime}"
        bool is_active
    }
    ADMIN_USERS {
        ObjectId _id
        string username UK
        string password_hash "bcrypt"
        string full_name
        string role "admin|staff"
        bool is_active
        datetime last_login_at
    }
    ACCESS_SESSIONS {
        ObjectId _id
        string code UK "6 ký tự, khách nhập"
        string method "cash|online"
        string status "pending|paid|active|expired|cancelled"
        int amount
        string created_by FK
        datetime code_expires_at
        datetime paid_at
        datetime activated_at
        datetime access_expires_at
    }
    PAYMENTS {
        ObjectId _id
        string session_id FK
        string provider "mock (Payoo)"
        int amount
        string status "pending|success|failed"
        string provider_ref
        datetime completed_at
    }
    KNOWLEDGE_ARTICLES {
        ObjectId _id
        string title
        string content
        string[] tags
        bool is_active
    }
    CHAT_LOGS {
        ObjectId _id
        string session_id FK
        string lang
        string question
        string answer
        string[] source_ids
        bool used_llm
        datetime created_at
    }
    VISIT_EVENTS {
        ObjectId _id
        string session_id FK
        string poi_id FK
        string lang
        string type "view|audio_play|geofence_enter"
        datetime created_at
    }
```

## Mô hình lưu nội dung đa ngôn ngữ

- Nội dung **gốc** (tiếng Việt) nằm trong `pois`. Admin chỉ nhập tiếng Việt.
- Mỗi ngôn ngữ là **1 document** trong `poi_localizations`, khóa duy nhất `(poi_id, lang)`.
- `source_hash = MD5(name + description gốc)`. Bản dịch chỉ **hợp lệ** khi `source_hash` khớp nội dung gốc hiện tại → sửa mô tả gốc thì mọi bản dịch cũ tự động không được dùng nữa, hệ thống dịch lại ở nền.
- `translated_by = manual`: admin sửa tay → dịch máy không ghi đè (trừ khi chọn "Dịch lại toàn bộ").

**Vì sao không nhúng `translations` vào `pois`?** 16 ngôn ngữ × (mô tả dài + trạng thái + lỗi) làm document POI phình to, mỗi lần cập nhật 1 ngôn ngữ phải ghi cả document, và khó truy vấn "các bản dịch đang lỗi". Tour thì ngắn (chỉ tên + mô tả 1 câu) nên nhúng `translations` cho đơn giản.

## Index

| Collection | Index | Mục đích |
|---|---|---|
| languages | `code` unique | |
| pois | `code` unique; `(is_active, sort_order)` | |
| poi_localizations | `(poi_id, lang)` unique | upsert, tra cứu nhanh |
| tours | `code` unique | |
| admin_users | `username` unique | |
| access_sessions | `code` unique; `(status, created_at)` | đổi mã, lọc lịch sử |
| payments | `session_id` | |
| chat_logs | `(session_id, created_at)` | giới hạn số câu/ngày |
| visit_events | `(poi_id, created_at)` | thống kê |
| ui_translations | `lang` unique | nhãn giao diện đã dịch |
| chat_cache | `key` unique; **TTL** trên `expires_at` | MongoDB tự xóa cache hết hạn |
| media_files | `key` unique | file audio (key = MD5 nội dung + giọng) |

## Collection phụ trợ (không phải thực thể nghiệp vụ)

| Collection | Nội dung | Ghi chú |
|---|---|---|
| `ui_translations` | `{lang, strings: {key: text}, source_hash}` | Dịch 1 lần / ngôn ngữ, dịch lại khi chuỗi gốc đổi |
| `chat_cache` | `{key, answer, expires_at}` | Cache câu trả lời chatbot, hết hạn sau `CHAT_CACHE_TTL_SECONDS` |
| `media_files` | `{key, data: Binary, content_type, size}` | File mp3 ~50–300 KB (< 16 MB/document); phục vụ qua `/media/...`, hỗ trợ tua (HTTP Range) |
