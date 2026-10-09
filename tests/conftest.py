"""
Fixture dùng chung cho test.

Mặc định dùng MongoDB giả lập (mongomock) -> chạy ở đâu cũng được.
Nếu đặt biến môi trường TEST_MONGO_URI (CI job "integration" làm vậy)
thì test repository chạy trên MongoDB THẬT.
"""

import os
import uuid

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.core.config import Settings
from app.db.indexes import ensure_indexes
from app.db.seed import seed_languages
from app.integrations.media_storage import LocalMediaStorage
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
    VisitEventRepository,
)
from app.services.task_runner import InlineTaskRunner
from tests.fakes import FakeTranslator, FakeTTS


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        MONGO_URI="mongomock://test",
        JWT_SECRET="test-secret-key-that-is-long-enough-123",
        TRANSLATOR_PROVIDER="none",
        TTS_PROVIDER="none",
        LLM_PROVIDER="none",
        MEDIA_DIR=str(tmp_path / "media"),
        SEED_SAMPLE_DATA=False,
        CHAT_DAILY_LIMIT=5,
    )


@pytest.fixture
async def db():
    real_uri = os.getenv("TEST_MONGO_URI")
    if real_uri:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(real_uri, tz_aware=True)
        name = f"test_{uuid.uuid4().hex[:8]}"
        database = client[name]
        await ensure_indexes(database)
        yield database
        await client.drop_database(name)
        client.close()
    else:
        database = AsyncMongoMockClient(tz_aware=True)[f"test_{uuid.uuid4().hex[:8]}"]
        await ensure_indexes(database)
        yield database


@pytest.fixture
async def seeded_db(db):
    await seed_languages(db)
    return db


@pytest.fixture
def repos(db) -> dict:
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
        "chat_cache": ChatCacheRepository(db),
    }


@pytest.fixture
def translator():
    return FakeTranslator()


@pytest.fixture
def tts():
    return FakeTTS()


@pytest.fixture
def storage(tmp_path):
    return LocalMediaStorage(str(tmp_path / "media"), "/media")


@pytest.fixture
def task_runner():
    return InlineTaskRunner()


def poi_data(code: str = "TEST_POI", **overrides) -> dict:
    data = {
        "code": code,
        "name": "Tượng Phật Bà Quan Thế Âm",
        "description": "Tượng cao khoảng 67 mét, hướng ra biển. Người dân tin Ngài che chở ngư dân.",
        "category": "statue",
        "latitude": 16.1003,
        "longitude": 108.2779,
        "trigger_radius_m": 30,
        "priority": 5,
        "image_urls": [],
        "sort_order": 0,
        "is_active": True,
    }
    data.update(overrides)
    return data
