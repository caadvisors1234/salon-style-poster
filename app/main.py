"""
FastAPIアプリケーションのエントリーポイント
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.api.v1.api import api_router

# FastAPIアプリケーション初期化
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)

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
    """ルートエンドポイント - ログインページへリダイレクト"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/main")
async def main_page(request: Request):
    """メインページ（タスク実行）"""
    return templates.TemplateResponse("main/index.html", {"request": request})


@app.get("/settings")
async def settings_page(request: Request):
    """設定ページ"""
    return templates.TemplateResponse("settings/index.html", {"request": request})


@app.get("/admin/users")
async def admin_users_page(request: Request):
    """ユーザー管理ページ（管理者専用）"""
    return templates.TemplateResponse("admin/users.html", {"request": request})


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}
