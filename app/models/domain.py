"""
Mô hình miền (domain models) - dữ liệu "thật" của hệ thống.

- Lớp Repository đọc document MongoDB rồi chuyển thành các model này.
- Lớp Service làm việc với các model này.
- Lớp API KHÔNG trả thẳng model ra ngoài mà chuyển sang schema riêng (app/api/schemas)
  để có thể giấu trường nhạy cảm (vd: password_hash) và giữ hợp đồng API ổn định.

Mỗi class tương ứng 1 collection trong ERD (xem docs/02-erd.md).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------- Enum ----------


class LocalizationStatus(StrEnum):
    PENDING = "pending"  # đã xếp hàng, chưa xử lý
    PROCESSING = "processing"  # đang dịch / tạo audio
    READY = "ready"  # có bản dịch (audio có thể có hoặc không)
    FAILED = "failed"  # dịch lỗi
    OUTDATED = "outdated"  # nội dung gốc đã đổi, bản dịch cũ không còn đúng


class TranslatedBy(StrEnum):
    SOURCE = "source"  # chính là nội dung gốc tiếng Việt
    MACHINE = "machine"  # dịch máy
    MANUAL = "manual"  # admin sửa tay


class AdminRole(StrEnum):
    ADMIN = "admin"  # toàn quyền
    STAFF = "staff"  # nhân viên quầy vé: tạo mã truy cập, xem POI


class AccessMethod(StrEnum):
    CASH = "cash"
    ONLINE = "online"


class AccessStatus(StrEnum):
    PENDING = "pending"  # chờ thanh toán online
    PAID = "paid"  # đã thanh toán, chưa kích hoạt
    ACTIVE = "active"  # du khách đã đổi mã lấy token
    EXPIRED = "expired"
    CANCELLED = "cancelled"  # thanh toán thất bại / admin thu hồi


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class EventType(StrEnum):
    VIEW = "view"  # mở chi tiết POI
    AUDIO_PLAY = "audio_play"  # nghe audio
    GEOFENCE_ENTER = "geofence_enter"  # GPS phát hiện vào vùng POI


# ---------- Entity ----------


class Language(DomainModel):
    id: str
    code: str  # mã ISO dùng trong API, vd "vi", "en", "zh"
    name: str  # tên tiếng Anh, vd "Vietnamese"
    native_name: str  # tên bản địa, vd "Tiếng Việt"
    translator_code: str  # mã cho dịch máy (Google dùng "zh-CN" cho tiếng Trung)
    tts_voice: str  # giọng đọc Edge-TTS
    is_active: bool = True
    sort_order: int = 0


class OpeningPeriod(DomainModel):
    """1 khung giờ mở cửa trong 1 ngày. Một ngày có thể có nhiều khung (vd nghỉ trưa)."""

    day: int  # 0 = Thứ Hai ... 6 = Chủ nhật (giống datetime.weekday())
    open: str  # "HH:MM"
    close: str  # "HH:MM", "24:00" = tới nửa đêm


class Poi(DomainModel):
    """Điểm tham quan (Point of Interest). Nội dung gốc luôn là tiếng Việt."""

    id: str
    code: str
    name: str
    description: str
    category: str = "landmark"
    latitude: float
    longitude: float
    trigger_radius_m: int = 30  # bán kính geofence: vào vùng này app tự phát audio
    priority: int = 0  # ưu tiên khi nhiều vùng chồng nhau (số lớn = ưu tiên hơn)
    thumbnail_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    sort_order: int = 0
    is_active: bool = True
    # --- Thông tin chi tiết (giống thẻ địa điểm trên Google Maps) ---
    opening_hours: list[OpeningPeriod] = Field(default_factory=list)  # rỗng = chưa có thông tin
    entry_fee_vnd: int = 0  # 0 = miễn phí
    visit_minutes: int | None = None  # thời gian tham quan gợi ý
    amenities: list[str] = Field(default_factory=list)  # mã tiện ích, xem app/services/poi_details.py
    tips: str = ""  # lưu ý / mẹo cho du khách (tiếng Việt, được dịch như mô tả)
    created_at: datetime
    updated_at: datetime


class PoiLocalization(DomainModel):
    """Bản dịch + audio của 1 POI cho 1 ngôn ngữ. Khóa duy nhất: (poi_id, lang)."""

    id: str
    poi_id: str
    lang: str
    name: str | None = None
    description: str | None = None
    audio_url: str | None = None
    status: LocalizationStatus = LocalizationStatus.PENDING
    translated_by: TranslatedBy = TranslatedBy.MACHINE
    source_hash: str | None = None  # hash nội dung gốc tại thời điểm dịch
    tips: str | None = None  # bản dịch phần "lưu ý"
    tips_hash: str | None = None  # hash phần lưu ý gốc lúc dịch (đổi lưu ý không bắt dịch lại cả mô tả)
    error: str | None = None
    updated_at: datetime


class TourTranslation(DomainModel):
    name: str
    description: str | None = None


class Tour(DomainModel):
    """Lộ trình gợi ý gồm nhiều POI theo thứ tự."""

    id: str
    code: str
    name: str
    description: str | None = None
    poi_ids: list[str] = Field(default_factory=list)
    estimated_minutes: int = 30
    translations: dict[str, TourTranslation] = Field(default_factory=dict)
    translation_requested_at: dict[str, datetime] = Field(default_factory=dict)  # lang -> lúc yêu cầu dịch
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class AdminUser(DomainModel):
    id: str
    username: str
    password_hash: str
    full_name: str
    role: AdminRole = AdminRole.STAFF
    is_active: bool = True
    created_at: datetime
    last_login_at: datetime | None = None


class AccessSession(DomainModel):
    """Một lượt mua quyền truy cập. `code` là mã ngắn khách nhập vào app."""

    id: str
    code: str
    method: AccessMethod
    status: AccessStatus
    amount: int
    currency: str = "VND"
    created_by: str | None = None  # id nhân viên (thanh toán tiền mặt)
    note: str | None = None
    created_at: datetime
    code_expires_at: datetime  # hạn để đổi mã
    paid_at: datetime | None = None
    activated_at: datetime | None = None
    access_expires_at: datetime | None = None  # hạn sử dụng app sau khi kích hoạt


class Payment(DomainModel):
    id: str
    session_id: str
    provider: str
    amount: int
    currency: str = "VND"
    status: PaymentStatus = PaymentStatus.PENDING
    provider_ref: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class KnowledgeArticle(DomainModel):
    """Bài viết kiến thức (FAQ, quy định...) làm nguồn cho chatbot RAG."""

    id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ChatLog(DomainModel):
    id: str
    session_id: str | None = None
    lang: str
    question: str
    answer: str
    source_ids: list[str] = Field(default_factory=list)
    used_llm: bool = False
    created_at: datetime


class VisitEvent(DomainModel):
    id: str
    session_id: str | None = None
    poi_id: str
    lang: str
    type: EventType
    created_at: datetime
