# SALON BOARD Style Poster - アーキテクチャドキュメント

## 目次

1. [システム概要](#システム概要)
2. [技術スタック](#技術スタック)
3. [アーキテクチャ図](#アーキテクチャ図)
4. [コンポーネント構成](#コンポーネント構成)
5. [データフロー](#データフロー)
6. [セキュリティ](#セキュリティ)
7. [デプロイメント](#デプロイメント)
8. [トラブルシューティング](#トラブルシューティング)

---

## システム概要

SALON BOARD Style Posterは、美容サロン向けのスタイル投稿自動化Webアプリケーションです。Excel/CSVファイルと画像ファイルをアップロードするだけで、Playwright（ブラウザ自動化）を使用して複数のスタイルをSALON BOARDへ自動的に投稿できます。

### 主要機能

1. **ユーザー管理**: 管理者による一般ユーザーの作成・管理
2. **SALON BOARD設定管理**: ユーザーごとのログイン情報管理（パスワード暗号化）
3. **バッチ投稿**: Excel/CSVと画像の一括投稿
4. **進捗管理**: リアルタイムで投稿進捗を表示
5. **エラーレポート**: 投稿失敗時の詳細情報とスクリーンショット
6. **タスク中止**: 実行中タスクの安全な中止

---

## 技術スタック

### バックエンド

- **Python 3.11+**: メインプログラミング言語
- **FastAPI**: 高速なWebフレームワーク
- **Uvicorn**: ASGIサーバー
- **Pydantic**: データバリデーション
- **SQLAlchemy**: ORM（Object-Relational Mapping）
- **Alembic**: データベースマイグレーション
- **Pandas**: データ処理（CSV/Excel読み込み）

### 非同期処理

- **Celery**: 分散タスクキュー
- **Redis**: メッセージブローカー・結果バックエンド

### ブラウザ自動化

- **Playwright**: ブラウザ自動化ライブラリ
- **Firefox**: 自動化対象ブラウザ

### セキュリティ

- **python-jose**: JWT認証
- **passlib (bcrypt)**: パスワードハッシュ化
- **cryptography (Fernet)**: 対称鍵暗号化

### データベース

- **PostgreSQL 15+**: リレーショナルデータベース

### フロントエンド

- **Jinja2**: サーバーサイドテンプレートエンジン
- **HTML5/CSS3/JavaScript**: UI実装
- **Fetch API**: 非同期通信

### インフラストラクチャ

- **Docker**: コンテナ化
- **Docker Compose**: マルチコンテナ管理
- **Nginx**: リバースプロキシ・静的ファイル配信

---

## アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────┐
│                          ユーザー                            │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (443)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      Nginx Container                          │
│  - リバースプロキシ                                           │
│  - 静的ファイル配信 (/static/*)                              │
│  - SSL/TLS終端                                                │
└───────────┬──────────────────────────────────┬───────────────┘
            │                                  │
            │ :8000                            │ Static Files
            ▼                                  │
┌──────────────────────────────────┐           │
│      Web Container (FastAPI)     │◄──────────┘
│  - REST API                      │
│  - HTML レンダリング             │
│  - 認証・認可                    │
│  - ファイルアップロード処理      │
└────┬──────────────────────┬──────┘
     │                      │
     │                      │ タスク登録
     │                      ▼
     │              ┌──────────────────┐
     │              │  Redis Container │
     │              │  - タスクキュー  │
     │              │  - 結果ストア    │
     │              └──────┬───────────┘
     │                     │ タスク取得
     │                     ▼
     │              ┌──────────────────────────┐
     │              │  Worker Container        │
     │              │  - Celery Worker         │
     │              │  - Playwright実行        │
     │              │  - Firefox起動           │
     │              │  - SALON BOARD操作       │
     │              └──────┬───────────────────┘
     │                     │
     │ データベース接続    │ データベース接続
     ▼                     ▼
┌───────────────────────────────────┐
│    PostgreSQL Container           │
│  - ユーザー情報                   │
│  - SALON BOARD設定                │
│  - タスク情報                     │
└───────────────────────────────────┘
```

---

## コンポーネント構成

### 1. Nginx Container

**役割**: リバースプロキシ、静的ファイル配信、SSL/TLS終端

**設定**:
```nginx
location / {
    proxy_pass http://web:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /static/ {
    alias /app/app/static/;
}
```

### 2. Web Container (FastAPI)

**役割**: REST API提供、HTML描画、認証・認可

**主要エンドポイント**:

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `/api/v1/auth/token` | POST | JWT トークン取得 |
| `/api/v1/auth/me` | GET | 現在のユーザー情報取得 |
| `/api/v1/users/*` | * | ユーザー管理（管理者専用） |
| `/api/v1/sb-settings/*` | * | SALON BOARD設定管理 |
| `/api/v1/tasks/start` | POST | タスク開始 |
| `/api/v1/tasks/status` | GET | タスク状態取得 |
| `/api/v1/tasks/cancel` | POST | タスク中止 |

**ディレクトリ構造**:
```
app/
├── api/v1/endpoints/     # APIエンドポイント
├── core/                 # コア機能（設定、セキュリティ、Celery）
├── models/               # SQLAlchemyモデル
├── schemas/              # Pydanticスキーマ
├── crud/                 # データベース操作
├── services/             # ビジネスロジック
├── static/               # 静的ファイル
├── templates/            # Jinja2テンプレート
└── selectors.yaml        # Playwrightセレクタ設定
```

### 3. Worker Container (Celery)

**役割**: バックグラウンドタスク実行、Playwright自動化

**主要タスク**:
- `process_style_post_task`: スタイル投稿処理

**処理フロー**:
1. Redisからタスクを取得
2. データベースからSALON BOARD設定を取得
3. Playwrightでブラウザを起動
4. SALON BOARDにログイン
5. スタイルデータをループ処理で投稿
6. 進捗をデータベースに記録
7. エラー時はスクリーンショットを保存

**重要な設定**:
```yaml
# docker-compose.yml
worker:
  platform: linux/amd64  # ARM64環境での必須設定
```

### 4. Redis Container

**役割**: タスクキュー、結果バックエンド

**使用目的**:
- Celeryのタスクキュー（broker）
- タスク結果の一時保存（backend）

### 5. PostgreSQL Container

**役割**: 永続データストレージ

**テーブル構成**:

#### `users`
| カラム | 型 | 説明 |
|---|---|---|
| id | Integer | 主キー |
| email | String | メールアドレス（UNIQUE） |
| hashed_password | String | ハッシュ化パスワード |
| role | String | ロール（admin/user） |
| created_at | DateTime | 作成日時 |

#### `salon_board_settings`
| カラム | 型 | 説明 |
|---|---|---|
| id | Integer | 主キー |
| user_id | Integer | ユーザーID（FK） |
| sb_user_id | String | SALON BOARDユーザーID |
| encrypted_sb_password | String | 暗号化SALON BOARDパスワード |
| salon_id | String | サロンID（複数店舗用） |
| salon_name | String | サロン名（複数店舗用） |

#### `current_tasks`
| カラム | 型 | 説明 |
|---|---|---|
| id | UUID | 主キー |
| user_id | Integer | ユーザーID（FK, UNIQUE） |
| status | String | ステータス（PROCESSING/SUCCESS/FAILURE） |
| progress | Integer | 進捗（完了件数） |
| total | Integer | 総件数 |
| errors | JSONB | エラーリスト |

---

## データフロー

### 1. ユーザー登録・ログイン

```
1. 管理者がユーザーを作成
   POST /api/v1/users/
   ├─ パスワードをbcryptでハッシュ化
   └─ データベースに保存

2. ユーザーがログイン
   POST /api/v1/auth/token
   ├─ パスワード検証
   ├─ JWTトークン生成
   └─ トークンをクライアントに返却

3. 以降のリクエスト
   Authorization: Bearer {token}
   ├─ トークン検証
   └─ ユーザー情報取得
```

### 2. SALON BOARD設定登録

```
1. ユーザーがSALON BOARD設定を登録
   POST /api/v1/sb-settings/
   ├─ パスワードをFernet暗号化
   └─ データベースに保存

2. 設定取得
   GET /api/v1/sb-settings/
   ├─ データベースから取得
   └─ パスワードは暗号化のまま返却
```

### 3. スタイル投稿タスク

```
1. ユーザーがファイルをアップロード
   POST /api/v1/tasks/start
   ├─ multipart/form-data でファイル受信
   ├─ uploads/{task_id}/ に保存
   │  ├─ styles_data.csv
   │  └─ images/
   │     ├─ style1.jpg
   │     └─ style2.jpg
   ├─ データベースにタスクレコード作成
   └─ Celeryタスクを登録

2. Workerがタスクを処理
   process_style_post_task.delay()
   ├─ SALON BOARD設定を取得
   ├─ パスワードを復号化
   ├─ Playwrightでブラウザ起動
   ├─ SALON BOARDにログイン
   ├─ スタイルデータをループ処理
   │  ├─ 進捗コールバック（中止チェック）
   │  ├─ 画像アップロード
   │  ├─ フォーム入力
   │  ├─ 登録
   │  └─ エラー時はスクリーンショット保存
   ├─ 完了ステータスに更新
   └─ アップロードファイルを削除

3. クライアントが進捗を取得
   GET /api/v1/tasks/status
   ├─ データベースから状態取得
   └─ JSON形式で返却
      {
        "status": "PROCESSING",
        "progress": 5,
        "total": 10,
        "errors": [...]
      }

4. ユーザーがタスクを中止（オプション）
   POST /api/v1/tasks/cancel
   ├─ Celery経由で強制終了
   │  celery_app.control.revoke(task_id, terminate=True)
   └─ ステータスをFAILUREに更新
```

---

## セキュリティ

### 1. 認証・認可

**JWT認証**:
```python
# トークン生成
access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
access_token = create_access_token(
    data={"sub": user.email}, expires_delta=access_token_expires
)

# トークン検証
payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
email = payload.get("sub")
```

**ロールベースアクセス制御**:
- **管理者（admin）**: すべてのユーザー管理が可能
- **一般ユーザー（user）**: 自分のリソースのみアクセス可能

### 2. パスワード管理

**ハッシュ化（bcrypt）**:
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ハッシュ化
hashed_password = pwd_context.hash(plain_password)

# 検証
pwd_context.verify(plain_password, hashed_password)
```

**暗号化（Fernet）**:
```python
from cryptography.fernet import Fernet

# 暗号化
f = Fernet(ENCRYPTION_KEY)
encrypted = f.encrypt(plain_password.encode())

# 復号化
decrypted = f.decrypt(encrypted).decode()
```

### 3. セキュリティヘッダー

Nginxで以下のヘッダーを設定：
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
```

### 4. リソース分離

- ユーザー単位のシングルタスク実行制限
- 各ユーザーは自分のリソースのみアクセス可能
- SALON BOARD設定は暗号化して保存

---

## デプロイメント

### 1. 環境構築

**必要な環境変数（.env）**:
```bash
# データベース
POSTGRES_USER=salonboard
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=salonboard_poster

# セキュリティ
SECRET_KEY=your_secret_key_here
ENCRYPTION_KEY=your_fernet_key_here

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

### 2. ビルド＆起動

```bash
# イメージビルド
docker-compose build

# コンテナ起動
docker-compose up -d

# ログ確認
docker-compose logs -f web
docker-compose logs -f worker

# データベースマイグレーション
docker-compose exec web alembic upgrade head

# 初期管理者作成
docker-compose exec web python -c "
from app.db.session import SessionLocal
from app.crud.user import create_user
from app.core.security import get_password_hash
from app.schemas.user import UserCreate

db = SessionLocal()
user = create_user(db, UserCreate(
    email='admin@example.com',
    password='admin',
    role='admin'
))
db.close()
"
```

### 3. スケーリング

**Workerの増設**:
```bash
docker-compose up -d --scale worker=3
```

**負荷分散**:
- Nginxで複数のWebコンテナにロードバランス
- Celeryで複数のWorkerに分散処理

---

## トラブルシューティング

### 1. ARM64環境でFirefoxがハングする

**症状**: Workerログで「ブラウザを起動中...」から進まない

**原因**: ARM64アーキテクチャでのFirefox互換性問題

**解決策**:
```yaml
# docker-compose.yml
worker:
  platform: linux/amd64
```

```dockerfile
# Dockerfile
FROM --platform=linux/amd64 python:3.11-slim
```

### 2. タスクが中止されない

**症状**: 中止ボタンを押してもタスクが継続する

**原因**: 進捗コールバックがtry-except内で呼ばれている

**解決策**: 進捗コールバックをtry-exceptの外で呼び出す
```python
# 正しい実装
if self.progress_callback:
    self.progress_callback(index, len(df))  # try-exceptの外

try:
    # スタイル処理
    self.step_process_single_style(...)
except Exception as e:
    # エラーハンドリング
```

### 3. 画像アップロードでタイムアウト

**症状**: 「送信ボタンのアクティブ化待機中...」でタイムアウト

**原因**: `.isActive` クラスが付与されない

**解決策**:
```python
# NG（タイムアウトする）
self.page.wait_for_selector(
    form_config["image"]["submit_button_active"]
)

# OK（直接クリック）
time.sleep(2)
self.page.locator("input.imageUploaderModalSubmitButton").click()
```

### 4. データベース接続エラー

**症状**: `connection refused` エラー

**診断**:
```bash
# PostgreSQLコンテナの状態確認
docker-compose ps db

# 接続テスト
docker-compose exec web python -c "
from app.db.session import SessionLocal
db = SessionLocal()
print('DB接続成功')
db.close()
"
```

### 5. Celeryタスクが実行されない

**症状**: タスクがPENDING状態のまま

**診断**:
```bash
# Workerの状態確認
docker-compose logs worker

# Redisの状態確認
docker-compose exec redis redis-cli ping

# タスク登録確認
docker-compose exec redis redis-cli LLEN celery
```

---

## パフォーマンス最適化

### 1. データベース

- インデックス設定済み（user_id, emailなど）
- コネクションプーリング有効

### 2. ブラウザ自動化

- ヘッドレスモード使用
- 画像最適化推奨（処理時間短縮）

### 3. ファイルアップロード

- アップロード完了後に自動削除
- スクリーンショットの定期クリーンアップ推奨

---

## 監視・ログ

### ログ出力先

- **Web**: `docker-compose logs web`
- **Worker**: `docker-compose logs worker`
- **Nginx**: `docker-compose logs nginx`

### 重要なログメッセージ

```bash
# タスク開始
=== タスク開始: {task_id} ===

# 進捗
--- スタイル 1/2 処理中 ---
✓ スタイル登録完了: {スタイル名}

# エラー
✗ エラー発生: {エラーメッセージ}
✓ スクリーンショット保存: {パス}

# タスク完了
=== タスク完了: {task_id} ===
```

---

## 今後の拡張性

### 考慮事項

1. **マルチテナント対応**: 組織単位での管理
2. **スケジュール投稿**: 指定時刻での自動投稿
3. **テンプレート機能**: よく使うスタイルのテンプレート化
4. **ダッシュボード**: 投稿統計の可視化
5. **Webhook通知**: タスク完了時の通知
