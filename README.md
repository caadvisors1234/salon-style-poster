# SALON BOARD Style Poster

## 1. 概要

このアプリケーションは、美容室スタッフが日常的に行っている「SALON BOARD」へのスタイル情報の投稿作業を自動化するためのWebアプリケーションです。
スタイル情報が記載されたファイルと画像ファイルをアップロードするだけで、一連の投稿プロセスをバックグラウンドで実行し、手作業による単純作業の時間を大幅に削減します。

### 主な機能

- **ユーザー管理機能（管理者用）**: 管理者による一般ユーザーアカウントの作成・削除。
- **SALON BOARD設定管理**: ユーザーごとに複数のSALON BOARDアカウント情報を暗号化して安全に保存。
- **スタイル投稿の自動化**: CSV/Excelファイルと画像ファイルをアップロードするだけで、Playwrightを利用してバックグラウンドで自動投稿。
- **リアルタイム進捗確認**: 非同期タスクの進捗状況をUI上でリアルタイムに確認可能。
- **エラーレポート**: 投稿に失敗した項目は、原因とスクリーンショット付きのレポートで確認可能。
- **モバイルファーストUI**: スマートフォンでの操作に最適化されたレスポンシブデザイン。

## 2. 技術スタック

- **バックエンド**: Python 3.11, FastAPI, Uvicorn
- **フロントエンド**: Jinja2, HTML5, CSS3, JavaScript
- **データベース**: PostgreSQL 15+
- **タスクキュー**: Celery, Redis
- **ブラウザ自動化**: Playwright for Python
- **コンテナ化**: Docker, Docker Compose
- **認証**: JWT (python-jose)
- **その他**: SQLAlchemy, Pydantic, Alembic, Pandas

## 3. セットアップと実行手順

### ステップ1: 環境変数の設定

プロジェクトのルートディレクトリにある `.env.example` ファイルをコピーして `.env` ファイルを作成します。

```bash
cp .env.example .env
```

その後、`.env` ファイルをエディタで開き、必要に応じて各変数を設定してください。特に `SECRET_KEY` と `ENCRYPTION_KEY` は必ずユニークで安全な値に変更してください。

`ENCRYPTION_KEY` は以下のPythonコードで生成できます。
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())
```

### ステップ2: Dockerコンテナのビルドと起動

以下のコマンドを実行して、Dockerイメージをビルドし、バックグラウンドでコンテナを起動します。

```bash
docker-compose up --build -d
```

### ステップ3: データベースマイグレーション

コンテナが起動したら、別のターミナルで以下のコマンドを実行して、データベースのテーブルを作成・更新します。

```bash
docker-compose exec web alembic upgrade head
```

### ステップ4: 初回管理者アカウントの作成

以下のコマンドを実行して、最初の管理者アカウントを作成します。`admin@example.com` と `your_strong_password` は任意の値に変更してください。

```bash
docker-compose exec web python -m scripts.create_admin --email admin@example.com --password your_strong_password
```

### ステップ5: アプリケーションへのアクセス

ブラウザで以下のURLにアクセスします。

- **URL**: `http://localhost:8080`

ステップ4で作成した管理者アカウント情報でログインしてください。

## 4. ディレクトリ構造

```
.                           # プロジェクトルート
├── app/                    # FastAPI/Celeryアプリケーションのソースコード
│   ├── api/                # APIエンドポイントのルーター
│   ├── core/               # 設定、セキュリティ、Celery設定などのコア機能
│   ├── crud/               # データベース操作（CRUD）
│   ├── db/                 # データベースセッション管理
│   ├── models/             # SQLAlchemyのモデル（テーブル定義）
│   ├── schemas/            # Pydanticのスキーマ（データ検証）
│   ├── services/           # Playwrightの実行ロジックやCeleryタスク
│   ├── static/             # CSS, JS, 画像ファイル
│   └── templates/          # Jinja2テンプレート
├── docs/                   # 各種設計書
├── scripts/                # 運用スクリプト（管理者作成など）
├── tests/                  # APIテストコード
├── .env.example            # 環境変数テンプレート
├── alembic.ini             # Alembic設定ファイル
├── docker-compose.yml      # Docker Compose設定ファイル
├── Dockerfile              # Web/Worker共通のDockerfile
└── README.md               # このファイル
```

## 5. テストの実行

本プロジェクトには、APIの動作を保証するための統合テストが含まれています。

### 全てのテストを実行

以下のコマンドで、`tests/` ディレクトリ配下の全てのテストを実行します。

```bash
docker-compose exec web pytest
```

### 特定のテストファイルを実行

特定のファイルのみをテストする場合は、以下のようにパスを指定します。

```bash
docker-compose exec web pytest tests/api/v1/test_auth.py
```