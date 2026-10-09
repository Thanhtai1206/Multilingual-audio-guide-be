"""
Phục vụ file audio lưu trong MongoDB (MEDIA_STORAGE=mongo).

Hỗ trợ header Range (206 Partial Content) để trình duyệt tua được audio,
và cache lâu dài vì tên file là hash nội dung (nội dung đổi -> tên đổi).
"""

import re

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response

from app.api.deps import get_media_service

router = APIRouter(include_in_schema=False)

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


@router.get("/{key:path}")
async def get_media(
    key: str, range_header: str | None = Header(None, alias="Range"), service=Depends(get_media_service)
):
    data, content_type = await service.get(key)
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": f'"{key.rsplit("/", 1)[-1].split(".")[0]}"',
    }
    size = len(data)
    match = RANGE_RE.fullmatch(range_header.strip()) if range_header else None
    if match and (match.group(1) or match.group(2)):
        if match.group(1):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1
        else:  # "bytes=-500" = 500 byte cuối
            start, end = max(size - int(match.group(2)), 0), size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return Response(data[start : end + 1], status_code=206, media_type=content_type, headers=headers)
    return Response(data, media_type=content_type, headers=headers)
