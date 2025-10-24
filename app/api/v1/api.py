"""
API v1ルーター統合
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, sb_settings, tasks

api_router = APIRouter()

# 各エンドポイントを統合
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(sb_settings.router, prefix="/sb-settings", tags=["SALON BOARD Settings"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
