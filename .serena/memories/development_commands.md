# 開発コマンド

## 環境セットアップ
```bash
# 仮想環境の作成とアクティベート
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# 依存関係のインストール
pip install -r requirements.txt

# Playwrightブラウザのインストール
playwright install firefox
```

## Docker環境
```bash
# 全コンテナ起動
docker-compose up -d

# 特定のコンテナ起動
docker-compose up -d db redis

# ログ確認
docker-compose logs -f web
docker-compose logs -f worker

# コンテナ停止
docker-compose down
```

## データベース操作
```bash
# マイグレーション作成
alembic revision --autogenerate -m "Description of changes"

# マイグレーション実行
alembic upgrade head

# マイグレーション戻し
alembic downgrade -1

# 初回管理者作成
docker-compose exec web python scripts/create_admin.py \
  --email admin@example.com \
  --password your_admin_password
```

## 開発サーバー起動
```bash
# FastAPI開発サーバー
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celeryワーカー
celery -A app.worker worker --loglevel=info
```

## テスト実行
```bash
# ユニットテスト
pytest tests/

# 特定のテストファイル
pytest tests/test_api.py

# カバレッジ付きテスト
pytest --cov=app tests/
```

## コード品質
```bash
# リンター（flake8）
flake8 app/

# フォーマッター（black）
black app/

# 型チェック（mypy）
mypy app/
```