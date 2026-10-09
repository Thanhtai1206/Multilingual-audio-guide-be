"""Schema (DTO) cho các API phía du khách."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.domain import EventType


class LanguageOut(BaseModel):
    code: str
    name: str
    native_name: str


class OpeningPeriodOut(BaseModel):
    day: int
    open: str
    close: str


class LocalizedPoiOut(BaseModel):
    id: str
    code: str
    name: str
    description: str
    category: str
    latitude: float
    longitude: float
    trigger_radius_m: int
    priority: int
    thumbnail_url: str | None = None
    image_urls: list[str] = []
    audio_url: str | None = None
    requested_lang: str
    served_lang: str
    is_fallback: bool
    distance_m: float | None = None
    opening_hours: list[OpeningPeriodOut] = []
    entry_fee_vnd: int = 0
    visit_minutes: int | None = None
    amenities: list[str] = []
    tips: str = ""
    tips_lang: str | None = None


class OpenStatusOut(BaseModel):
    state: str = Field(..., description="open | closing_soon | closed | opening_soon | unknown")
    closes_at: str | None = None
    minutes_left: int | None = None
    opens_at: str | None = None
    opens_day: int | None = None
    opens_in_days: int | None = None


class PopularTimesOut(BaseModel):
    sample_size: int
    by_day: dict[int, list[int]] | None = Field(None, description="0..6 -> 24 mức đông (0-100) theo giờ")


class PoiInsightsOut(BaseModel):
    poi_id: str
    now_local: str
    today: int
    open_status: OpenStatusOut
    popular_times: PopularTimesOut
    busy_now: int | None = None


class LocalizedTourOut(BaseModel):
    id: str
    code: str
    name: str
    description: str | None = None
    poi_ids: list[str]
    estimated_minutes: int
    served_lang: str


class ContentBundleOut(BaseModel):
    lang: str
    version: str
    languages: list[LanguageOut]
    pois: list[LocalizedPoiOut]
    tours: list[LocalizedTourOut]
    pending_translations: int = 0  # > 0: hệ thống đang dịch, app nên tải lại sau vài giây


class UiStringsOut(BaseModel):
    lang: str
    strings: dict[str, str]
    is_fallback: bool


class RecommendRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, examples=[16.1001])
    longitude: float = Field(..., ge=-180, le=180, examples=[108.2773])
    lang: str = Field("vi", examples=["en"])
    poi_ids: list[str] | None = Field(None, description="Các POI khách tự chọn (bỏ trống = hệ thống tự gợi ý)")
    tour_id: str | None = Field(None, description="Dùng POI của 1 lộ trình có sẵn")
    max_stops: int | None = Field(None, ge=1, le=30)


class RouteStopOut(BaseModel):
    order: int
    poi: LocalizedPoiOut
    walk_distance_m: float
    walk_minutes: float
    listen_minutes: float


class RecommendedRouteOut(BaseModel):
    start_latitude: float
    start_longitude: float
    stops: list[RouteStopOut]
    total_distance_m: float
    total_minutes: float


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500, examples=["Tượng Quan Âm cao bao nhiêu?"])
    lang: str = Field("vi", examples=["vi"])


class ChatSourceOut(BaseModel):
    id: str
    type: str
    title: str


class ChatAnswerOut(BaseModel):
    answer: str
    lang: str
    sources: list[ChatSourceOut]
    used_llm: bool
    cached: bool = False


class EventRequest(BaseModel):
    poi_id: str
    type: EventType
    lang: str = "vi"


# ---------- Quyền truy cập / thanh toán ----------


class AccessInfoOut(BaseModel):
    price_vnd: int
    access_hours: int
    methods: list[str]
    access_required: bool


class RedeemRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=12, examples=["AB3K9Q"])


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class OnlinePaymentOut(BaseModel):
    payment_id: str
    payment_url: str
    amount: int
    currency: str


class VisitorSessionOut(BaseModel):
    session_id: str | None
    status: str | None
    access_expires_at: datetime | None
    is_admin_preview: bool = False


class WebhookRequest(BaseModel):
    payment_id: str
    status: str = Field(..., pattern="^(success|failed)$")
    provider_ref: str | None = None
