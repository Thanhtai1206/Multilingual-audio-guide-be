"""Nghiệp vụ thanh toán online (theo luồng "Online Payment Flow" trong PRD)."""

import logging

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import utcnow
from app.models.domain import AccessMethod, AccessSession, AccessStatus, Payment, PaymentStatus

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, *, payment_repo, session_repo, access_service, gateway):
        self.payment_repo = payment_repo
        self.session_repo = session_repo
        self.access_service = access_service
        self.gateway = gateway

    async def start_online_payment(self) -> tuple[AccessSession, Payment, str]:
        """B1: tạo phiên chờ thanh toán + bản ghi payment + URL cổng thanh toán."""
        session = await self.access_service.create_session(method=AccessMethod.ONLINE, status=AccessStatus.PENDING)
        payment = await self.payment_repo.insert(
            {
                "session_id": session.id,
                "provider": self.gateway.name,
                "amount": session.amount,
                "currency": session.currency,
                "status": PaymentStatus.PENDING,
                "created_at": utcnow(),
            }
        )
        return session, payment, self.gateway.create_payment_url(payment.id, payment.amount)

    async def get_payment(self, payment_id: str) -> tuple[Payment, AccessSession]:
        payment = await self.payment_repo.get_by_id(payment_id)
        if payment is None:
            raise NotFoundError("Không tìm thấy giao dịch", code="PAYMENT_NOT_FOUND")
        session = await self.session_repo.get_by_id(payment.session_id)
        return payment, session

    async def handle_webhook(self, payload: dict, signature: str) -> Payment:
        """
        B2: cổng thanh toán báo kết quả.
        - Chữ ký sai -> từ chối (chống giả mạo "đã thanh toán").
        - Idempotent: cổng có thể gọi lại nhiều lần, chỉ xử lý lần đầu.
        """
        if not self.gateway.verify_webhook(payload, signature):
            raise UnauthorizedError("Chữ ký webhook không hợp lệ", code="INVALID_SIGNATURE")
        payment, session = await self.get_payment(str(payload.get("payment_id")))
        if payment.status != PaymentStatus.PENDING:
            return payment

        now = utcnow()
        success = payload.get("status") == "success"
        payment = await self.payment_repo.update(
            payment.id,
            {
                "status": PaymentStatus.SUCCESS if success else PaymentStatus.FAILED,
                "provider_ref": payload.get("provider_ref"),
                "completed_at": now,
            },
        )
        await self.session_repo.update(
            session.id,
            {"status": AccessStatus.PAID, "paid_at": now} if success else {"status": AccessStatus.CANCELLED},
        )
        logger.info("Thanh toán %s -> %s", payment.id, payment.status)
        return payment
