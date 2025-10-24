# Python 3.11ベースイメージ
FROM python:3.11-slim

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージ更新と必要なパッケージインストール
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwrightブラウザインストール（Firefox）
RUN playwright install firefox
RUN playwright install-deps firefox

# アプリケーションコードをコピー
COPY . .

# ポート公開（FastAPI用）
EXPOSE 8000

# デフォルトコマンド（docker-compose.ymlで上書き）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
