## Mô tả
<!-- PR này làm gì? Closes #<số issue> -->

## Lớp bị ảnh hưởng
- [ ] Lớp 1 — API (`app/api/`)
- [ ] Lớp 2 — Service (`app/services/`)
- [ ] Lớp 3 — Repository / Integration
- [ ] Frontend / Docs / CI

## Checklist
- [ ] Router không chứa nghiệp vụ, không gọi Repository trực tiếp
- [ ] Service không import `fastapi`
- [ ] Đã viết/cập nhật test; `pytest` chạy xanh
- [ ] `ruff check . && ruff format --check .` không lỗi
- [ ] Không commit `.env`, API key, mật khẩu
