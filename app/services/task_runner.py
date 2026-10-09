"""
Chạy tác vụ nền (dịch + tạo audio mất vài giây/ngôn ngữ, không bắt admin chờ).

Semaphore giới hạn số tác vụ chạy cùng lúc để không bị Google/Edge chặn vì gọi dồn dập.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class BackgroundTaskRunner:
    def __init__(self, max_concurrency: int = 3):
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: set[asyncio.Task] = set()

    @property
    def pending_count(self) -> int:
        return len(self._tasks)

    def submit(self, factory: Callable[[], Awaitable], name: str = "task") -> None:
        task = asyncio.create_task(self._run(factory, name), name=name)
        self._tasks.add(task)  # giữ tham chiếu để task không bị garbage-collect
        task.add_done_callback(self._tasks.discard)

    async def _run(self, factory: Callable[[], Awaitable], name: str) -> None:
        async with self._semaphore:
            try:
                await factory()
            except Exception:  # noqa: BLE001 - tác vụ nền không được làm sập server
                logger.exception("Tác vụ nền '%s' lỗi", name)

    async def wait_all(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)


class InlineTaskRunner:
    """Bản dùng cho test: chạy tuần tự, có thể chờ xong ngay."""

    def __init__(self):
        self._queue: list[Callable[[], Awaitable]] = []

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    def submit(self, factory: Callable[[], Awaitable], name: str = "task") -> None:
        self._queue.append(factory)

    async def wait_all(self) -> None:
        while self._queue:
            await self._queue.pop(0)()

    async def shutdown(self) -> None:
        self._queue.clear()
