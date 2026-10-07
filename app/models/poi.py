"""Model POI: một điểm tham quan có nội dung thuyết minh gốc.

Ánh xạ ERD:   POI  (collection MongoDB: `pois`)
Quan hệ:      category_id -> CATEGORY.id      (có thể để trống)
              source_lang -> LANGUAGE.code
              created_by  -> USER.id
              1 POI có nhiều TRANSLATION
Index (do `db/indexes.py` tạo, nhóm C phụ trách):
              text index trên `name`; index thường trên `category_id`.

Model này là MẪU: các model còn lại viết theo cùng khung
(docstring -> hằng số -> class kế thừa MongoModel -> Field có ràng buộc
 -> validator cho luật liên trường).
"""
from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from app.models.base import MongoModel, utc_now

# Mã ngôn ngữ dạng "vi", "en", "ja" (2-3 chữ cái thường). Khớp LANGUAGE.code.
LANG_CODE_PATTERN = r"^[a-z]{2,3}$"

# Giới hạn độ dài nội dung gốc. Văn bản quá dài sẽ làm dịch/TTS chậm và tốn tiền,
# nên chặn ngay từ model thay vì để lỗi xảy ra ở dịch vụ ngoài.
SOURCE_TEXT_MAX_LENGTH = 5000


class POI(MongoModel):
    # --- Thông tin chính -------------------------------------------------
    name: str = Field(min_length=1, max_length=200, description="Tên điểm tham quan")
    source_text: str = Field(
        min_length=1,
        max_length=SOURCE_TEXT_MAX_LENGTH,
        description="Nội dung thuyết minh gốc, cần dịch sang các ngôn ngữ khác",
    )
    source_lang: str = Field(
        pattern=LANG_CODE_PATTERN,
        description="Mã ngôn ngữ của source_text, ví dụ 'vi'",
    )

    # --- Khóa ngoại (lưu dạng str, xem quy ước trong base.py) -------------
    category_id: Optional[str] = Field(default=None, description="Danh mục, có thể chưa phân loại")
    created_by: Optional[str] = Field(default=None, description="USER tạo ra POI này")

    # --- Vị trí (để dành cho mở rộng GPS, không bắt buộc) -----------------
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    # --- Dấu thời gian ----------------------------------------------------
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # --- Luật liên trường -------------------------------------------------
    @model_validator(mode="after")
    def _toa_do_phai_di_cung_nhau(self) -> "POI":
        """Hoặc có cả latitude và longitude, hoặc không có cái nào."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude và longitude phải cùng có hoặc cùng để trống")
        return self
