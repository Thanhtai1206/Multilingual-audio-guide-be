"""Model AUDIO_FILE: một file âm thanh sinh ra từ một bản dịch (TRANSLATION).

Ánh xạ ERD:   AUDIO_FILE  (collection MongoDB: `audio_files`)
Quan hệ:      translation_id -> TRANSLATION.id
              1 TRANSLATION có thể có nhiều AUDIO_FILE (ví dụ nhiều giọng đọc)
Index (do `db/indexes.py` tạo, nhóm C phụ trách):
              index thường trên `translation_id`.

Vòng đời trạng thái: pending -> done (hoặc failed). Khi mới tạo (pending) chưa có
file nên `file_path`, `duration_sec`, `size_bytes` cho phép để trống; chúng chỉ
bắt buộc khi status = done.
"""
from datetime import datetime # Import datetime để dùng default_factory=utc_now
from typing import Optional # Import Optional để dùng cho các trường có thể None

from pydantic import Field, model_validator # Import Field để định nghĩa các trường dữ liệu và model_validator để xác thực dữ liệu sau khi khởi tạo

from app.models.base import MongoModel, utc_now
from app.models.enums import Status

# Định dạng âm thanh: chữ thường/số, 2-5 ký tự (mp3, wav, ogg...).
AUDIO_FORMAT_PATTERN = r"^[a-z0-9]{2,5}$"

# Class này ánh xạ collection `audio_files` trong MongoDB, dùng để lưu thông tin file âm thanh sinh ra từ một bản dịch.
class AudioFile(MongoModel):
    # --- Khóa ngoại (str, xem quy ước trong base.py) ----------------------
    translation_id: str = Field(min_length=1, description="Bản dịch mà audio này đọc")

    # --- Thông tin âm thanh -----------------------------------------------
    voice: str = Field(min_length=1, max_length=100, description="Tên giọng đọc, ví dụ 'ja-JP-NanamiNeural'")
    format: str = Field(default="mp3", pattern=AUDIO_FORMAT_PATTERN)
    file_path: Optional[str] = Field(default=None, description="Đường dẫn file trên đĩa/URL, có khi status = done")
    duration_sec: Optional[int] = Field(default=None, ge=0)
    size_bytes: Optional[int] = Field(default=None, ge=0)

    # --- Trạng thái và thời gian ------------------------------------------
    status: Status = Field(default=Status.PENDING)
    created_at: datetime = Field(default_factory=utc_now)

    # --- Luật liên trường -------------------------------------------------
    @model_validator(mode="after")
    def _audio_xong_phai_co_file_hop_le(self) -> "AudioFile":
        """status = done thì bắt buộc có file_path và file không rỗng.

        Project tham khảo từng sinh ra file mp3 0 byte nhưng vẫn coi là thành công,
        luật này chặn lỗi đó ngay từ model.
        """
        if self.status == Status.DONE:
            if not self.file_path:
                raise ValueError("status = done thì file_path là bắt buộc")
            if not self.size_bytes:
                raise ValueError("status = done thì size_bytes phải > 0 (file không được rỗng)")
        return self
