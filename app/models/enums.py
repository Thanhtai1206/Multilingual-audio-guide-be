"""Các giá trị cố định dùng chung cho nhiều model (chốt chung cả nhóm).

Dùng Enum thay cho chuỗi tự do để tránh gõ sai ("done" / "Done" / "finished").
`str, Enum` giúp giá trị lưu vào MongoDB và trả ra JSON vẫn là chuỗi thường.
"""
from enum import Enum


class Role(str, Enum):
    """Vai trò của USER."""
    ADMIN = "admin"
    EDITOR = "editor"


class Status(str, Enum):
    """Trạng thái xử lý, dùng cho TRANSLATION, AUDIO_FILE và PROCESSING_JOB."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TranslationOrigin(str, Enum):
    """Bản dịch do máy sinh ra hay do người sửa tay."""
    AUTO = "auto"
    MANUAL = "manual"


class JobType(str, Enum):
    """Loại công việc của PROCESSING_JOB."""
    TRANSLATE = "translate"
    TTS = "tts"
