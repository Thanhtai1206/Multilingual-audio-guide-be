"""Test nghiệp vụ truy cập/thanh toán, tài khoản admin, chatbot và thống kê."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PaymentPendingError,
    RateLimitError,
    UnauthorizedError,
)
from app.core.security import utcnow
from app.integrations.payment_gateway import MockPaymentGateway
from app.models.domain import AdminRole
from app.services.chat_service import ChatService
from app.services.payment_service import PaymentService
from tests.conftest import poi_data
from tests.fakes import FakeLLM


class TestAccessService:
    async def test_cash_code_redeem_flow(self, services):
        (session,) = await services["access"].create_cash_codes(staff_id="staff1")
        assert session.status == "paid" and len(session.code) == 6
        token, active = await services["access"].redeem(session.code.lower())  # không phân biệt hoa thường
        assert active.status == "active" and active.access_expires_at
        verified = await services["access"].verify_token(token)
        assert verified.id == session.id

    async def test_redeem_again_while_active_reissues_token(self, services):
        (session,) = await services["access"].create_cash_codes(staff_id="s")
        await services["access"].redeem(session.code)
        token, _ = await services["access"].redeem(session.code)
        assert token

    async def test_invalid_code(self, services):
        with pytest.raises(NotFoundError):
            await services["access"].redeem("XXXXXX")

    async def test_quantity_limits(self, services):
        with pytest.raises(BusinessRuleError):
            await services["access"].create_cash_codes(staff_id="s", quantity=0)
        assert len(await services["access"].create_cash_codes(staff_id="s", quantity=3)) == 3

    async def test_expired_code(self, services, repos):
        (session,) = await services["access"].create_cash_codes(staff_id="s")
        await repos["session"].update(session.id, {"code_expires_at": utcnow() - timedelta(minutes=1)})
        with pytest.raises(BusinessRuleError) as exc:
            await services["access"].redeem(session.code)
        assert exc.value.code == "ACCESS_EXPIRED"
        assert (await repos["session"].get_by_id(session.id)).status == "expired"

    async def test_revoked_token_rejected(self, services):
        (session,) = await services["access"].create_cash_codes(staff_id="s")
        token, _ = await services["access"].redeem(session.code)
        await services["access"].revoke(session.id)
        with pytest.raises(UnauthorizedError):
            await services["access"].verify_token(token)

    async def test_garbage_token_rejected(self, services):
        with pytest.raises(UnauthorizedError):
            await services["access"].verify_token("abc.def.ghi")


class TestPaymentService:
    @pytest.fixture
    def payment(self, services, repos, settings):
        gateway = MockPaymentGateway("http://x", settings.PAYMENT_WEBHOOK_SECRET)
        return PaymentService(
            payment_repo=repos["payment"],
            session_repo=repos["session"],
            access_service=services["access"],
            gateway=gateway,
        ), gateway

    async def test_online_success_flow(self, payment, services):
        service, gateway = payment
        session, pay, url = await service.start_online_payment()
        assert url.endswith(pay.id) and session.status == "pending"
        with pytest.raises(PaymentPendingError):
            await services["access"].redeem(session.code)
        payload = {"payment_id": pay.id, "status": "success", "provider_ref": "R1"}
        result = await service.handle_webhook(payload, gateway.sign(payload))
        assert result.status == "success"
        token, _ = await services["access"].redeem(session.code)
        assert token

    async def test_webhook_bad_signature(self, payment):
        service, _ = payment
        _, pay, _ = await service.start_online_payment()
        with pytest.raises(UnauthorizedError):
            await service.handle_webhook({"payment_id": pay.id, "status": "success"}, "fake-signature")

    async def test_webhook_idempotent_and_failure(self, payment, services):
        service, gateway = payment
        session, pay, _ = await service.start_online_payment()
        failed = {"payment_id": pay.id, "status": "failed"}
        await service.handle_webhook(failed, gateway.sign(failed))
        success = {"payment_id": pay.id, "status": "success"}
        again = await service.handle_webhook(success, gateway.sign(success))
        assert again.status == "failed"  # lần gọi sau không đổi kết quả
        with pytest.raises(BusinessRuleError):
            await services["access"].redeem(session.code)


class TestAuthService:
    async def test_first_admin_and_login(self, services):
        await services["auth"].ensure_first_admin("admin", "admin123")
        await services["auth"].ensure_first_admin("admin2", "x")  # đã có user -> không tạo thêm
        token, user = await services["auth"].login("ADMIN", "admin123")
        assert user.role == AdminRole.ADMIN and user.last_login_at
        assert (await services["auth"].get_user_from_token(token)).id == user.id

    async def test_wrong_password_same_message(self, services):
        await services["auth"].ensure_first_admin("admin", "admin123")
        with pytest.raises(UnauthorizedError) as e1:
            await services["auth"].login("admin", "sai-mat-khau")
        with pytest.raises(UnauthorizedError) as e2:
            await services["auth"].login("khong-ton-tai", "admin123")
        assert e1.value.message == e2.value.message

    async def test_disabled_user_cannot_login(self, services):
        user = await services["auth"].create_user(
            username="staff", password="12345678", full_name="NV", role=AdminRole.STAFF
        )
        admin = await services["auth"].create_user(
            username="boss", password="12345678", full_name="B", role=AdminRole.ADMIN
        )
        await services["auth"].update_user(user.id, {"is_active": False}, actor=admin)
        with pytest.raises(UnauthorizedError):
            await services["auth"].login("staff", "12345678")

    async def test_cannot_lock_self_and_duplicate_username(self, services):
        admin = await services["auth"].create_user(
            username="boss", password="12345678", full_name="B", role=AdminRole.ADMIN
        )
        with pytest.raises(BusinessRuleError):
            await services["auth"].update_user(admin.id, {"is_active": False}, actor=admin)
        with pytest.raises(ConflictError):
            await services["auth"].create_user(
                username="BOSS", password="12345678", full_name="x", role=AdminRole.STAFF
            )

    async def test_admin_token_is_not_visitor_token(self, services):
        await services["auth"].ensure_first_admin("admin", "admin123")
        token, _ = await services["auth"].login("admin", "admin123")
        with pytest.raises(UnauthorizedError):
            await services["access"].verify_token(token)


class TestChatService:
    @pytest.fixture
    async def content(self, services, repos):
        await services["poi"].create(poi_data("QUAN_AM"), auto_localize=False)
        now = utcnow()
        await repos["knowledge"].insert(
            {
                "title": "Giờ mở cửa",
                "content": "Chùa mở cửa từ 6 giờ đến 21 giờ.",
                "tags": [],
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )

    async def test_extractive_answer_without_llm(self, services, content):
        answer = await services["chat"].ask(question="Tượng Quan Âm cao bao nhiêu mét?", lang="vi", session_id="s")
        assert "67 mét" in answer.answer and answer.sources[0].type == "poi" and not answer.used_llm

    async def test_matches_without_diacritics(self, services, content):
        answer = await services["chat"].ask(question="gio mo cua", lang="vi", session_id="s")
        assert "6 giờ" in answer.answer

    async def test_answer_translated_to_user_language(self, services, content):
        answer = await services["chat"].ask(question="opening hours mở cửa", lang="en", session_id="s")
        assert answer.answer.startswith("[en]") and answer.lang == "en"

    async def test_off_topic_without_llm_explains_scope(self, services, content):
        answer = await services["chat"].ask(question="xyz qwerty", lang="vi", session_id="s")
        assert "Chùa Linh Ứng" in answer.answer and "Xin lỗi" not in answer.answer and answer.sources == []

    async def test_cache_hit(self, services, content):
        # Cache dùng cho câu hỏi mở đầu (2 phiên khác nhau hỏi cùng 1 câu)
        await services["chat"].ask(question="Giờ mở cửa?", lang="vi", session_id="s1")
        again = await services["chat"].ask(question="giờ mở cửa", lang="vi", session_id="s2")
        assert again.cached is True

    async def test_daily_limit(self, services, content, settings):
        for _ in range(settings.CHAT_DAILY_LIMIT):
            await services["chat"].ask(question="Giờ mở cửa?", lang="vi", session_id="limit")
        with pytest.raises(RateLimitError):
            await services["chat"].ask(question="Giờ mở cửa?", lang="vi", session_id="limit")

    def _with_llm(self, services, repos, translator, llm, **kw):
        return ChatService(
            poi_repo=repos["poi"],
            knowledge_repo=repos["knowledge"],
            chat_repo=repos["chat"],
            language_service=services["language"],
            translator=translator,
            llm=llm,
            cache_repo=repos["chat_cache"],
            daily_limit=99,
            **kw,
        )

    async def test_llm_gets_full_knowledge_base_and_scope_rules(self, services, content, repos, translator):
        llm = FakeLLM("Tượng Quan Âm cao khoảng 67 mét, hướng ra biển.")
        answer = await self._with_llm(services, repos, translator, llm).ask(
            question="Tượng Quan Âm cao bao nhiêu?", lang="en", session_id="x"
        )
        assert answer.used_llm and answer.answer == "Tượng Quan Âm cao khoảng 67 mét, hướng ra biển."
        system = llm.messages[0]["content"]
        assert "TÀI LIỆU CỦA CHÙA" in system and "NGOÀI PHẠM VI" in system and "English" in system
        assert "67 mét" in system and "6 giờ đến 21 giờ" in system  # gửi cả POI lẫn bài viết
        assert llm.messages[-1] == {"role": "user", "content": "Tượng Quan Âm cao bao nhiêu?"}
        assert answer.sources and answer.sources[0].title == "Tượng Phật Bà Quan Thế Âm"

    async def test_llm_knows_poi_details_and_current_time(self, services, content, repos, translator):
        from datetime import UTC, datetime

        poi = (await repos["poi"].list_active())[0]
        await services["poi"].update(
            poi.id,
            {"opening_hours": [{"day": d, "open": "06:00", "close": "21:00"} for d in range(7)], "tips": "Mang nón."},
            auto_localize=False,
        )
        llm = FakeLLM("Đang mở cửa đến 21:00.")
        chat = self._with_llm(services, repos, translator, llm, clock=lambda: datetime(2026, 10, 9, 2, 40, tzinfo=UTC))
        await chat.ask(question="Giờ này còn mở cửa không?", lang="vi", session_id="t")
        system = llm.messages[0]["content"]
        assert "GIỜ HIỆN TẠI Ở CHÙA: Thứ Sáu, 09/10/2026 09:40" in system
        assert "Thứ Hai - Chủ nhật: 06:00-21:00" in system and "Lưu ý: Mang nón." in system

    async def test_llm_answers_even_without_matching_document(self, services, content, repos, translator):
        """Không còn câu "Xin lỗi chưa có thông tin": câu nào cũng do AI xử lý (kể cả từ chối ngoài phạm vi)."""
        llm = FakeLLM("Mình chỉ hỗ trợ các câu hỏi về Chùa Linh Ứng.")
        answer = await self._with_llm(services, repos, translator, llm).ask(
            question="Viết giúp tôi code Python", lang="vi", session_id="x"
        )
        assert answer.used_llm and llm.calls == 1 and answer.sources == []  # từ chối -> không kèm nguồn lạc đề

    async def test_follow_up_question_sends_history_and_skips_cache(self, services, content, repos, translator):
        llm = FakeLLM("Câu trả lời")
        chat = self._with_llm(services, repos, translator, llm, history_turns=4)
        await chat.ask(question="Tượng Quan Âm cao bao nhiêu?", lang="vi", session_id="h")
        await chat.ask(question="Nó được xây năm nào?", lang="vi", session_id="h")
        roles = [m["role"] for m in llm.messages]
        assert roles == ["system", "user", "assistant", "user"]
        assert llm.messages[1]["content"] == "Tượng Quan Âm cao bao nhiêu?"
        # câu nối tiếp giống hệt câu của phiên khác vẫn phải hỏi AI, không lấy cache
        await chat.ask(question="Nó được xây năm nào?", lang="vi", session_id="h")
        assert llm.calls == 3

    async def test_large_knowledge_base_sends_only_relevant_parts(self, services, content, repos, translator):
        from app.services import chat_service

        now = utcnow()
        for i in range(40):
            await repos["knowledge"].insert(
                {
                    "title": f"Bài {i}",
                    "content": "nội dung dài " * 60,
                    "tags": [],
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        llm = FakeLLM("ok")
        await self._with_llm(services, repos, translator, llm).ask(question="Giờ mở cửa?", lang="vi", session_id="z")
        system = llm.messages[0]["content"]
        assert len(system) < chat_service.FULL_CONTEXT_MAX_CHARS + 4000
        assert "6 giờ đến 21 giờ" in system  # đoạn liên quan nhất vẫn có mặt

    async def test_llm_error_falls_back_to_extractive(self, services, content, repos, translator):
        broken = await self._with_llm(services, repos, translator, FakeLLM(fail=True)).ask(
            question="Tượng Quan Âm cao mấy mét?", lang="vi", session_id="x"
        )
        assert not broken.used_llm and "67 mét" in broken.answer

    async def test_fallback_answer_is_not_cached_when_llm_recovers(self, services, content, repos, translator):
        """AI lỗi tạm thời -> câu dự phòng không được cache; lần sau AI chạy lại thì trả lời bằng AI."""
        llm = FakeLLM("Xin chào! Mình là hướng dẫn viên ảo.", fail=True)
        chat = self._with_llm(services, repos, translator, llm)
        first = await chat.ask(question="xin chào", lang="vi", session_id="a")
        assert not first.used_llm
        llm.fail = False
        second = await chat.ask(question="xin chào", lang="vi", session_id="b")
        assert second.used_llm and not second.cached and second.answer.startswith("Xin chào")


class TestStatsService:
    async def test_overview_and_events(self, services):
        poi = await services["poi"].create(poi_data("A"), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["vi", "en"])
        await services["stats"].record_event(poi_id=poi.id, event_type="view", lang="en", session_id=None)
        overview = await services["stats"].overview()
        assert overview.total_pois == 1 and overview.total_events == 1
        assert overview.top_pois[0]["name"] == poi.name
        assert overview.localization_coverage_percent == pytest.approx(100 * 2 / 16, abs=0.1)

    async def test_record_event_unknown_poi(self, services):
        with pytest.raises(NotFoundError):
            await services["stats"].record_event(poi_id="nope", event_type="view", lang="en", session_id=None)


class TestLanguageServiceWithMocks:
    """Ví dụ unit test THUẦN: mock hoàn toàn repository bằng AsyncMock (không cần DB)."""

    async def test_cannot_disable_required_language(self):
        from app.services.language_service import LanguageService

        repo = MagicMock()
        repo.set_active = AsyncMock()
        service = LanguageService(repo, source_lang="vi", fallback_lang="en")
        with pytest.raises(BusinessRuleError):
            await service.set_active("vi", False)
        repo.set_active.assert_not_called()

    async def test_resolve_code_unknown_returns_fallback(self):
        from app.services.language_service import LanguageService

        repo = MagicMock()
        repo.get_by_code = AsyncMock(return_value=None)
        service = LanguageService(repo, source_lang="vi", fallback_lang="en")
        assert await service.resolve_code("xx") == "en"


async def test_chat_cache_shared_across_instances(services, repos, translator):
    """Cache nằm trong MongoDB -> service mới (vd sau khi khởi động lại) vẫn dùng được."""
    await services["poi"].create(
        __import__("tests.conftest", fromlist=["poi_data"]).poi_data("QA"), auto_localize=False
    )
    await services["chat"].ask(question="Tượng Quan Âm cao bao nhiêu?", lang="vi", session_id="a")
    fresh = ChatService(
        poi_repo=repos["poi"],
        knowledge_repo=repos["knowledge"],
        chat_repo=repos["chat"],
        language_service=services["language"],
        translator=translator,
        llm=None,
        cache_repo=repos["chat_cache"],
        daily_limit=99,
    )
    answer = await fresh.ask(question="tuong quan am cao bao nhieu", lang="vi", session_id="b")
    assert answer.cached is True
