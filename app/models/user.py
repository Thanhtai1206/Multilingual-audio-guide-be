"""Model USER: tài khoản quản trị (admin hoặc editor) của hệ thống.

Ánh xạ ERD:   USER  (collection MongoDB: `users`)
Quan hệ:      1 USER tạo nhiều POI (POI.created_by)
              1 USER kích hoạt nhiều PROCESSING_JOB (PROCESSING_JOB.triggered_by)
Index (do `db/indexes.py` tạo, nhóm C phụ trách):
              unique trên `username`; unique trên `email`.

LƯU Ý BẢO MẬT:
  - Chỉ lưu `password_hash`, KHÔNG BAO GIỜ lưu mật khẩu thô. Việc băm mật khẩu
    làm ở Service (auth_service), model chỉ giữ kết quả đã băm.
  - Khi trả user ra API, lớp schemas phải LOẠI `password_hash` khỏi response.
"""
from datetime import datetime

from pydantic import EmailStr, Field

from app.models.base import MongoModel, utc_now
from app.models.enums import Role

# Chữ, số, dấu gạch dưới, gạch ngang, dấu chấm; không có khoảng trắng.
# Biến này dùng để validate username khi tạo user mới, và cũng dùng để validate username khi login.
USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


class User(MongoModel):
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr = Field(description="Email hợp lệ, dùng để định danh/liên hệ")
    password_hash: str = Field(min_length=1, description="Mật khẩu ĐÃ BĂM, không phải mật khẩu thô")
    role: Role = Field(default=Role.EDITOR, description="admin: toàn quyền; editor: không quản lý ngôn ngữ")
    is_active: bool = Field(default=True, description="False = tài khoản bị khóa, không đăng nhập được")
    created_at: datetime = Field(default_factory=utc_now)
