"""
Nghiệp vụ QUYỀN TRUY CẬP của du khách (theo sơ đồ Payment processing flow trong PRD).

Vòng đời một AccessSession:
    online:  pending --(webhook thành công)--> paid --(khách đổi mã)--> active --> expired
    cash:    (nhân viên xác nhận đã thu tiền) paid --(khách đổi mã)--> active --> expired
    bất kỳ:  --(thanh toán lỗi / admin thu hồi)--> cancelled
"""

from datetime import timedelta

from app.core.exceptions import (
    BusinessRuleError,
    NotFoundError,
    PaymentPendingError,
    UnauthorizedError,
)
from app.core.security import (
    TOKEN_TYPE_VISITOR,
    create_token,
    decode_token,
    generate_access_code,
    utcnow,
)
from app.models.domain import AccessMethod, AccessSession, AccessStatus

MAX_CODES_PER_REQUEST = 50


class AccessService:
    def __init__(self, *, session_repo, settings):
        self.session_repo = session_repo
        self.settings = settings

    async def _unique_code(self) -> str:
        for _ in range(10):
            code = generate_access_code()
            if not await self.session_repo.code_exists(code):
                return code
        raise BusinessRuleError("Không tạo được mã truy cập, vui lòng thử lại", code="CODE_GENERATION_FAILED")

    async def create_session(
        self, *, method: AccessMethod, status: AccessStatus, created_by: str | None = None, note: str | None = None
    ) -> AccessSession:
        now = utcnow()
        return await self.session_repo.insert(
            {
                "code": await self._unique_code(),
                "method": method,
                "status": status,
                "amount": self.settings.ACCESS_PRICE_VND,
                "currency": "VND",
                "created_by": created_by,
                "note": note,
                "created_at": now,
                "code_expires_at": now + timedelta(hours=self.settings.ACCESS_CODE_TTL_HOURS),
                "paid_at": now if status == AccessStatus.PAID else None,
            }
        )

    async def create_cash_codes(self, *, staff_id: str, quantity: int = 1, note: str | None = None):
        """Nhân viên đã thu tiền mặt -> sinh mã ngắn đưa cho khách."""
        if not 1 <= quantity <= MAX_CODES_PER_REQUEST:
            raise BusinessRuleError(f"Số lượng mã phải từ 1 đến {MAX_CODES_PER_REQUEST}", code="INVALID_QUANTITY")
        return [
            await self.create_session(
                method=AccessMethod.CASH, status=AccessStatus.PAID, created_by=staff_id, note=note
            )
            for _ in range(quantity)
        ]

    async def redeem(self, code: str) -> tuple[str, AccessSession]:
        """Khách nhập mã -> nhận access token. Trả về (token, session)."""
        code = code.strip().upper()
        session = await self.session_repo.get_by_code(code)
        if session is None:
            raise NotFoundError("Mã truy cập không đúng", code="INVALID_ACCESS_CODE")
        now = utcnow()

        if session.status == AccessStatus.PENDING:
            raise PaymentPendingError("Thanh toán chưa hoàn tất, vui lòng chờ trong giây lát")
        if session.status == AccessStatus.CANCELLED:
            raise BusinessRuleError("Mã truy cập đã bị hủy", code="ACCESS_CANCELLED")
        if session.status == AccessStatus.PAID:
            if session.code_expires_at < now:
                await self.session_repo.update(session.id, {"status": AccessStatus.EXPIRED})
                raise BusinessRuleError("Mã truy cập đã hết hạn", code="ACCESS_EXPIRED")
            # Lần đầu đổi mã -> kích hoạt, bắt đầu tính thời gian sử dụng
            session = await self.session_repo.update(
                session.id,
                {
                    "status": AccessStatus.ACTIVE,
                    "activated_at": now,
                    "access_expires_at": now + timedelta(hours=self.settings.VISITOR_TOKEN_HOURS),
                },
            )
        elif session.status == AccessStatus.ACTIVE:
            # Đã kích hoạt: cho đổi lại (vd khách xóa cache trình duyệt) nếu còn hạn
            if session.access_expires_at and session.access_expires_at < now:
                await self.session_repo.update(session.id, {"status": AccessStatus.EXPIRED})
                raise BusinessRuleError("Quyền truy cập đã hết hạn", code="ACCESS_EXPIRED")
        else:
            raise BusinessRuleError("Quyền truy cập đã hết hạn", code="ACCESS_EXPIRED")

        token, _ = create_token(
            subject=session.id,
            token_type=TOKEN_TYPE_VISITOR,
            expires_delta=session.access_expires_at - now,
            secret=self.settings.JWT_SECRET,
            algorithm=self.settings.JWT_ALGORITHM,
        )
        return token, session

    async def verify_token(self, token: str) -> AccessSession:
        """Kiểm tra token du khách: chữ ký hợp lệ + phiên còn hoạt động (admin có thể thu hồi)."""
        payload = decode_token(
            token,
            secret=self.settings.JWT_SECRET,
            expected_type=TOKEN_TYPE_VISITOR,
            algorithm=self.settings.JWT_ALGORITHM,
        )
        session = await self.session_repo.get_by_id(payload["sub"])
        if session is None or session.status != AccessStatus.ACTIVE:
            raise UnauthorizedError("Quyền truy cập không còn hiệu lực", code="ACCESS_REVOKED")
        return session

    async def search(self, *, status: str | None, page: int, size: int):
        return await self.session_repo.search(status=status, skip=(page - 1) * size, limit=size)

    async def revoke(self, session_id: str) -> AccessSession:
        session = await self.session_repo.get_by_id(session_id)
        if session is None:
            raise NotFoundError("Không tìm thấy phiên truy cập")
        return await self.session_repo.update(session_id, {"status": AccessStatus.CANCELLED})
