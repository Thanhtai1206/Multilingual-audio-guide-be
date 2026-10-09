"""
DEPENDENCY INJECTION - "lắp ráp" 3 lớp với nhau.

Mỗi request, FastAPI gọi các hàm get_xxx dưới đây để tạo:
    Database -> Repository -> Service
rồi đưa Service vào endpoint qua Depends(...).

Lợi ích lớn nhất: khi test lớp API, ta thay (override) get_poi_service bằng
một Service giả -> test router mà không cần database. Xem tests/test_api.
"""

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.models.domain import AdminRole, AdminUser
from app.repositories.repositories import (
    AccessSessionRepository,
    AdminUserRepository,
    ChatCacheRepository,
    ChatLogRepository,
    KnowledgeRepository,
    LanguageRepository,
    PaymentRepository,
    PoiLocalizationRepository,
    PoiRepository,
    TourRepository,
    UiTranslationRepository,
    VisitEventRepository,
)
from app.services.access_service import AccessService
from app.services.ai_assistant_service import AiAssistantService
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.content_service import ContentService
from app.services.knowledge_service import KnowledgeService
from app.services.language_service import LanguageService
from app.services.localization_service import LocalizationService
from app.services.media_service import MediaService
from app.services.payment_service import PaymentService
from app.services.poi_insights_service import PoiInsightsService
from app.services.poi_service import PoiService
from app.services.stats_service import StatsService
from app.services.tour_service import TourService
from app.services.ui_text_service import UiTextService

bearer_scheme = HTTPBearer(auto_error=False, description="JWT: token du khách hoặc token admin")


# ------------------------------------------------------------------ hạ tầng
def get_settings_dep() -> Settings:
    return get_settings()


def get_db(request: Request):
    return request.app.state.db


def get_state(request: Request):
    return request.app.state


# ------------------------------------------------------------------ lớp 3: repositories
def get_repos(db=Depends(get_db)) -> dict:
    return {
        "language": LanguageRepository(db),
        "poi": PoiRepository(db),
        "localization": PoiLocalizationRepository(db),
        "tour": TourRepository(db),
        "user": AdminUserRepository(db),
        "session": AccessSessionRepository(db),
        "payment": PaymentRepository(db),
        "knowledge": KnowledgeRepository(db),
        "chat": ChatLogRepository(db),
        "event": VisitEventRepository(db),
        "ui": UiTranslationRepository(db),
        "chat_cache": ChatCacheRepository(db),
    }


# ------------------------------------------------------------------ lớp 2: services
def get_language_service(repos=Depends(get_repos), settings=Depends(get_settings_dep)) -> LanguageService:
    return LanguageService(
        repos["language"], source_lang=settings.SOURCE_LANGUAGE, fallback_lang=settings.FALLBACK_LANGUAGE
    )


def get_localization_service(
    repos=Depends(get_repos), state=Depends(get_state), settings=Depends(get_settings_dep)
) -> LocalizationService:
    return LocalizationService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        language_repo=repos["language"],
        tour_repo=repos["tour"],
        translator=state.translator,
        tts=state.tts,
        storage=state.storage,
        task_runner=state.task_runner,
        source_lang=settings.SOURCE_LANGUAGE,
    )


def get_content_service(repos=Depends(get_repos), language_service=Depends(get_language_service)) -> ContentService:
    return ContentService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        tour_repo=repos["tour"],
        language_service=language_service,
    )


def get_poi_insights_service(repos=Depends(get_repos), settings=Depends(get_settings_dep)) -> PoiInsightsService:
    return PoiInsightsService(
        poi_repo=repos["poi"], event_repo=repos["event"], utc_offset_hours=settings.SITE_UTC_OFFSET_HOURS
    )


def get_poi_service(repos=Depends(get_repos), localization_service=Depends(get_localization_service)) -> PoiService:
    return PoiService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        tour_repo=repos["tour"],
        localization_service=localization_service,
    )


def get_tour_service(
    repos=Depends(get_repos),
    content_service=Depends(get_content_service),
    localization_service=Depends(get_localization_service),
) -> TourService:
    return TourService(
        tour_repo=repos["tour"],
        poi_repo=repos["poi"],
        content_service=content_service,
        localization_service=localization_service,
    )


