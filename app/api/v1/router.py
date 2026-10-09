"""Gom tất cả router của API v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import access, admin, content

api_router = APIRouter()
api_router.include_router(access.router)
api_router.include_router(content.router)
api_router.include_router(admin.auth_router)
api_router.include_router(admin.router)
