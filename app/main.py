"""
FastAPIアプリケーションのエントリーポイント
"""
import logging

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from sqlalchemy import text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.session import engine
from app.api.v1.api import api_router
from app.core.security import get_current_user
from app.schemas.user import User

# ロギング初期化
setup_logging("web")
logger = logging.getLogger(__name__)

# レート制限初期化
limiter = Limiter(key_func=get_remote_address)

# FastAPIアプリケーション初期化
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)

# レート制限を有効化
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS設定
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 静的ファイルマウント
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2テンプレート設定
templates = Jinja2Templates(directory="app/templates")

# APIルーター登録
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # データベース接続確認
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception as e:
        logger.exception("Database connection failed: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    logger.info("Shutting down %s", settings.APP_NAME)


@app.get("/")
async def root(request: Request):
    """ルートエンドポイント - ログインページを表示"""
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@app.get("/login")
async def login_page(request: Request):
    """ログインページ"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/main")
async def main_page(request: Request):
    """メインページ（タスク実行）- クライアントサイドで認証チェック"""
    return templates.TemplateResponse("main/index.html", {"request": request, "active_page": "main"})


@app.get("/settings")
async def settings_page(request: Request):
    """設定ページ - クライアントサイドで認証チェック"""
    return templates.TemplateResponse("settings/index.html", {"request": request, "active_page": "settings"})


@app.get("/admin/users")
async def admin_users_page(request: Request):
    """ユーザー管理ページ（管理者専用）- クライアントサイドで認証チェック"""
    return templates.TemplateResponse("admin/users.html", {"request": request, "active_page": "admin"})


@app.get("/unpublish")
async def unpublish_page(request: Request):
    """スタイル非掲載ページ"""
    return templates.TemplateResponse("unpublish/index.html", {"request": request, "active_page": "unpublish"})


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """ブラウザがデフォルトで参照する favicon パスに対応"""
    return FileResponse("app/static/favicon.ico")