def get_access_service(repos=Depends(get_repos), settings=Depends(get_settings_dep)) -> AccessService:
    return AccessService(session_repo=repos["session"], settings=settings)


def get_payment_service(
    repos=Depends(get_repos), state=Depends(get_state), access_service=Depends(get_access_service)
) -> PaymentService:
    return PaymentService(
        payment_repo=repos["payment"],
        session_repo=repos["session"],
        access_service=access_service,
        gateway=state.payment_gateway,
    )


def get_auth_service(repos=Depends(get_repos), settings=Depends(get_settings_dep)) -> AuthService:
    return AuthService(user_repo=repos["user"], settings=settings)


def get_chat_service(
    repos=Depends(get_repos),
    state=Depends(get_state),
    settings=Depends(get_settings_dep),
    language_service=Depends(get_language_service),
) -> ChatService:
    return ChatService(
        poi_repo=repos["poi"],
        knowledge_repo=repos["knowledge"],
        chat_repo=repos["chat"],
        language_service=language_service,
        translator=state.translator,
        llm=state.llm,
        cache_repo=repos["chat_cache"],
        daily_limit=settings.CHAT_DAILY_LIMIT,
        cache_ttl_seconds=settings.CHAT_CACHE_TTL_SECONDS,
        history_turns=settings.CHAT_HISTORY_TURNS,
        utc_offset_hours=settings.SITE_UTC_OFFSET_HOURS,
    )


def get_knowledge_service(repos=Depends(get_repos)) -> KnowledgeService:
    return KnowledgeService(knowledge_repo=repos["knowledge"])


def get_stats_service(repos=Depends(get_repos)) -> StatsService:
    return StatsService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        language_repo=repos["language"],
        session_repo=repos["session"],
        chat_repo=repos["chat"],
        event_repo=repos["event"],
    )


def get_ui_text_service(repos=Depends(get_repos), state=Depends(get_state)) -> UiTextService:
    return UiTextService(ui_repo=repos["ui"], language_repo=repos["language"], translator=state.translator)


def get_media_service(state=Depends(get_state)) -> MediaService:
    return MediaService(storage=state.storage)


def get_ai_assistant_service(state=Depends(get_state)) -> AiAssistantService:
    return AiAssistantService(llm=state.llm)


# ------------------------------------------------------------------ xác thực & phân quyền
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> AdminUser:
    if credentials is None:
        raise UnauthorizedError("Vui lòng đăng nhập", code="NOT_AUTHENTICATED")
    return await auth_service.get_user_from_token(credentials.credentials)


async def require_admin_role(user: AdminUser = Depends(get_current_admin)) -> AdminUser:
    """Chỉ role 'admin' (nhân viên 'staff' bị chặn)."""
    if user.role != AdminRole.ADMIN:
        raise ForbiddenError("Chức năng này chỉ dành cho quản trị viên", code="ADMIN_ONLY")
    return user


@dataclass
class VisitorContext:
    session_id: str | None
    status: str | None = None
    access_expires_at: object = None
    is_admin_preview: bool = False


async def get_visitor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    access_service: AccessService = Depends(get_access_service),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings_dep),
) -> VisitorContext:
    """
    Cổng kiểm soát truy cập cho API du khách (PRD: "Verify access_token -> allow or deny").
    - Token du khách hợp lệ -> cho qua.
    - Token admin -> cho qua để admin xem thử app.
    - Không có token: nếu ACCESS_REQUIRED=false (demo) thì cho qua ẩn danh, ngược lại chặn.
    """
    if credentials is None:
        if settings.ACCESS_REQUIRED:
            raise UnauthorizedError("Bạn cần mua quyền truy cập để sử dụng", code="ACCESS_REQUIRED")
        return VisitorContext(session_id=None)
    token = credentials.credentials
    try:
        session = await access_service.verify_token(token)
        return VisitorContext(session_id=session.id, status=session.status, access_expires_at=session.access_expires_at)
    except UnauthorizedError as visitor_error:
        try:
            await auth_service.get_user_from_token(token)
        except UnauthorizedError:
            raise visitor_error from None
        return VisitorContext(session_id=None, is_admin_preview=True)
