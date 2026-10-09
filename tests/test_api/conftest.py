"""
Test lớp API bằng cách THAY Service thật bằng Service giả (mock).

app.dependency_overrides[get_xxx_service] = lambda: mock
-> router gọi vào mock, không đụng tới database. Ta chỉ kiểm tra:
   validate input, mã HTTP, định dạng response, phân quyền, cách gọi Service.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import create_app
from app.models.domain import AdminRole, AdminUser

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def make_admin(role: AdminRole = AdminRole.ADMIN) -> AdminUser:
    return AdminUser(
        id="u1", username="admin", password_hash="x", full_name="Admin", role=role, is_active=True, created_at=NOW
    )


def async_mock_service(*method_names: str) -> MagicMock:
    service = MagicMock()
    for name in method_names:
        setattr(service, name, AsyncMock())
    return service


@pytest.fixture
def app(settings):
    application = create_app(settings, init=False)
    application.dependency_overrides[deps.get_settings_dep] = lambda: settings
    # Hạ tầng giả: Service nào không bị override vẫn khởi tạo được nhưng không chạm DB thật
    for name in ("db", "translator", "tts", "storage", "llm", "payment_gateway", "chat_cache"):
        setattr(application.state, name, MagicMock())
    application.state.task_runner = MagicMock(pending_count=0)
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def as_visitor(app):
    """Giả lập du khách đã có quyền truy cập."""
    app.dependency_overrides[deps.get_visitor] = lambda: deps.VisitorContext(session_id="sess1", status="active")


@pytest.fixture
def as_admin(app):
    user = make_admin(AdminRole.ADMIN)
    app.dependency_overrides[deps.get_current_admin] = lambda: user
    return user


@pytest.fixture
def as_staff(app):
    user = make_admin(AdminRole.STAFF)
    app.dependency_overrides[deps.get_current_admin] = lambda: user
    return user


def override(app, dependency, mock):
    app.dependency_overrides[dependency] = lambda: mock
    return mock
