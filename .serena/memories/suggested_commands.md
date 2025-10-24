# 推奨コマンド集

## 開発環境セットアップ
```bash
# 仮想環境作成・アクティベート
python -m venv .venv
source .venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt

# Playwrightブラウザインストール
playwright install firefox
```

## Docker環境操作
```bash
# 全コンテナ起動
docker-compose up -d

# 特定サービス起動
docker-compose up -d db redis

# ログ確認
docker-compose logs -f web
docker-compose logs -f worker

# コンテナ停止
docker-compose down

# コンテナ再起動
docker-compose restart
```

## データベース操作
```bash
# マイグレーション作成
alembic revision --autogenerate -m "Description"

# マイグレーション実行
alembic upgrade head

# マイグレーション戻し
alembic downgrade -1

# 管理者作成
docker-compose exec web python scripts/create_admin.py \
  --email admin@example.com --password your_password
```

## 開発サーバー
```bash
# FastAPI開発サーバー
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celeryワーカー
celery -A app.worker worker --loglevel=info

# 両方同時起動（別ターミナル）
# ターミナル1: uvicorn app.main:app --reload
# ターミナル2: celery -A app.worker worker --loglevel=info
```

## テスト・品質管理
```bash
# テスト実行
pytest tests/

# カバレッジ付きテスト
pytest --cov=app tests/

# リンター
flake8 app/

# フォーマッター
black app/

# 型チェック
mypy app/
```

## ファイル操作
```bash
# ファイル検索
find . -name "*.py" -type f
grep -r "pattern" app/

# ディレクトリ構造確認
tree app/ -I "__pycache__"

# ファイル権限確認
ls -la app/
```

## Git操作
```bash
# ステータス確認
git status

# 変更をステージング
git add .

# コミット
git commit -m "feat: add new feature"

# プッシュ
git push origin main

# ブランチ作成
git checkout -b feature/new-feature
```

## ログ・デバッグ
```bash
# アプリケーションログ確認
docker-compose logs -f web

# ワーカーログ確認
docker-compose logs -f worker

# データベースログ確認
docker-compose logs -f db

# コンテナ内でコマンド実行
docker-compose exec web bash
docker-compose exec db psql -U salon_board_user -d salon_board_db
```