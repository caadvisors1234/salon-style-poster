"""
FastAPIアプリケーションのエントリーポイント
"""
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.db.session import engine
from app.api.v1.api import api_router
from app.core.security import get_current_user
from app.schemas.user import User

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
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # データベース接続確認
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    print(f"Shutting down {settings.APP_NAME}")


@app.get("/")
async def root(request: Request):
    """ルートエンドポイント - ログインページを表示"""
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@app.get("/main")
async def main_page(request: Request, current_user: User = Depends(get_current_user)):
    """メインページ（タスク実行）"""
    return templates.TemplateResponse("main/index.html", {"request": request, "user": current_user})


@app.get("/settings")
async def settings_page(request: Request, current_user: User = Depends(get_current_user)):
    """設定ページ"""
    return templates.TemplateResponse("settings/index.html", {"request": request, "user": current_user})


@app.get("/admin/users")
async def admin_users_page(request: Request, current_user: User = Depends(get_current_user)):
    """ユーザー管理ページ（管理者専用）"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return templates.TemplateResponse("admin/users.html", {"request": request, "user": current_user})


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}
