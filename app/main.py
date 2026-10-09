"""
Điểm khởi động ứng dụng.

Kiến trúc 3 lớp (luồng gọi MỘT CHIỀU, không được đi ngược hay nhảy cóc):

    [Lớp 1 - Presentation]  app/api/          nhận HTTP request, validate, trả JSON
              │
              ▼
    [Lớp 2 - Business]      app/services/     quy tắc nghiệp vụ
              │
              ▼
    [Lớp 3 - Data Access]   app/repositories/ (MongoDB) + app/integrations/ (dịch máy, TTS, LLM, thanh toán)

Chạy:  uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.v1.endpoints import media, mock_gateway
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.db.indexes import ensure_indexes
from app.db.mongo import check_connection, create_client, ping
from app.db.seed import backfill_sample_details, seed_languages, seed_sample_content
from app.integrations.llm import build_llm
from app.integrations.media_storage import build_media_storage
from app.integrations.payment_gateway import MockPaymentGateway
from app.integrations.translator import build_translator
from app.integrations.tts import build_tts
from app.repositories.repositories import AdminUserRepository
from app.services.auth_service import AuthService
from app.services.task_runner import BackgroundTaskRunner

logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


async def init_state(app: FastAPI, settings: Settings, *, db=None, overrides: dict | None = None) -> None:
    """Khởi tạo các thành phần dùng chung, gắn vào app.state để deps.py lấy ra."""
    if db is None:
        app.state.mongo_client = create_client(settings.MONGO_URI)
        db = app.state.mongo_client[settings.MONGO_DB_NAME]
        await check_connection(db, settings.MONGO_URI)
    app.state.db = db
    app.state.settings = settings
    app.state.translator = build_translator(settings.TRANSLATOR_PROVIDER, mymemory_email=settings.MYMEMORY_EMAIL)
    app.state.tts = build_tts(settings.TTS_PROVIDER)
    app.state.storage = build_media_storage(settings, db)
    app.state.llm = build_llm(settings)
    # Cổng giả lập chạy cùng server -> dùng URL tương đối, deploy ở domain nào cũng đúng
    app.state.payment_gateway = MockPaymentGateway("", settings.PAYMENT_WEBHOOK_SECRET)
    app.state.task_runner = BackgroundTaskRunner(settings.MAX_CONCURRENT_LOCALIZATION)
    for key, value in (overrides or {}).items():
        setattr(app.state, key, value)


async def bootstrap_data(app: FastAPI, settings: Settings) -> None:
    db = app.state.db
    await ensure_indexes(db)
    await seed_languages(db)
    auth = AuthService(user_repo=AdminUserRepository(db), settings=settings)
    await auth.ensure_first_admin(settings.FIRST_ADMIN_USERNAME, settings.FIRST_ADMIN_PASSWORD)
    from app.api.deps import get_localization_service, get_repos  # tránh import vòng

    localization = get_localization_service(get_repos(db), app.state, settings)
    # Server từng bị tắt khi đang dịch -> chạy tiếp các bản dịch còn dở
    await localization.recover_unfinished()
    if settings.SEED_SAMPLE_DATA:
        inserted = await seed_sample_content(db)
        await backfill_sample_details(db)
        if inserted and settings.AUTO_LOCALIZE_ON_STARTUP:
            await localization.schedule_all()


def create_app(settings: Settings | None = None, *, init: bool = True) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if init:
            settings.validate_for_production()
            await init_state(app, settings)
            await bootstrap_data(app, settings)
            logger.info("%s v%s đã sẵn sàng (%s)", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
        yield
        if init:
            await app.state.task_runner.shutdown()
            client = getattr(app.state, "mongo_client", None)
            if client is not None:
                client.close()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Backend 3 lớp cho hệ thống **Thuyết minh tự động đa ngôn ngữ** - Chùa Linh Ứng.\n\n"
            "- API du khách cần `Authorization: Bearer <access_token>` (lấy qua `/access/token`).\n"
            "- API admin cần token từ `/admin/auth/login`.\n"
            "- Mọi phản hồi theo định dạng `{success, data, message}` hoặc `{success:false, error}`."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag", "X-Translation-Pending"],
    )
    register_exception_handlers(app)

    @app.get("/health", tags=["Health"], summary="Liveness: server còn sống")
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.get("/health/ready", tags=["Health"], summary="Readiness: kết nối DB OK")
    async def ready():
        db_ok = await ping(app.state.db)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"status": "ready" if db_ok else "not_ready", "database": db_ok}, status_code=200 if db_ok else 503
        )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    if settings.PAYMENT_PROVIDER == "mock":
        app.include_router(mock_gateway.router)

    if settings.MEDIA_STORAGE == "local":
        Path(settings.MEDIA_DIR).mkdir(parents=True, exist_ok=True)
        app.mount(settings.MEDIA_URL_PREFIX, StaticFiles(directory=settings.MEDIA_DIR), name="media")
    else:  # audio lưu trong MongoDB
        app.include_router(media.router, prefix=settings.MEDIA_URL_PREFIX)
    if FRONTEND_DIR.exists():
        # Mount cuối cùng để không "nuốt" các route API phía trên
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()
