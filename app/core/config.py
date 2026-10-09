"""
Cấu hình ứng dụng.

Mọi giá trị đều đọc từ biến môi trường (hoặc file .env) nhờ pydantic-settings.
Nhờ vậy cùng một mã nguồn chạy được ở máy dev, trong CI và trên server
chỉ bằng cách đổi biến môi trường - không phải sửa code.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Thông tin chung ---
    APP_NAME: str = "Linh Ung Multilingual Audio Guide API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"  # development | test | production
    API_V1_PREFIX: str = "/api/v1"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: list[str] = ["*"]
    LOG_LEVEL: str = "INFO"

    # --- Cơ sở dữ liệu ---
    # MongoDB thật: "mongodb://localhost:27017" (cài trên máy / Docker) hoặc "mongodb+srv://..." (Atlas).
    # "mongomock://..." chỉ dành cho bộ test tự động.
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "audio_guide"

    # --- Bảo mật / token ---
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ADMIN_TOKEN_MINUTES: int = 480
    VISITOR_TOKEN_HOURS: int = 24

    # --- Quyền truy cập của du khách (thanh toán) ---
    ACCESS_REQUIRED: bool = True  # False = mở tự do, tiện khi demo/dev
    ACCESS_PRICE_VND: int = 50000
    ACCESS_CODE_TTL_HOURS: int = 24  # mã chưa dùng sẽ hết hạn sau ngần này giờ
    PAYMENT_PROVIDER: str = "mock"  # hiện chỉ có cổng giả lập (thay cho Payoo)
    PAYMENT_WEBHOOK_SECRET: str = "mock-webhook-secret"

    # --- Dịch máy, TTS, LLM ---
    TRANSLATOR_PROVIDER: str = "google"  # google (Google -> Google API -> MyMemory) | mymemory | none
    MYMEMORY_EMAIL: str | None = None  # khai báo email -> MyMemory cho ~50.000 ký tự/ngày thay vì 5.000
    TTS_PROVIDER: str = "edge"  # edge | none
    # AI tạo sinh cho chatbot: auto (tự nhận theo dạng key) | gemini | groq | openrouter | none
    LLM_PROVIDER: str = "auto"
    LLM_API_KEY: str | None = None  # vd key Gemini miễn phí: https://aistudio.google.com/apikey
    LLM_MODEL: str | None = None  # bỏ trống = model mặc định của nhà cung cấp
    LLM_BASE_URL: str | None = None  # chỉ cần khi dùng dịch vụ tương thích OpenAI khác
    LLM_TIMEOUT_SECONDS: float = 60.0  # thời gian tối đa chờ AI trả lời 1 câu
    CHAT_HISTORY_TURNS: int = 4  # số lượt hỏi-đáp trước đó gửi kèm để AI hiểu câu hỏi nối tiếp
    OPENROUTER_API_KEY: str | None = None  # (cách cấu hình cũ, vẫn dùng được)
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    EXTERNAL_TIMEOUT_SECONDS: float = 30.0

    # --- Đa ngôn ngữ ---
    SOURCE_LANGUAGE: str = "vi"  # ngôn ngữ gốc admin nhập nội dung
    FALLBACK_LANGUAGE: str = "en"  # ngôn ngữ dự phòng chung cho khách quốc tế
    MAX_CONCURRENT_LOCALIZATION: int = 3

    # --- Địa điểm ---
    SITE_UTC_OFFSET_HOURS: int = 7  # múi giờ của chùa (Việt Nam UTC+7, không đổi giờ mùa hè)

    # --- Chatbot ---
    CHAT_DAILY_LIMIT: int = 50
    CHAT_CACHE_TTL_SECONDS: int = 600  # cache câu trả lời lưu trong MongoDB, tự xóa khi hết hạn

    # --- File media (audio, ảnh) ---
    # mongo = lưu file audio ngay trong MongoDB (bền vững, deploy đâu cũng còn) | local = thư mục MEDIA_DIR
    MEDIA_STORAGE: str = "mongo"
    MEDIA_DIR: str = "media"
    MEDIA_URL_PREFIX: str = "/media"

    # --- Khởi tạo dữ liệu ---
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_PASSWORD: str = "admin123"
    SEED_SAMPLE_DATA: bool = True
    AUTO_LOCALIZE_ON_STARTUP: bool = False

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def llm_enabled(self) -> bool:
        if self.LLM_PROVIDER == "none":
            return False
        return bool(self.LLM_API_KEY or self.OPENROUTER_API_KEY)

    def validate_for_production(self) -> None:
        """Chặn khởi động nếu cấu hình nguy hiểm khi chạy production (fail-fast)."""
        if not self.is_production:
            return
        problems = []
        if self.JWT_SECRET == DEFAULT_JWT_SECRET or len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET phải được đặt và dài tối thiểu 32 ký tự")
        if self.FIRST_ADMIN_PASSWORD == "admin123":
            problems.append("FIRST_ADMIN_PASSWORD không được dùng mật khẩu mặc định")
        if self.PAYMENT_WEBHOOK_SECRET == "mock-webhook-secret":
            problems.append("PAYMENT_WEBHOOK_SECRET phải được đổi")
        if self.MONGO_URI.startswith("mongomock://"):
            problems.append("MONGO_URI phải trỏ tới MongoDB thật (mongomock mất dữ liệu khi khởi động lại)")
        if problems:
            raise RuntimeError("Cấu hình production không hợp lệ: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
