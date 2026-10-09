"""Schema (DTO) cho các API quản trị."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.domain import AdminRole

CODE_PATTERN = r"^[A-Za-z0-9_\-]{2,50}$"


# ---------- Auth & User ----------
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["admin"])
    password: str = Field(..., min_length=6, max_length=100, examples=["admin123"])


class AdminUserOut(BaseModel):
    """Không bao giờ trả password_hash ra ngoài."""

    id: str
    username: str
    full_name: str
    role: AdminRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AdminUserOut


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.]+$")
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=100)
    role: AdminRole = AdminRole.STAFF


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=100)
    role: AdminRole | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=100)


# ---------- POI ----------
class OpeningPeriodIn(BaseModel):
    """1 khung giờ mở cửa. Mở xuyên đêm (vd 22:00 - 02:00) thì tách thành 2 khung ở 2 ngày."""

    day: int = Field(..., ge=0, le=6, description="0 = Thứ Hai ... 6 = Chủ nhật")
    open: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["06:00"])
    close: str = Field(..., pattern=r"^(([01]\d|2[0-3]):[0-5]\d|24:00)$", examples=["21:00"])

    @model_validator(mode="after")
    def close_after_open(self):
        if self.close <= self.open:  # "HH:MM" cùng độ dài -> so sánh chuỗi = so sánh giờ
            raise ValueError("Giờ đóng cửa phải sau giờ mở cửa")
        return self


class PoiDetailsIn(BaseModel):
    opening_hours: list[OpeningPeriodIn] = Field(default_factory=list, max_length=50)
    entry_fee_vnd: int = Field(0, ge=0, le=10_000_000, description="0 = miễn phí")
    visit_minutes: int | None = Field(None, ge=1, le=600, description="Thời gian tham quan gợi ý (phút)")
    amenities: list[str] = Field(default_factory=list, max_length=20, examples=[["parking", "restroom"]])
    tips: str = Field("", max_length=2000, description="Lưu ý cho du khách (tiếng Việt, tự dịch)")


class PoiBase(PoiDetailsIn):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=10000)
    category: str = Field("landmark", max_length=50)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    trigger_radius_m: int = Field(30, ge=5, le=500)
    priority: int = Field(0, ge=0, le=100)
    thumbnail_url: str | None = None
    image_urls: list[str] = Field(default_factory=list, max_length=8)
    sort_order: int = 0
    is_active: bool = True


class PoiCreate(PoiBase):
    code: str = Field(..., pattern=CODE_PATTERN, examples=["CONG_TAM_QUAN"])


class PoiUpdate(BaseModel):
    """Mọi trường đều tùy chọn - chỉ gửi trường muốn sửa."""

    code: str | None = Field(None, pattern=CODE_PATTERN)
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1, max_length=10000)
    category: str | None = Field(None, max_length=50)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    trigger_radius_m: int | None = Field(None, ge=5, le=500)
    priority: int | None = Field(None, ge=0, le=100)
    thumbnail_url: str | None = None
    image_urls: list[str] | None = Field(None, max_length=8)
    sort_order: int | None = None
    is_active: bool | None = None
    opening_hours: list[OpeningPeriodIn] | None = Field(None, max_length=50)
    entry_fee_vnd: int | None = Field(None, ge=0, le=10_000_000)
    visit_minutes: int | None = Field(None, ge=1, le=600)
    amenities: list[str] | None = Field(None, max_length=20)
    tips: str | None = Field(None, max_length=2000)


class PoiOut(PoiBase):
    id: str
    code: str
    created_at: datetime
    updated_at: datetime


class LocalizeRequest(BaseModel):
    languages: list[str] | None = Field(None, description="Bỏ trống = mọi ngôn ngữ đang bật")
    force: bool = Field(False, description="True = dịch lại kể cả bản đã có / bản sửa tay")


class LocalizeAllRequest(BaseModel):
    force: bool = False


class LocalizeQueuedOut(BaseModel):
    queued: int


class LocalizationOverviewOut(BaseModel):
    lang: str
    language_name: str
    status: str
    is_fresh: bool
    translated_by: str | None = None
    has_audio: bool
    audio_url: str | None = None
    name: str | None = None
    description: str | None = None
    error: str | None = None


class ManualLocalizationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=10000)
    regenerate_audio: bool = True


# ---------- Tour ----------
class TourCreate(BaseModel):
    code: str = Field(..., pattern=CODE_PATTERN)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    poi_ids: list[str] = Field(default_factory=list)
    estimated_minutes: int = Field(30, ge=1, le=600)
    is_active: bool = True


class TourUpdate(BaseModel):
    code: str | None = Field(None, pattern=CODE_PATTERN)
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    poi_ids: list[str] | None = None
    estimated_minutes: int | None = Field(None, ge=1, le=600)
    is_active: bool | None = None


class TourOut(BaseModel):
    id: str
    code: str
    name: str
    description: str | None
    poi_ids: list[str]
    estimated_minutes: int
    is_active: bool
    translated_languages: list[str]
    created_at: datetime
    updated_at: datetime


# ---------- Language ----------
class LanguageAdminOut(BaseModel):
    code: str
    name: str
    native_name: str
    translator_code: str
    tts_voice: str
    is_active: bool


class LanguageToggle(BaseModel):
    is_active: bool


# ---------- Access ----------
class CashCodeRequest(BaseModel):
    quantity: int = Field(1, ge=1, le=50)
    note: str | None = Field(None, max_length=200)


class AccessSessionOut(BaseModel):
    id: str
    code: str
    method: str
    status: str
    amount: int
    currency: str
    note: str | None = None
    created_at: datetime
    code_expires_at: datetime
    paid_at: datetime | None = None
    activated_at: datetime | None = None
    access_expires_at: datetime | None = None


# ---------- Knowledge ----------
class ArticleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


class ArticleUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1, max_length=10000)
    tags: list[str] | None = None
    is_active: bool | None = None


class ArticleOut(ArticleCreate):
    id: str
    created_at: datetime
    updated_at: datetime


# ---------- Stats / AI ----------
class StatsOut(BaseModel):
    total_pois: int
    active_pois: int
    active_languages: int
    localization_status: dict[str, int]
    localization_coverage_percent: float
    access_sessions: dict[str, int]
    revenue_vnd: int
    total_chats: int
    total_events: int
    top_pois: list[dict]
    events_by_lang: dict[str, int]
    background_tasks: int = 0


class ChatLogOut(BaseModel):
    id: str
    lang: str
    question: str
    answer: str
    used_llm: bool
    created_at: datetime


class EnhanceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)


class EnhanceOut(BaseModel):
    description: str
