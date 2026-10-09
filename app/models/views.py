"""
Các "view model" do lớp Service tạo ra (kết quả đã xử lý nghiệp vụ),
khác với domain model là dữ liệu thô lưu trong DB.
Ví dụ: LocalizedPoi = POI đã được chọn đúng ngôn ngữ theo chuỗi fallback.
"""

from pydantic import BaseModel, Field


class LocalizedPoi(BaseModel):
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
    image_urls: list[str] = Field(default_factory=list)
    audio_url: str | None = None
    requested_lang: str
    served_lang: str  # ngôn ngữ thực sự trả về
    is_fallback: bool  # True nếu không có bản dịch đúng ngôn ngữ yêu cầu
    distance_m: float | None = None
    # Thông tin chi tiết (giống Google Maps); nhãn tiện ích/ngày do giao diện dịch theo mã
    opening_hours: list[dict] = Field(default_factory=list)  # [{day, open, close}]
    entry_fee_vnd: int = 0
    visit_minutes: int | None = None
    amenities: list[str] = Field(default_factory=list)
    tips: str = ""
    tips_lang: str | None = None  # ngôn ngữ thực sự của phần lưu ý (có thể là bản dự phòng)


class PoiInsights(BaseModel):
    """Thông tin "sống" của 1 POI, tính theo thời điểm hiện tại - không nằm trong bundle vì đổi theo giờ."""

    poi_id: str
    now_local: str  # giờ hiện tại ở chùa, ISO 8601
    today: int  # 0 = Thứ Hai ... 6 = Chủ nhật
    open_status: dict  # xem poi_details.opening_status
    popular_times: dict  # {sample_size, by_day: {0..6: [24 số 0-100]} | None}
    busy_now: int | None = None  # mức đông giờ này (0-100), None nếu chưa đủ dữ liệu


class LocalizedTour(BaseModel):
    id: str
    code: str
    name: str
    description: str | None = None
    poi_ids: list[str]
    estimated_minutes: int
    served_lang: str


class ContentBundle(BaseModel):
    lang: str
    version: str
    languages: list[dict]
    pois: list[LocalizedPoi]
    tours: list[LocalizedTour]


class RouteStop(BaseModel):
    order: int
    poi: LocalizedPoi
    walk_distance_m: float  # quãng đường đi bộ từ điểm trước tới điểm này
    walk_minutes: float
    listen_minutes: float  # thời gian nghe thuyết minh ước tính


class RecommendedRoute(BaseModel):
    start_latitude: float
    start_longitude: float
    stops: list[RouteStop]
    total_distance_m: float
    total_minutes: float


class LocalizationOverview(BaseModel):
    lang: str
    language_name: str
    status: str  # pending | processing | ready | failed | outdated | missing
    is_fresh: bool  # bản dịch khớp nội dung gốc hiện tại
    translated_by: str | None = None
    has_audio: bool = False
    audio_url: str | None = None
    name: str | None = None
    description: str | None = None
    error: str | None = None


class ChatSource(BaseModel):
    id: str
    type: str  # poi | article
    title: str


class ChatAnswer(BaseModel):
    answer: str
    lang: str
    sources: list[ChatSource]
    used_llm: bool
    cached: bool = False


class StatsOverview(BaseModel):
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
