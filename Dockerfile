# Python 3.11ベースイメージ (AMD64アーキテクチャを明示指定)
FROM --platform=linux/amd64 python:3.11-slim

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージ更新と必要なパッケージインストール
# Playwright Firefox依存関係を含む
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcb-shm0 \
    libxext6 \
    libxrandr2 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libgtk-3-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libasound2 \
    libxrender1 \
    libfreetype6 \
    libfontconfig1 \
    libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwrightブラウザインストール（Firefox）
RUN playwright install firefox

# アプリケーションコードをコピー
COPY . .

# ポート公開（FastAPI用）
EXPOSE 8000

# デフォルトコマンド（docker-compose.ymlで上書き）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
