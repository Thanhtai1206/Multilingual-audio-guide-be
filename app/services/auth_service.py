"""Nghiệp vụ tài khoản quản trị: đăng nhập, quản lý nhân viên."""

from datetime import timedelta
from typing import Any

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, UnauthorizedError
from app.core.security import (
    TOKEN_TYPE_ADMIN,
    create_token,
    decode_token,
    hash_password,
    utcnow,
    verify_password,
)
from app.models.domain import AdminRole, AdminUser


class AuthService:
    def __init__(self, *, user_repo, settings):
        self.user_repo = user_repo
        self.settings = settings

    async def login(self, username: str, password: str) -> tuple[str, AdminUser]:
        user = await self.user_repo.get_by_username(username.strip().lower())
        # Cùng 1 thông báo cho cả "sai tài khoản" và "sai mật khẩu" để không lộ username nào tồn tại
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Sai tên đăng nhập hoặc mật khẩu", code="INVALID_CREDENTIALS")
        if not user.is_active:
            raise UnauthorizedError("Tài khoản đã bị khóa", code="ACCOUNT_DISABLED")
        user = await self.user_repo.update(user.id, {"last_login_at": utcnow()})
        token, _ = create_token(
            subject=user.id,
            token_type=TOKEN_TYPE_ADMIN,
            expires_delta=timedelta(minutes=self.settings.ADMIN_TOKEN_MINUTES),
            secret=self.settings.JWT_SECRET,
            algorithm=self.settings.JWT_ALGORITHM,
            extra={"role": user.role},
        )
        return token, user

    async def get_user_from_token(self, token: str) -> AdminUser:
        payload = decode_token(
            token,
            secret=self.settings.JWT_SECRET,
            expected_type=TOKEN_TYPE_ADMIN,
            algorithm=self.settings.JWT_ALGORITHM,
        )
        user = await self.user_repo.get_by_id(payload["sub"])
        if user is None or not user.is_active:
            raise UnauthorizedError("Tài khoản không còn hiệu lực", code="ACCOUNT_DISABLED")
        return user

    async def list_users(self) -> list[AdminUser]:
        return await self.user_repo.list(sort=[("username", 1)])

    async def create_user(self, *, username: str, password: str, full_name: str, role: AdminRole) -> AdminUser:
        username = username.strip().lower()
        if await self.user_repo.get_by_username(username):
            raise ConflictError("Tên đăng nhập đã tồn tại", code="USERNAME_EXISTS")
        return await self.user_repo.insert(
            {
                "username": username,
                "password_hash": hash_password(password),
                "full_name": full_name,
                "role": role,
                "is_active": True,
                "created_at": utcnow(),
            }
        )

    async def update_user(self, user_id: str, data: dict[str, Any], *, actor: AdminUser) -> AdminUser:
        target = await self.user_repo.get_by_id(user_id)
        if target is None:
            raise NotFoundError("Không tìm thấy tài khoản")
        if target.id == actor.id and (data.get("is_active") is False or data.get("role") == AdminRole.STAFF):
            raise BusinessRuleError("Không thể tự khóa hoặc tự hạ quyền chính mình", code="SELF_LOCKOUT")
        update = {k: v for k, v in data.items() if k in {"full_name", "role", "is_active"} and v is not None}
        if data.get("password"):
            update["password_hash"] = hash_password(data["password"])
        return await self.user_repo.update(user_id, update)

    async def change_password(self, user: AdminUser, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.password_hash):
            raise BusinessRuleError("Mật khẩu hiện tại không đúng", code="WRONG_PASSWORD")
        await self.user_repo.update(user.id, {"password_hash": hash_password(new_password)})

    async def ensure_first_admin(self, username: str, password: str) -> None:
        """Tạo tài khoản admin đầu tiên nếu hệ thống chưa có tài khoản nào."""
        if await self.user_repo.count() == 0:
            await self.create_user(
                username=username, password=password, full_name="Quản trị viên", role=AdminRole.ADMIN
            )
