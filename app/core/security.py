"""
Tiện ích bảo mật: băm mật khẩu (bcrypt) và tạo/kiểm tra JWT.

Hệ thống có 2 loại token:
- "admin":   cấp cho nhân viên/quản trị khi đăng nhập dashboard.
- "visitor": cấp cho du khách sau khi đổi mã truy cập (đã thanh toán).
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.exceptions import UnauthorizedError

TOKEN_TYPE_ADMIN = "admin"
TOKEN_TYPE_VISITOR = "visitor"

# Bảng chữ cho mã truy cập: bỏ các ký tự dễ nhầm (0/O, 1/I/L) để khách nhập tay dễ hơn
ACCESS_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    secret: str,
    algorithm: str = "HS256",
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """Tạo JWT. Trả về (token, thời điểm hết hạn)."""
    expires_at = utcnow() + expires_delta
    payload: dict[str, Any] = {"sub": subject, "typ": token_type, "exp": expires_at, "iat": utcnow()}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm), expires_at


def decode_token(token: str, *, secret: str, expected_type: str, algorithm: str = "HS256") -> dict[str, Any]:
    """Giải mã + kiểm tra chữ ký, hạn dùng và loại token."""
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token đã hết hạn", code="TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Token không hợp lệ", code="TOKEN_INVALID") from exc
    if payload.get("typ") != expected_type:
        raise UnauthorizedError("Sai loại token", code="TOKEN_INVALID")
    return payload


def generate_access_code(length: int = 6) -> str:
    return "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(length))


def sign_payload(message: str, secret: str) -> str:
    """Chữ ký HMAC-SHA256 - dùng để xác thực webhook từ cổng thanh toán."""
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(message: str, signature: str, secret: str) -> bool:
    return hmac.compare_digest(sign_payload(message, secret), signature or "")
