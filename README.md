# SALON BOARD Style Poster

SALON BOARDへのスタイル投稿を自動化するWebアプリケーション

## 概要

このアプリケーションは、美容サロンのスタイリストがSALON BOARDにスタイルを一括投稿するための自動化システムです。Excel/CSVファイルと画像ファイルをアップロードすることで、Playwright（ブラウザ自動化）を使用して複数のスタイルを自動的に投稿できます。

### 主な機能

- **ユーザー管理**: 管理者による一般ユーザーの作成・管理
- **SALON BOARD設定管理**: ユーザーごとのSALON BOARDログイン情報管理（パスワード暗号化）
- **バッチ投稿**: Excel/CSVファイルと画像をアップロードして一括投稿
- **進捗管理**: リアルタイムで投稿進捗を表示
- **エラーレポート**: 投稿失敗時の詳細なエラー情報とスクリーンショット保存
- **タスク中止**: 実行中のタスクを安全に中止可能

## 技術スタック

### バックエンド
- **Python 3.11+**
- **FastAPI**: REST APIフレームワーク
- **SQLAlchemy**: ORM
- **PostgreSQL 15+**: データベース
- **Celery**: 非同期タスクキュー
- **Redis**: Celeryブローカー/バックエンド
- **Playwright**: ブラウザ自動化
- **Alembic**: データベースマイグレーション

### セキュリティ
- **JWT (python-jose)**: API認証
- **bcrypt (passlib)**: パスワードハッシュ化
- **Fernet (cryptography)**: SALON BOARDパスワード暗号化

### フロントエンド
- **Jinja2**: テンプレートエンジン
- **HTML5/CSS3/JavaScript**: UI実装

### インフラ
- **Docker & Docker Compose**: コンテナ化
- **Nginx**: リバースプロキシ、静的ファイル配信

## アーキテクチャ

```
┌─────────────┐
│   Nginx     │  (リバースプロキシ、静的ファイル配信)
└──────┬──────┘
       │
┌──────┴──────┐
│   FastAPI   │  (Web API)
│  (Uvicorn)  │
└──────┬──────┘
       │
┌──────┴──────┬──────────────┬────────────┐
│  PostgreSQL │    Redis     │   Celery   │
│     (DB)    │  (Broker)    │  Worker    │
└─────────────┴──────────────┴────────────┘
```

## セットアップ

### 必要な環境

- Docker & Docker Compose
- Git

### インストール手順

#### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd salon-style-poster
```

#### 2. 環境変数の設定

`.env.example`をコピーして`.env`ファイルを作成し、環境変数を設定します。

```bash
cp .env.example .env
```

`.env`ファイルの内容（例）:

```env
# PostgreSQL設定
POSTGRES_USER=salonuser
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=salon_board_db

# Redis設定
REDIS_PASSWORD=your_redis_password_here

# JWT設定
SECRET_KEY=your_super_secret_key_here_change_this_in_production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 暗号化設定（Fernet Key）
ENCRYPTION_KEY=your_fernet_encryption_key_here

# アプリケーション設定
APP_NAME=SALON BOARD Style Poster
APP_VERSION=1.0.0
```

**重要**: `SECRET_KEY`と`ENCRYPTION_KEY`は必ず変更してください。

#### Fernet Keyの生成方法

```python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### 3. Dockerコンテナの起動

```bash
docker-compose up -d
```

初回起動時は、イメージのビルドに数分かかる場合があります。

#### 4. データベースの初期化

```bash
docker-compose exec web python scripts/init_db.py
```

このコマンドでAlembicマイグレーションが実行され、データベーステーブルが作成されます。

#### 5. 管理者アカウントの作成

```bash
docker-compose exec web python scripts/create_admin.py \
  --email admin@example.com \
  --password your_admin_password
```

### アクセス

- **Webアプリケーション**: http://localhost
- **API ドキュメント**: http://localhost/api/v1/docs

## 使い方

### 1. ログイン

管理者アカウントでログインします。

### 2. SALON BOARD設定の登録

「設定」ページから、SALON BOARDのログイン情報を登録します。

- 設定名（識別用）
- SALON BOARD ユーザーID（メールアドレス）
- SALON BOARD パスワード（暗号化されて保存）
- サロンID・サロン名（複数サロン管理時に使用、任意）

### 3. スタイルデータの準備

#### CSVまたはExcelファイルの作成

以下のカラムを含むCSVまたはExcelファイルを作成します:

