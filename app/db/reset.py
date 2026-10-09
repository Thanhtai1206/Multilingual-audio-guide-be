"""
Xóa SẠCH database rồi tạo lại dữ liệu ban đầu (ngôn ngữ, admin, dữ liệu mẫu).
Dùng khi muốn demo lại từ đầu. Chạy:   python -m app.db.reset --yes
"""

import asyncio
import sys

from app.core.config import get_settings
from app.db.indexes import ensure_indexes
from app.db.mongo import check_connection, create_client, mask_uri
from app.db.seed import seed_languages, seed_sample_content
from app.repositories.repositories import AdminUserRepository
from app.services.auth_service import AuthService


async def reset() -> None:
    settings = get_settings()
    client = create_client(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    await check_connection(db, settings.MONGO_URI)
    await client.drop_database(settings.MONGO_DB_NAME)
    await ensure_indexes(db)
    await seed_languages(db)
    await AuthService(user_repo=AdminUserRepository(db), settings=settings).ensure_first_admin(
        settings.FIRST_ADMIN_USERNAME, settings.FIRST_ADMIN_PASSWORD
    )
    if settings.SEED_SAMPLE_DATA:
        await seed_sample_content(db)
    client.close()
    print(f"Đã xóa và khởi tạo lại database '{settings.MONGO_DB_NAME}' tại {mask_uri(settings.MONGO_URI)}")


if __name__ == "__main__":
    if "--yes" not in sys.argv:
        print("Lệnh này XÓA TOÀN BỘ dữ liệu (POI, bản dịch, audio, mã truy cập...). Chạy lại với --yes để xác nhận.")
        sys.exit(1)
    asyncio.run(reset())
