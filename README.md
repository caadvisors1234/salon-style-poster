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
- **フロントエンド**: Jinja2, HTML5, CSS3, JavaScript（モバイルファーストデザイン）
- **データベース**: PostgreSQL 15+
- **タスクキュー**: Celery, Redis
- **ブラウザ自動化**: Playwright for Python（Firefox headless）
- **コンテナ化**: Docker, Docker Compose（AMD64プラットフォーム指定）
- **認証**: JWT (python-jose)
- **暗号化**: Fernet (cryptography)、bcrypt (passlib)
- **その他**: SQLAlchemy, Pydantic, Alembic, Pandas

## 3. 重要な技術的考慮事項

### ARM64（Apple Silicon）環境での注意点
このアプリケーションはARM64環境（Apple Silicon Mac等）でも動作しますが、Playwrightブラウザの起動問題を回避するため、Docker設定で`platform: linux/amd64`を指定しています。これによりエミュレーションが発生しますが、ブラウザ起動時間は約2-3秒で正常に動作します。

### 画像アップロード処理の実装
SALON BOARDの画像アップロードモーダルでは、送信ボタンに`.isActive`クラスが付与されるのを待つとタイムアウトが発生するため、画像選択後2秒待機してから直接ボタンをクリックする方式を採用しています。

### タスクキャンセル機能
実行中のタスクは強制終了（SIGKILL）により即座に中止できます。進捗表示画面の「中止」ボタンから実行可能です。

## 4. セットアップと実行手順

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

## 5. ディレクトリ構造

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

## 6. 使用方法

### SALON BOARD設定の登録
1. ログイン後、ヘッダーの「設定」リンクをクリック
2. SALON BOARDのログイン情報を入力して保存（パスワードは暗号化されて保存されます）
3. 複数のSALON BOARDアカウントを登録可能

### スタイル投稿の実行
1. メインページで以下のファイルをアップロード：
   - **スタイルデータファイル**: CSV（UTF-8）またはExcel形式
   - **画像ファイル**: スタイル情報ファイルで指定した画像をすべて選択（複数選択可、ZIPアーカイブは不要）
   > **注意:** 画像ファイル名は、スタイルデータファイルの `画像名` カラムと完全一致している必要があります。
2. 使用するSALON BOARD設定を選択
3. 「投稿開始」ボタンをクリック
4. 進捗状況がリアルタイムで表示されます
5. 完了後、エラーがあった場合はレポートが表示されます

### スタイル非掲載の実行
1. ナビゲーションから「スタイル非掲載」ページに移動
2. SALON BOARD設定を選択
3. HotPepperBeautyのサロンURLを入力し「件数取得」をクリック（スタイル数を自動取得）
4. 非掲載する開始/終了番号を入力し、除外する番号があればカンマ区切りで入力
5. 「非掲載タスクを開始」をクリック。進捗・キャンセル・結果表示は投稿タスクと同様に確認可能です

### タスクの中止
実行中のタスクを中止する場合は、進捗表示画面の「中止」ボタンをクリックしてください。タスクは即座に強制終了されます。

## 7. テストの実行

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

## 8. トラブルシューティング

### ブラウザ起動が遅い（ARM64環境）
**症状**: タスク実行時にブラウザ起動に数分以上かかる、またはタイムアウトする

**原因**: `docker-compose.yml`でプラットフォーム指定が欠けている

**解決策**: `docker-compose.yml`の`web`と`worker`サービスに以下を追加：
```yaml
platform: linux/amd64
```

### 画像アップロードでタイムアウトが発生
**症状**: スタイル投稿時に画像アップロードでタイムアウトエラーが発生

**原因**: 送信ボタンの`.isActive`クラスを待機している古い実装

**解決策**: 最新版のコードでは修正済み。`app/services/style_poster.py`で2秒待機+直接クリック方式を採用

### タスクが中止できない
**症状**: 中止ボタンをクリックしてもタスクが継続する

**原因**: 古いバージョンの中止処理

**解決策**: 最新版では強制終了（SIGKILL）を実装済み。コンテナを再起動してください：
```bash
docker-compose restart web worker
```

### データベース接続エラー
**症状**: アプリケーション起動時にデータベース接続エラーが発生

**解決策**:
```bash
# コンテナ状態確認
docker-compose ps

# PostgreSQLコンテナが起動していない場合
docker-compose up -d db

# データベースログ確認
docker-compose logs db
```

### Celeryワーカーが起動しない
**症状**: タスクが「処理中」のまま進まない

**解決策**:
```bash
# ワーカーログ確認
docker-compose logs worker

# ワーカー再起動
docker-compose restart worker

# Redisの状態確認
docker-compose exec redis redis-cli ping
```

### スクリーンショットディレクトリが肥大化する
**症状**: `app/static/screenshots` の容量が増え続ける

**解決策**:
- Celery Beat が毎日 `cleanup_screenshots` タスクを実行し、既定では「30日より古いファイルの削除」と「合計500MBを超える場合は古い順に削除」を行います。
- 設定値は `.env` の `SCREENSHOT_RETENTION_DAYS` と `SCREENSHOT_DIR_MAX_BYTES` を変更することで調整できます。
- 即時クリーンアップが必要な場合は、`docker-compose exec worker celery -A app.worker call cleanup_screenshots` を手動実行してください。

## 9. 関連ドキュメント

プロジェクトの詳細な技術情報は以下のドキュメントを参照してください：

- **docs/ARCHITECTURE.md**: システムアーキテクチャ、セキュリティ、デプロイ手順
- **docs/playwright_spec.md**: Playwright自動化の技術仕様と実装詳細
- **docs/implementation_plan.md**: 実装計画と進捗状況
- **docs/api_spec.md**: REST API仕様
- **docs/database_design.md**: データベース設計
- **AGENTS.md**: コントリビューター向けガイドライン

## 10. ライセンスとサポート

このプロジェクトは内部使用を目的としています。技術的な質問や問題が発生した場合は、開発チームにお問い合わせください。
