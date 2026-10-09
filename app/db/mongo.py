"""
Kết nối MongoDB.

- Mặc định: MongoDB thật qua Motor (driver async chính thức), vd mongodb://localhost:27017
  hoặc MongoDB Atlas (mongodb+srv://...). Dữ liệu lưu bền vững.
- "mongomock://..." chỉ dành cho bộ test tự động (MongoDB giả lập trong RAM, cần requirements-dev).
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(RuntimeError):
    """Không kết nối được MongoDB lúc khởi động."""


def create_client(uri: str):
    if uri.startswith("mongomock://"):
        try:
            from mongomock_motor import AsyncMongoMockClient
        except ImportError as exc:  # chỉ cài trong requirements-dev
            raise DatabaseUnavailableError(
                "MONGO_URI=mongomock:// chỉ dùng cho test. Hãy đặt MONGO_URI=mongodb://localhost:27017"
            ) from exc
        logger.warning("Đang dùng MongoDB GIẢ LẬP trong RAM - dữ liệu sẽ mất khi tắt server")
        return AsyncMongoMockClient(tz_aware=True)
    return AsyncIOMotorClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000, appname="linh-ung-audio-guide")


def mask_uri(uri: str) -> str:
    """Ẩn mật khẩu trong chuỗi kết nối khi ghi log: mongodb+srv://user:***@host."""
    if "@" not in uri or "://" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


async def check_connection(db: AsyncIOMotorDatabase, uri: str) -> None:
    """Fail-fast: không có DB thì dừng ngay với hướng dẫn rõ ràng, thay vì lỗi khó hiểu lúc chạy."""
    try:
        await db.command("ping")
    except Exception as exc:  # noqa: BLE001
        raise DatabaseUnavailableError(
            f"Không kết nối được MongoDB tại {mask_uri(uri)} ({exc.__class__.__name__}).\n"
            "  - Cài MongoDB trên máy: kiểm tra service 'MongoDB' đang chạy (services.msc), hoặc\n"
            "  - Dùng Docker: docker compose up -d mongo, hoặc\n"
            "  - Dùng MongoDB Atlas: đặt MONGO_URI=mongodb+srv://... trong file .env"
        ) from exc
    logger.info("Đã kết nối MongoDB: %s / db=%s", mask_uri(uri), db.name)


async def ping(db: AsyncIOMotorDatabase) -> bool:
    try:
        await db.command("ping")
        return True
    except Exception:  # noqa: BLE001 - chỉ dùng cho health check
        return False
