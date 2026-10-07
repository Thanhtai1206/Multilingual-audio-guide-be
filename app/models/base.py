"""Lớp cha chung cho mọi model (chốt chung cả nhóm, không tự ý sửa riêng).

Quy ước của lớp Model (thực thể nghiệp vụ):
  1. Model chỉ mô tả DỮ LIỆU + LUẬT RÀNG BUỘC của một thực thể trong ERD.
     Không import fastapi, pymongo, bson ở đây (giữ ranh giới 3 lớp).
  2. Mọi id (kể cả khóa ngoại) là `str` trong code. Việc đổi str <-> ObjectId
     là trách nhiệm của lớp Repository, ở sát MongoDB.
  3. Thời gian luôn là UTC (xem `utc_now`).
"""
from datetime import datetime, timezone
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# Khi đọc từ MongoDB, `_id` là ObjectId. BeforeValidator(str) ép nó về str
# trước khi Pydantic kiểm tra, nên model không cần biết ObjectId là gì.
PyObjectId = Annotated[str, BeforeValidator(str)]


def utc_now() -> datetime:
    """Thời điểm hiện tại theo UTC (có tzinfo), dùng làm giá trị mặc định."""
    return datetime.now(timezone.utc)


class MongoModel(BaseModel):
    """Lớp cha: có sẵn trường `id` ánh xạ với `_id` của MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,      # cho phép tạo bằng id=... lẫn _id=...
        str_strip_whitespace=True,  # tự cắt khoảng trắng đầu/cuối chuỗi
        extra="ignore",             # bỏ qua trường lạ trong document cũ
    )

    # None khi đối tượng chưa được lưu; có giá trị sau khi Repository lưu xong.
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
