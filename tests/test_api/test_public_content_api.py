"""Test API phía du khách với Service giả."""

from datetime import UTC, datetime

from app.api import deps
from app.core.exceptions import NotFoundError, PaymentPendingError, RateLimitError, UnauthorizedError
from app.models.domain import AccessSession, Language
from app.models.views import ChatAnswer, LocalizedPoi, RecommendedRoute
from tests.test_api.conftest import async_mock_service, override

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def localized_poi(**kw) -> LocalizedPoi:
    data = dict(
        id="p1",
        code="A",
        name="Tên",
        description="Mô tả",
        category="statue",
        latitude=16.1,
        longitude=108.2,
        trigger_radius_m=30,
        priority=1,
        audio_url="/media/audio/a.mp3",
        requested_lang="en",
        served_lang="en",
        is_fallback=False,
    )
    data.update(kw)
    return LocalizedPoi(**data)


class TestEnvelopeAndErrors:
    def test_health(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_unknown_route_returns_error_envelope(self, client):
        body = client.get("/api/v1/khong-ton-tai").json()
        assert body["success"] is False and body["error"]["code"] == "NOT_FOUND"

    def test_openapi_docs_available(self, client):
        schema = client.get("/openapi.json").json()
        assert "/api/v1/content/bundle" in schema["paths"]


class TestLanguagesAndAccess:
    def test_list_languages(self, app, client):
        service = override(app, deps.get_language_service, async_mock_service("list_languages"))
        service.list_languages.return_value = [
            Language(
                id="1", code="vi", name="Vietnamese", native_name="Tiếng Việt", translator_code="vi", tts_voice="v"
            )
        ]
        body = client.get("/api/v1/languages").json()
        assert body == {
            "success": True,
            "data": [{"code": "vi", "name": "Vietnamese", "native_name": "Tiếng Việt"}],
            "message": None,
        }
        assert "tts_voice" not in body["data"][0]  # không lộ trường nội bộ

    def test_redeem_success(self, app, client):
        service = override(app, deps.get_access_service, async_mock_service("redeem"))
        session = AccessSession(
            id="s1",
            code="ABC123",
            method="cash",
            status="active",
            amount=50000,
            created_at=NOW,
            code_expires_at=NOW,
            access_expires_at=NOW,
        )
        service.redeem.return_value = ("jwt-token", session)
        response = client.post("/api/v1/access/token", json={"code": "abc123"})
        assert response.status_code == 200
        assert response.json()["data"]["access_token"] == "jwt-token"
        service.redeem.assert_awaited_once_with("abc123")

    def test_redeem_pending_payment_returns_409(self, app, client):
        service = override(app, deps.get_access_service, async_mock_service("redeem"))
        service.redeem.side_effect = PaymentPendingError("chưa xong")
        response = client.post("/api/v1/access/token", json={"code": "ABC123"})
        assert response.status_code == 409 and response.json()["error"]["code"] == "PAYMENT_PENDING"

    def test_redeem_validation_error(self, client):
        response = client.post("/api/v1/access/token", json={"code": "x"})
        body = response.json()
        assert response.status_code == 422 and body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["details"][0]["field"] == "code"

    def test_webhook_requires_signature_header(self, client):
        response = client.post("/api/v1/payments/webhook", json={"payment_id": "p", "status": "success"})
        assert response.status_code == 422

    def test_webhook_bad_signature_401(self, app, client):
        service = override(app, deps.get_payment_service, async_mock_service("handle_webhook"))
        service.handle_webhook.side_effect = UnauthorizedError("sai chữ ký", code="INVALID_SIGNATURE")
        response = client.post(
            "/api/v1/payments/webhook", json={"payment_id": "p", "status": "success"}, headers={"X-Signature": "bad"}
        )
        assert response.status_code == 401 and response.json()["error"]["code"] == "INVALID_SIGNATURE"


class TestVisitorGate:
    def test_content_requires_token(self, app, client):
        access = override(app, deps.get_access_service, async_mock_service("verify_token"))
        override(app, deps.get_auth_service, async_mock_service("get_user_from_token"))
        response = client.get("/api/v1/pois")
        assert response.status_code == 401 and response.json()["error"]["code"] == "ACCESS_REQUIRED"
        access.verify_token.assert_not_called()

    def test_invalid_token_rejected(self, app, client):
        access = override(app, deps.get_access_service, async_mock_service("verify_token"))
        auth = override(app, deps.get_auth_service, async_mock_service("get_user_from_token"))
        access.verify_token.side_effect = UnauthorizedError("x", code="TOKEN_INVALID")
        auth.get_user_from_token.side_effect = UnauthorizedError("y")
        response = client.get("/api/v1/pois", headers={"Authorization": "Bearer abc"})
        assert response.status_code == 401 and response.json()["error"]["code"] == "TOKEN_INVALID"


class TestContentEndpoints:
    def test_list_pois(self, app, client, as_visitor):
        service = override(app, deps.get_content_service, async_mock_service("list_pois"))
        service.list_pois.return_value = [localized_poi()]
        body = client.get("/api/v1/pois?lang=en").json()
        assert body["data"][0]["served_lang"] == "en"
        service.list_pois.assert_awaited_once_with("en")

    def test_get_poi_not_found(self, app, client, as_visitor):
        service = override(app, deps.get_content_service, async_mock_service("get_poi"))
        service.get_poi.side_effect = NotFoundError("Không tìm thấy POI", code="POI_NOT_FOUND")
        response = client.get("/api/v1/pois/xxx")
        assert response.status_code == 404 and response.json()["error"]["code"] == "POI_NOT_FOUND"

    def test_poi_insights_not_cached(self, app, client, as_visitor):
        from app.models.views import PoiInsights

        service = override(app, deps.get_poi_insights_service, async_mock_service("get"))
        service.get.return_value = PoiInsights(
            poi_id="p1",
            now_local="2026-10-09T09:40+07:00",
            today=4,
            open_status={"state": "open", "closes_at": "21:00", "minutes_left": 680},
            popular_times={"sample_size": 3, "by_day": None},
        )
        response = client.get("/api/v1/pois/p1/insights")
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        data = response.json()["data"]
        assert data["open_status"]["closes_at"] == "21:00" and data["popular_times"]["by_day"] is None
        service.get.assert_awaited_once_with("p1")

    def test_nearby_validates_coordinates(self, client, as_visitor):
        assert client.get("/api/v1/pois/nearby?lat=999&lng=108").status_code == 422

    def test_bundle_etag_304(self, app, client, as_visitor):
        content = override(app, deps.get_content_service, async_mock_service("compute_version", "build_bundle"))
        language = override(app, deps.get_language_service, async_mock_service("resolve_code"))
        language.resolve_code.return_value = "en"
        localization = override(app, deps.get_localization_service, async_mock_service("request_language"))
        localization.request_language.return_value = 2
        content.compute_version.return_value = "v1"
        response = client.get("/api/v1/content/bundle?lang=en", headers={"If-None-Match": 'W/"v1"'})
        assert response.status_code == 304
        assert response.headers["X-Translation-Pending"] == "2"  # app biết vẫn đang dịch
        content.build_bundle.assert_not_called()
        localization.request_language.assert_awaited_once_with("en")

    def test_recommend(self, app, client, as_visitor):
        service = override(app, deps.get_tour_service, async_mock_service("recommend"))
        service.recommend.return_value = RecommendedRoute(
            start_latitude=16.1, start_longitude=108.2, stops=[], total_distance_m=0, total_minutes=0
        )
        response = client.post("/api/v1/tours/recommend", json={"latitude": 16.1, "longitude": 108.2, "lang": "ja"})
        assert response.status_code == 200
        assert service.recommend.await_args.kwargs["lang"] == "ja"

    def test_chat_passes_session_and_handles_rate_limit(self, app, client, as_visitor):
        service = override(app, deps.get_chat_service, async_mock_service("ask"))
        service.ask.return_value = ChatAnswer(answer="Trả lời", lang="vi", sources=[], used_llm=False)
        assert client.post("/api/v1/chat", json={"question": "Giờ mở cửa?"}).status_code == 200
        assert service.ask.await_args.kwargs["session_id"] == "sess1"
        service.ask.side_effect = RateLimitError("quá giới hạn", code="CHAT_LIMIT_REACHED")
        assert client.post("/api/v1/chat", json={"question": "Giờ mở cửa?"}).status_code == 429

    def test_event_type_validated(self, app, client, as_visitor):
        override(app, deps.get_stats_service, async_mock_service("record_event"))
        assert client.post("/api/v1/events", json={"poi_id": "p", "type": "hack"}).status_code == 422
        assert client.post("/api/v1/events", json={"poi_id": "p", "type": "view"}).status_code == 201


class TestUiStrings:
    def test_ui_strings_public(self, app, client):
        service = override(app, deps.get_ui_text_service, async_mock_service("get_strings"))
        service.get_strings.return_value = ("ja", {"tabMap": "地図"}, False)
        body = client.get("/api/v1/ui-strings/ja").json()
        assert body["data"] == {"lang": "ja", "strings": {"tabMap": "地図"}, "is_fallback": False}


class TestMediaEndpoint:
    def _setup(self, app):
        service = override(app, deps.get_media_service, async_mock_service("get"))
        service.get.return_value = (b"0123456789", "audio/mpeg")
        return service

    def test_full_file(self, app, client):
        self._setup(app)
        response = client.get("/media/audio/abc.mp3")
        assert response.status_code == 200 and response.content == b"0123456789"
        assert response.headers["content-type"] == "audio/mpeg" and response.headers["accept-ranges"] == "bytes"

    def test_range_request_for_seeking(self, app, client):
        self._setup(app)
        response = client.get("/media/audio/abc.mp3", headers={"Range": "bytes=2-5"})
        assert response.status_code == 206 and response.content == b"2345"
        assert response.headers["content-range"] == "bytes 2-5/10"
        assert client.get("/media/audio/abc.mp3", headers={"Range": "bytes=-3"}).content == b"789"
        assert client.get("/media/audio/abc.mp3", headers={"Range": "bytes=50-"}).status_code == 416

    def test_missing_file_404(self, app, client):
        service = override(app, deps.get_media_service, async_mock_service("get"))
        service.get.side_effect = NotFoundError("Không tìm thấy file", code="MEDIA_NOT_FOUND")
        assert client.get("/media/audio/x.mp3").status_code == 404
