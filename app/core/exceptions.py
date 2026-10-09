"""
Ngoại lệ nghiệp vụ dùng chung cho cả 3 lớp.

Lớp Service chỉ ném các ngoại lệ này (không biết gì về HTTP).
Lớp API (app/api/errors.py) mới là nơi quy đổi chúng thành mã HTTP 4xx/5xx.
Nhờ vậy Service có thể tái sử dụng ở nơi khác (script, worker) mà không phụ thuộc web.
"""

from typing import Any


class AppError(Exception):
    """Lỗi gốc. `code` là mã máy đọc được, `message` là thông báo cho người dùng."""

    code: str = "APP_ERROR"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class NotFoundError(AppError):
    code = "NOT_FOUND"


class ConflictError(AppError):
    code = "CONFLICT"


class BusinessRuleError(AppError):
    """Dữ liệu hợp lệ về kiểu nhưng vi phạm quy tắc nghiệp vụ."""

    code = "BUSINESS_RULE_VIOLATION"


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    code = "FORBIDDEN"


class PaymentPendingError(AppError):
    """Phiên truy cập tồn tại nhưng chưa thanh toán xong."""

    code = "PAYMENT_PENDING"


class RateLimitError(AppError):
    code = "RATE_LIMITED"


class ExternalServiceError(AppError):
    """Dịch vụ bên ngoài (dịch máy, TTS, LLM, cổng thanh toán) lỗi."""

    code = "EXTERNAL_SERVICE_ERROR"