| カラム名 | 必須 | 説明 |
|---------|------|------|
| 画像名 | ○ | アップロードする画像ファイル名 |
| スタイル名 | ○ | スタイルのタイトル |
| スタイル説明 | ○ | スタイルの詳細説明 |
| カテゴリ | ○ | カテゴリ名（例: カット、カラー、パーマ） |
| クーポン | × | 関連クーポン名（任意） |
| ハッシュタグ | × | カンマ区切りのハッシュタグ（任意） |

#### 画像ファイルの準備

CSV/Excelファイルの「画像名」カラムに記載したファイル名と一致する画像ファイルを準備します。

### 4. タスクの実行

「タスク実行」ページで以下の操作を行います:

1. SALON BOARD設定を選択
2. スタイル情報ファイル（CSV/Excel）をアップロード
3. 画像ファイルを複数選択してアップロード
4. 「タスクを開始」ボタンをクリック

### 5. 進捗確認

タスク実行中は、リアルタイムで進捗バーが更新されます。

- 完了件数 / 総件数
- 進捗率
- ステータス（処理中、中止中、成功、失敗）

### 6. エラーレポート

タスク完了後、エラーが発生した場合は「エラーレポート」セクションに詳細が表示されます。

- 行番号
- スタイル名
- エラー項目
- エラー理由
- スクリーンショット（該当する場合）

## Docker Composeコマンド

### コンテナの起動

```bash
docker-compose up -d
```

### コンテナの停止

```bash
docker-compose down
```

### ログの確認

```bash
# すべてのコンテナのログ
docker-compose logs -f

# 特定のコンテナのログ
docker-compose logs -f web
docker-compose logs -f worker
```

### コンテナの再起動

```bash
docker-compose restart
```

### データベースのバックアップ

```bash
docker-compose exec db pg_dump -U salonuser salon_board_db > backup.sql
```

### データベースのリストア

```bash
cat backup.sql | docker-compose exec -T db psql -U salonuser salon_board_db
```

## 開発

### ローカル開発環境のセットアップ

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# Playwrightブラウザのインストール
playwright install firefox
```

### データベースマイグレーションの作成

```bash
# 新しいマイグレーションファイルを生成
alembic revision --autogenerate -m "Description of changes"

# マイグレーションを適用
alembic upgrade head

# マイグレーションを1つ戻す
alembic downgrade -1
```

### テストの実行

```bash
pytest tests/
```

## トラブルシューティング

### データベース接続エラー

**症状**: `Database connection failed`

**解決策**:
1. PostgreSQLコンテナが起動しているか確認: `docker-compose ps`
2. `.env`ファイルの`POSTGRES_*`設定を確認
3. コンテナを再起動: `docker-compose restart db web`

### Celeryワーカーがタスクを処理しない

**症状**: タスクが「処理中」のまま進まない

**解決策**:
1. Workerコンテナのログを確認: `docker-compose logs -f worker`
2. Redisコンテナが起動しているか確認: `docker-compose ps`
3. Workerコンテナを再起動: `docker-compose restart worker`

### Playwrightがブラウザを起動できない

**症状**: `Browser executable not found`

**解決策**:
1. Dockerコンテナを再ビルド: `docker-compose build worker`
2. Playwrightがインストールされているか確認: `docker-compose exec worker playwright --version`

### 画像アップロードエラー

**症状**: `Missing image files: xxx.jpg`

**解決策**:
1. CSV/Excelファイルの「画像名」とアップロードした画像ファイル名が完全に一致しているか確認
2. ファイル名の大文字・小文字も区別されます
3. 拡張子も含めて正確に記載してください

### ログイン後すぐにログアウトされる

**症状**: ログインしてもすぐにログインページに戻る

**解決策**:
1. ブラウザのローカルストレージをクリア
2. `.env`の`SECRET_KEY`が正しく設定されているか確認
3. サーバー時刻が正しいか確認（JWTトークンの有効期限に影響）

## セキュリティ

### パスワード管理

- ユーザーパスワード: bcryptでハッシュ化して保存
- SALON BOARDパスワード: Fernetで暗号化して保存

### 認証

- JWT (JSON Web Token) によるステートレス認証
- トークン有効期限: デフォルト24時間（設定可能）

### HTTPS/SSL

本番環境では必ずHTTPS通信を使用してください。Nginx設定でSSL証明書を設定できます。

## ライセンス

このプロジェクトは[ライセンス名]の下でライセンスされています。

## サポート

問題が発生した場合は、GitHubのIssuesページで報告してください。

## 作者

[作者名]

## 更新履歴

### v1.0.0 (2024-10-24)
- 初回リリース
- 基本機能実装
  - ユーザー管理
  - SALON BOARD設定管理
  - バッチ投稿機能
  - 進捗管理
  - エラーレポート
