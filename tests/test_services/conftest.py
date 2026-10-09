"""Lắp ráp các Service với repository (mongomock) + dịch vụ ngoài giả."""

import pytest

from app.services.access_service import AccessService
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.content_service import ContentService
from app.services.language_service import LanguageService
from app.services.localization_service import LocalizationService
from app.services.poi_service import PoiService
from app.services.stats_service import StatsService
from app.services.tour_service import TourService


@pytest.fixture
def services(seeded_db, repos, settings, translator, tts, storage, task_runner):
    language = LanguageService(repos["language"], source_lang="vi", fallback_lang="en")
    localization = LocalizationService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        language_repo=repos["language"],
        tour_repo=repos["tour"],
        translator=translator,
        tts=tts,
        storage=storage,
        task_runner=task_runner,
    )
    content = ContentService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        tour_repo=repos["tour"],
        language_service=language,
    )
    poi = PoiService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        tour_repo=repos["tour"],
        localization_service=localization,
    )
    tour = TourService(
        tour_repo=repos["tour"], poi_repo=repos["poi"], content_service=content, localization_service=localization
    )
    access = AccessService(session_repo=repos["session"], settings=settings)
    auth = AuthService(user_repo=repos["user"], settings=settings)
    chat = ChatService(
        poi_repo=repos["poi"],
        knowledge_repo=repos["knowledge"],
        chat_repo=repos["chat"],
        language_service=language,
        translator=translator,
        llm=None,
        cache_repo=repos["chat_cache"],
        daily_limit=settings.CHAT_DAILY_LIMIT,
    )
    stats = StatsService(
        poi_repo=repos["poi"],
        localization_repo=repos["localization"],
        language_repo=repos["language"],
        session_repo=repos["session"],
        chat_repo=repos["chat"],
        event_repo=repos["event"],
    )
    return {
        "language": language,
        "localization": localization,
        "content": content,
        "poi": poi,
        "tour": tour,
        "access": access,
        "auth": auth,
        "chat": chat,
        "stats": stats,
    }
