# 6. Quy ước làm việc nhóm trên GitHub

Đề bài yêu cầu *"giao tiếp qua GitHub"* — giảng viên sẽ xem lịch sử commit, PR, review để đánh giá đóng góp từng người.

## 6.1 Phân công theo lớp (đề xuất)

| Thành viên | Lớp | Thư mục sở hữu | Test |
|---|---|---|---|
| Trương Công Danh | 1 — Presentation | `app/api/` (router, schema, deps, errors) | `tests/test_api/` |
| Võ Thành Tài | 2 — Business Logic | `app/services/`, `app/models/` | `tests/test_services/` |
| Nguyễn Lê Tấn Phát | 3 — Data Access + DevOps | `app/repositories/`, `app/integrations/`, `app/db/`, `.github/`, `Dockerfile` | `tests/test_repositories/` |
| Cả nhóm | Frontend, tài liệu | `frontend/`, `docs/` | `tests/test_e2e.py` |

Mỗi người nên làm được **một tính năng xuyên 3 lớp** (vd thêm trường mới cho POI: schema → service → repository) để hiểu toàn bộ luồng khi vấn đáp.

## 6.2 Nhánh (branch)

```
main      ← chỉ nhận merge qua PR, luôn deploy được (CD chạy từ đây)
develop   ← nhánh tích hợp hằng ngày
feature/<tên-ngắn>   vd feature/chat-rate-limit
fix/<tên-ngắn>       vd fix/geofence-cooldown
docs/<tên-ngắn>      vd docs/erd
```

## 6.3 Commit message (Conventional Commits)

```
<loại>(<phạm vi>): <mô tả ngắn, tiếng Việt được>

feat(api): thêm endpoint gợi ý lộ trình
fix(service): sửa lỗi fallback khi bản dịch lỗi
test(repo): thêm test index unique cho access_sessions
ci: chạy integration test với MongoDB 7
docs: cập nhật ERD
```
Loại: `feat`, `fix`, `test`, `refactor`, `docs`, `ci`, `chore`.

## 6.4 Quy trình một tính năng

1. Tạo **Issue** mô tả việc cần làm, gán người, gắn label (`api`, `service`, `repository`, `ci`, `bug`).
2. `git checkout develop && git pull && git checkout -b feature/xxx`
3. Code + viết test **ở đúng lớp của mình**. Chạy `pytest` và `ruff check . && ruff format .` trước khi push.
4. Mở **Pull Request** vào `develop`, ghi `Closes #<số issue>`, điền template.
5. CI phải xanh + ít nhất 1 thành viên khác **review & approve**.
6. *Squash and merge*. Cuối mỗi tuần/mốc: PR `develop → main` để deploy.

## 6.5 Checklist review

- [ ] Router có chứa logic nghiệp vụ hoặc gọi Repository trực tiếp không? (không được)
- [ ] Service có import thứ gì từ `fastapi` không? (không được)
- [ ] Lỗi nghiệp vụ dùng exception trong `app/core/exceptions.py`, không `HTTPException` ở Service
- [ ] Có test cho trường hợp thành công **và** thất bại
- [ ] Không commit `.env`, API key, mật khẩu
