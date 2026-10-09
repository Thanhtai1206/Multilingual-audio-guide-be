# 8. So sánh với project ban đầu (Gap Analysis)

Project ban đầu (`backend/app.py`, 132 dòng) là một demo "AI Audio Tour Guide": nhập tên địa điểm → gọi LLM viết kịch bản tiếng Anh → Edge-TTS đọc. Mọi thứ nằm trong 1 file.

| Tiêu chí (Option 2 + PRD) | Ban đầu | Hiện tại |
|---|---|---|
| Kiến trúc 3 lớp | ❌ 1 file gộp route + gọi AI + ghi file | ✅ `api/` → `services/` → `repositories/` + `integrations/` |
| Cơ sở dữ liệu | ❌ Không có | ✅ MongoDB, 10 collection, index, seed |
| Đa ngôn ngữ | ❌ Chỉ tiếng Anh, giọng cố định | ✅ 16 ngôn ngữ, dịch tự động, giọng riêng từng ngôn ngữ, fallback 3 tầng, sửa tay |
| POI + GPS (PRD) | ❌ | ✅ POI có tọa độ + bán kính, nearby, geofence trên app |
| Lộ trình (PRD) | ❌ | ✅ Tour cố định + gợi ý thứ tự theo vị trí |
| Chatbot RAG (PRD) | ❌ | ✅ BM25 + LLM tùy chọn, giới hạn/ngày, cache |
| Thanh toán / mã truy cập (PRD) | ❌ | ✅ Online (cổng giả lập + webhook HMAC) và tiền mặt (mã 6 ký tự) |
| Admin dashboard (PRD) | ❌ | ✅ Quản lý POI, bản dịch, tour, mã, kiến thức, ngôn ngữ, tài khoản |
| Giám sát (PRD) | ❌ | ✅ Thống kê, health/readiness |
| Xác thực, phân quyền | ❌ | ✅ JWT, bcrypt, role admin/staff |
| Xử lý lỗi | ❌ `print` + HTTP 500 | ✅ Exception nghiệp vụ + handler tập trung, response chuẩn |
| Test | ❌ 0 test | ✅ 162 test, 3 lớp + E2E, coverage ~92% |
| CI/CD | ❌ | ✅ GitHub Actions CI (lint, test, integration, Docker) + CD (GHCR, Render) |
| Cấu hình | ⚠️ `.env` chứa API key nằm trong file zip | ✅ `.env.example`, `.gitignore`, fail-fast ở production |
| README | ⚠️ Mô tả cấu trúc Java (`src/main/java/...`) không khớp code Python | ✅ Khớp code thật |

## Những gì được giữ lại
- Ý tưởng dùng **Edge-TTS** (miễn phí, giọng tốt) và **OpenRouter** cho LLM.
- Hàm làm sạch Markdown trước khi đọc (`clean_for_speech`).

## ⚠️ Việc cần làm ngay
File zip ban đầu có `.env` chứa **OPENROUTER_API_KEY thật**. Nếu repo/zip đã từng được chia sẻ, hãy vào https://openrouter.ai/keys **thu hồi key cũ và tạo key mới**, và đảm bảo `.env` không bao giờ được commit.
