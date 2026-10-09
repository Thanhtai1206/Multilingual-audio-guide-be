"""
Định dạng phản hồi CHUẨN cho toàn bộ API.

Thành công:  {"success": true,  "data": {...}, "message": null}
Lỗi:         {"success": false, "error": {"code": "POI_NOT_FOUND", "message": "...", "details": null}}

Frontend chỉ cần kiểm tra `success` là biết kết quả, và đọc `error.code` để xử lý từng trường hợp.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


def ok(data: Any = None, message: str | None = None) -> dict:
    return {"success": True, "data": data, "message": message}


class PageQuery(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


# Mô tả các lỗi dùng chung để hiện trong Swagger
COMMON_ERRORS = {
    401: {"model": ErrorResponse, "description": "Chưa xác thực / token không hợp lệ"},
    403: {"model": ErrorResponse, "description": "Không đủ quyền"},
    404: {"model": ErrorResponse, "description": "Không tìm thấy"},
    422: {"model": ErrorResponse, "description": "Dữ liệu gửi lên không hợp lệ"},
}
