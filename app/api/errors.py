"""
Xử lý lỗi TẬP TRUNG.

Thay vì try/except ở từng endpoint, mọi ngoại lệ đều "bay" lên đây và được
chuyển thành JSON chuẩn {"success": false, "error": {...}} với mã HTTP phù hợp.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AppError,
    BusinessRuleError,
    ConflictError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    PaymentPendingError,
    RateLimitError,
    UnauthorizedError,
)

logger = logging.getLogger(__name__)

# Bảng quy đổi: ngoại lệ nghiệp vụ -> mã HTTP
STATUS_MAP: dict[type[AppError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    BusinessRuleError: 400,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    PaymentPendingError: 409,
    RateLimitError: 429,
    ExternalServiceError: 503,
}


def status_for(exc: AppError) -> int:
    for cls in type(exc).__mro__:
        if cls in STATUS_MAP:
            return STATUS_MAP[cls]
    return 400


def error_json(status: int, code: str, message: str, details=None, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"success": False, "error": {"code": code, "message": message, "details": details}},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        status = status_for(exc)
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return error_json(status, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err["loc"] if p != "body"), "message": err["msg"]}
            for err in exc.errors()
        ]
        return error_json(422, "VALIDATION_ERROR", "Dữ liệu gửi lên không hợp lệ", details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return error_json(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception):
        logger.exception("Lỗi không mong muốn: %s", exc)
        return error_json(500, "INTERNAL_ERROR", "Lỗi hệ thống, vui lòng thử lại sau")
