## **SALON BOARDスタイル自動投稿Webアプリケーション 実装計画書**

### **1. プロジェクト概要**

#### **1.1. 目的**
要件定義書と詳細設計書に基づき、SALON BOARDスタイル自動投稿Webアプリケーションの完全実装を行う。

#### **1.2. 技術スタック**
- **バックエンド**: Python 3.11+, FastAPI, Uvicorn
- **データベース**: PostgreSQL 15+
- **タスクキュー**: Celery, Redis
- **ブラウザ自動化**: Playwright for Python
- **フロントエンド**: Jinja2, HTML5, CSS3, JavaScript
- **コンテナ**: Docker, Docker Compose
- **認証**: JWT (python-jose)
- **セキュリティ**: passlib[bcrypt], cryptography (Fernet)

#### **1.3. アーキテクチャ**
- Nginxコンテナ（リバースプロキシ、SSL終端、静的ファイル配信）
- Webコンテナ（FastAPI）
- Workerコンテナ（Celery + Playwright）
- PostgreSQLコンテナ
- Redisコンテナ

---

### **2. 実装タスク一覧**

---

## **フェーズ1: プロジェクト基盤構築**
**優先度: 最高 | 期間: 1-2日**

### **ステップ1.1: プロジェクト構造のセットアップ**

- [x] ディレクトリ構造作成
  ```
  app/
  ├── api/
  │   └── v1/
  │       ├── endpoints/
  │       │   ├── __init__.py
  │       │   ├── auth.py
  │       │   ├── users.py
  │       │   ├── sb_settings.py
  │       │   ├── tasks.py
  │       │   └── pages.py
  │       └── api.py
  ├── core/
  │   ├── __init__.py
  │   ├── config.py
  │   ├── security.py
  │   └── celery_app.py
  ├── crud/
  │   ├── __init__.py
  │   ├── user.py
  │   ├── salon_board_setting.py
  │   └── current_task.py
  ├── db/
  │   ├── __init__.py
  │   └── session.py
  ├── models/
  │   ├── __init__.py
  │   ├── user.py
  │   ├── salon_board_setting.py
  │   └── current_task.py
  ├── schemas/
  │   ├── __init__.py
  │   ├── user.py
  │   ├── salon_board_setting.py
  │   ├── task.py
  │   └── token.py
  ├── services/
  │   ├── __init__.py
  │   ├── style_poster.py
  │   └── tasks.py
  ├── static/
  │   ├── css/
  │   │   └── style.css
  │   ├── js/
  │   │   └── main.js
  │   └── screenshots/
  ├── templates/
  │   ├── base.html
  │   ├── auth/
  │   │   └── login.html
  │   ├── main/
  │   │   └── index.html
  │   ├── settings/
  │   │   └── index.html
  │   └── admin/
  │       └── users.html
  ├── selectors.yaml
  ├── worker.py
  └── main.py
  scripts/
  ├── __init__.py
  └── create_admin.py
  alembic/
  tests/
  nginx/
  └── nginx.conf
  ```

### **ステップ1.2: 依存関係定義**

- [x] `requirements.txt`作成
  - [x] fastapi
  - [x] uvicorn[standard]
  - [x] sqlalchemy
  - [x] psycopg2-binary
  - [x] celery
  - [x] redis
  - [x] playwright
  - [x] python-jose[cryptography]
  - [x] passlib[bcrypt]
  - [x] cryptography
  - [x] pydantic
  - [x] pydantic-settings
  - [x] python-multipart
  - [x] pandas
  - [x] openpyxl
  - [x] jinja2
  - [x] aiofiles
  - [x] alembic
  - [x] pyyaml

### **ステップ1.3: 環境設定ファイル**

- [x] `.env.example`作成（環境変数テンプレート）
  - [x] PostgreSQL設定
  - [x] Redis設定
  - [x] JWT設定
  - [x] 暗号化キー設定
  - [x] アプリケーション設定

- [x] `.gitignore`作成
  - [x] `.env`
  - [x] `__pycache__/`
  - [x] `*.pyc`
  - [x] `.venv/`
  - [x] `venv/`
  - [x] `.pytest_cache/`
  - [x] `*.log`
  - [x] `app/static/screenshots/*.png`
  - [x] `.DS_Store`

### **ステップ1.4: Docker環境構築**

- [x] `Dockerfile`作成（Web/Worker共通）
  - [x] Python 3.11ベースイメージ
  - [x] 依存関係インストール
  - [x] Playwrightブラウザインストール
  - [x] アプリケーションコードコピー
  - [x] 作業ディレクトリ設定

- [x] `docker-compose.yml`作成
  - [x] nginxサービス定義
  - [x] webサービス定義（FastAPI）
  - [x] workerサービス定義（Celery）
  - [x] dbサービス定義（PostgreSQL）
  - [x] redisサービス定義
  - [x] ネットワーク設定
  - [x] ボリューム設定

- [x] Nginx設定ファイル作成
  - [x] `nginx/nginx.conf`
  - [x] リバースプロキシ設定
  - [x] 静的ファイル配信設定
  - [x] アップロードサイズ制限設定

---

## **フェーズ2: コア機能実装**
**優先度: 最高 | 期間: 2-3日**

### **ステップ2.1: データベース層**

- [x] `app/db/session.py`実装
  - [x] データベースURL構築
  - [x] SQLAlchemy Engineとセッション作成
  - [x] get_db依存関数

- [x] `app/models/user.py`実装
  - [x] Userモデル定義
  - [x] カラム定義（id, email, hashed_password, role, created_at）
  - [x] リレーション定義

- [x] `app/models/salon_board_setting.py`実装
  - [x] SalonBoardSettingモデル定義
  - [x] カラム定義（id, user_id, setting_name, sb_user_id, encrypted_sb_password, salon_id, salon_name, created_at, updated_at）
  - [x] 外部キー定義

- [x] `app/models/current_task.py`実装
  - [x] CurrentTaskモデル定義
  - [x] カラム定義（id(UUID), user_id(UNIQUE), status, total_items, completed_items, error_info_json, created_at）
  - [x] 外部キー定義

### **ステップ2.2: セキュリティ層**

- [x] `app/core/config.py`実装
  - [x] Pydantic Settingsでの環境変数読み込み
  - [x] データベース設定
  - [x] JWT設定
  - [x] Celery設定
  - [x] 暗号化キー設定

- [x] `app/core/security.py`実装
  - [x] パスワードハッシュ化関数（bcrypt）
  - [x] パスワード検証関数
  - [x] JWT生成関数
  - [x] JWT検証関数
  - [x] Fernet暗号化関数
  - [x] Fernet復号化関数
  - [x] 現在ユーザー取得関数（依存関数）

### **ステップ2.3: スキーマ層**

- [x] `app/schemas/token.py`実装
  - [x] Token
  - [x] TokenData

- [x] `app/schemas/user.py`実装
  - [x] UserBase
  - [x] UserCreate
  - [x] UserUpdate
  - [x] User
  - [x] UserInDB
  - [x] UserList

- [x] `app/schemas/salon_board_setting.py`実装
  - [x] SalonBoardSettingBase
  - [x] SalonBoardSettingCreate
  - [x] SalonBoardSettingUpdate
  - [x] SalonBoardSetting
  - [x] SalonBoardSettingList

- [x] `app/schemas/task.py`実装
  - [x] TaskStatus
  - [x] TaskCreate
  - [x] TaskStatusResponse
  - [x] ErrorDetail
  - [x] ErrorReport

### **ステップ2.4: CRUD層**

- [x] `app/crud/user.py`実装
  - [x] get_user_by_id
  - [x] get_user_by_email
  - [x] get_users（ページネーション対応）
  - [x] create_user
  - [x] update_user_password
  - [x] delete_user

- [x] `app/crud/salon_board_setting.py`実装
  - [x] get_setting_by_id
  - [x] get_settings_by_user_id
  - [x] create_setting
  - [x] update_setting
  - [x] delete_setting

- [x] `app/crud/current_task.py`実装
  - [x] get_task_by_id
  - [x] get_task_by_user_id
  - [x] create_task
  - [x] update_task_progress
  - [x] update_task_status
  - [x] add_task_error
  - [x] delete_task

---

## **フェーズ3: API実装**
**優先度: 最高 | 期間: 2-3日**

### **ステップ3.1: 認証エンドポイント**

- [x] `app/api/v1/endpoints/auth.py`実装
  - [x] `POST /api/v1/auth/token` - ログイン
  - [x] `GET /api/v1/auth/me` - 現在のユーザー情報取得

### **ステップ3.2: ユーザー管理エンドポイント（管理者専用）**

- [x] `app/api/v1/endpoints/users.py`実装
  - [x] `GET /api/v1/users` - ユーザー一覧取得
  - [x] `POST /api/v1/users` - ユーザー作成
  - [x] `GET /api/v1/users/{user_id}` - ユーザー情報取得
  - [x] `PUT /api/v1/users/{user_id}/password` - パスワードリセット
  - [x] `DELETE /api/v1/users/{user_id}` - ユーザー削除
  - [x] 管理者権限チェック依存関数実装

### **ステップ3.3: SALON BOARD設定エンドポイント**

- [x] `app/api/v1/endpoints/sb_settings.py`実装
  - [x] `GET /api/v1/sb-settings` - 設定一覧取得
  - [x] `POST /api/v1/sb-settings` - 設定作成
  - [x] `PUT /api/v1/sb-settings/{setting_id}` - 設定更新
  - [x] `DELETE /api/v1/sb-settings/{setting_id}` - 設定削除

### **ステップ3.4: タスク管理エンドポイント**

- [x] `app/api/v1/endpoints/tasks.py`実装
  - [x] `POST /api/v1/tasks/style-post` - タスク作成・実行
  - [x] `GET /api/v1/tasks/status` - 進捗状況取得
  - [x] `POST /api/v1/tasks/cancel` - 中止リクエスト
  - [x] `GET /api/v1/tasks/error-report` - エラーレポート取得
  - [x] `DELETE /api/v1/tasks/finished-task` - 完了タスク削除
  - [ ] ファイルバリデーション関数実装

### **ステップ3.5: APIルーター統合**

- [x] `app/api/v1/api.py`実装
  - [x] 全エンドポイントのルーター統合

- [x] `app/main.py`実装
  - [x] FastAPIアプリケーション初期化
  - [x] CORS設定
  - [x] 静的ファイルマウント
  - [x] APIルーター登録
  - [ ] テンプレート設定
  - [x] 起動時イベント（DB接続確認）

---

## **フェーズ4: Playwright自動化実装**
**優先度: 最高 | 期間: 3-4日**

### **ステップ4.1: セレクタ設定ファイル**

- [x] `app/selectors.yaml`作成
  - [x] login セクション
  - [x] salon_selection セクション
  - [x] navigation セクション
  - [x] style_form セクション
  - [x] robot_detection セクション
  - [x] widget セクション

### **ステップ4.2: Playwrightサービス**

- [x] `app/services/style_poster.py`実装
  - [x] `SalonBoardStylePoster`クラス定義
  - [x] `__init__`: 初期化、セレクタ読み込み
  - [x] `_start_browser`: Firefox起動、自動化検知対策
  - [x] `_close_browser`: ブラウザ終了
  - [x] `_take_screenshot`: スクリーンショット撮影
  - [x] `_check_robot_detection`: ロボット認証検出
  - [x] `_click_and_wait`: クリック＆待機
  - [x] `step_login`: ログイン処理
    - [x] ログインページへ移動
    - [x] ID/パスワード入力
    - [x] ログインボタンクリック
    - [x] サロン選択ロジック（複数店舗対応）
  - [x] `step_navigate_to_style_list_page`: スタイル一覧ページへ移動
  - [x] `step_process_single_style`: 1件のスタイル処理
    - [x] 新規登録ページへ
    - [x] 画像アップロード
    - [x] スタイリスト名選択
    - [x] テキスト入力（コメント、スタイル名、メニュー内容）
    - [x] カテゴリ/長さ選択
    - [x] クーポン選択
    - [x] ハッシュタグ入力
    - [x] 登録完了
  - [x] `run`: メイン実行ロジック
    - [x] ブラウザ起動
    - [x] ログイン
    - [x] CSVファイル読み込み
    - [x] スタイル一覧ページへ移動
    - [x] スタイルごとにループ処理
    - [x] 進捗更新
    - [ ] 中止検知（Celery統合時に実装）
    - [x] エラーハンドリング
    - [x] ブラウザ終了

---

## **フェーズ5: Celery/非同期処理実装**
**優先度: 最高 | 期間: 2日**

### **ステップ5.1: Celery設定**

- [x] `app/core/celery_app.py`実装
  - [x] Celeryアプリケーション初期化
  - [x] Redisブローカー設定
  - [x] 結果バックエンド設定
  - [x] タスク設定（タイムアウト、リトライ等）

### **ステップ5.2: Celeryタスク**

- [x] `app/services/tasks.py`実装
  - [x] `process_style_post_task`タスク定義
    - [x] タスクIDでDB更新
    - [x] アップロードファイルの検証
    - [x] SalonBoardStylePosterインスタンス化
    - [x] `run`メソッド実行
    - [x] 進捗コールバック実装
    - [x] エラー記録
    - [x] 最終ステータス更新

- [x] `app/worker.py`実装
  - [x] Celeryワーカーのエントリーポイント
  - [x] タスク自動検出設定

---

## **フェーズ6: フロントエンド実装**
**優先度: 高 | 期間: 3-4日**

### **ステップ6.1: 静的ファイル**

- [ ] `app/static/css/style.css`実装
  - [ ] モバイルファーストレスポンシブデザイン
  - [ ] タスク作成フォームスタイル
  - [ ] 進捗バースタイル
  - [ ] エラー表示スタイル
  - [ ] ボタンスタイル
  - [ ] テーブルスタイル

- [ ] `app/static/js/main.js`実装
  - [ ] ログインフォーム送信処理
  - [ ] タスク作成フォーム送信処理（multipart/form-data）
  - [ ] 進捗ポーリング処理（3秒ごと）
  - [ ] UI状態切り替え（Idle/Processing/Finished）
  - [ ] 中止ボタン処理
  - [ ] エラーレポートダウンロード処理
  - [ ] 完了タスク削除処理

### **ステップ6.2: Jinja2テンプレート**

- [ ] `app/templates/base.html`実装
  - [ ] 共通ヘッダー
  - [ ] ナビゲーションバー
  - [ ] フッター
  - [ ] CSS/JSリンク

- [ ] `app/templates/auth/login.html`実装
  - [ ] ログインフォーム
  - [ ] エラーメッセージ表示

- [ ] `app/templates/main/index.html`実装
  - [ ] タスク作成モード
    - [ ] SALON BOARD設定選択ドロップダウン
    - [ ] スタイル情報ファイルアップロード
    - [ ] 画像ファイル複数アップロード
    - [ ] 実行ボタン
  - [ ] 進捗表示モード
    - [ ] 進捗バー
    - [ ] 完了件数/総件数表示
    - [ ] 中止ボタン
  - [ ] 完了モード
    - [ ] 完了メッセージ
    - [ ] エラーレポートダウンロードリンク
    - [ ] OKボタン

- [ ] `app/templates/settings/index.html`実装
  - [ ] 設定一覧テーブル
  - [ ] 設定追加フォーム
  - [ ] 設定編集モーダル
  - [ ] 設定削除確認ダイアログ

- [ ] `app/templates/admin/users.html`実装
  - [ ] ユーザー一覧テーブル
  - [ ] ユーザー追加フォーム
  - [ ] パスワードリセットモーダル
  - [ ] ユーザー削除確認ダイアログ

### **ステップ6.3: テンプレートルーター**

- [ ] `app/api/v1/endpoints/pages.py`実装
  - [ ] `GET /` - ログインページまたはメインページリダイレクト
  - [ ] `GET /login` - ログインページ
  - [ ] `GET /main` - メインページ（認証必須）
  - [ ] `GET /settings` - SALON BOARD設定ページ（認証必須）
  - [ ] `GET /admin/users` - ユーザー管理ページ（管理者のみ）
  - [ ] `POST /logout` - ログアウト処理

---

## **フェーズ7: 運用スクリプトと設定**
**優先度: 中 | 期間: 1日**

### **ステップ7.1: 初回管理者作成スクリプト**

- [ ] `scripts/create_admin.py`実装
  - [ ] argparseでのコマンドライン引数処理
  - [ ] データベース接続
  - [ ] 管理者アカウント作成
  - [ ] エラーハンドリング

### **ステップ7.2: データベースマイグレーション**

- [ ] Alembic初期化
  - [ ] `alembic init alembic`実行
  - [ ] `alembic.ini`設定

- [ ] 初回マイグレーションファイル作成
  - [ ] `alembic revision --autogenerate -m "Initial migration"`
  - [ ] マイグレーションファイル確認・修正

- [ ] マイグレーション実行スクリプト
  - [ ] `scripts/init_db.py`作成（初回セットアップ用）

### **ステップ7.3: README作成**

- [ ] `README.md`実装
  - [ ] プロジェクト概要
  - [ ] セットアップ手順
  - [ ] 環境変数設定方法
  - [ ] Docker起動コマンド
  - [ ] 初回管理者作成コマンド
  - [ ] トラブルシューティング

---

## **フェーズ8: テストとデバッグ**
**優先度: 中 | 期間: 2-3日**

### **ステップ8.1: ユニットテスト**

- [ ] テスト環境設定
  - [ ] `pytest`インストール
  - [ ] `pytest.ini`設定
  - [ ] テスト用データベース設定

- [ ] `tests/test_crud.py`実装
  - [ ] ユーザーCRUDテスト
  - [ ] SALON BOARD設定CRUDテスト
  - [ ] タスクCRUDテスト

- [ ] `tests/test_security.py`実装
  - [ ] パスワードハッシュ化テスト
  - [ ] JWT生成/検証テスト
  - [ ] Fernet暗号化/復号化テスト

### **ステップ8.2: 統合テスト**

- [ ] `tests/test_api.py`実装
  - [ ] 認証APIテスト
  - [ ] ユーザー管理APIテスト
  - [ ] SALON BOARD設定APIテスト
  - [ ] タスクAPIテスト（モック使用）

- [ ] サンプルデータでの実行テスト
  - [ ] `sample/styles_data.csv`でのタスク実行
  - [ ] エラーハンドリング確認
  - [ ] 進捗更新確認

### **ステップ8.3: デバッグとリファクタリング**

- [ ] ログ出力確認
- [ ] エラーハンドリング改善
- [ ] コードクリーンアップ
- [ ] 型ヒント追加
- [ ] ドキュメント文字列追加

---

## **3. 完了基準**

### **各フェーズの完了基準**

#### **フェーズ1完了基準**
- [ ] Docker Composeで全コンテナが起動する
- [ ] データベースに接続できる
- [ ] Redisに接続できる

#### **フェーズ2完了基準**
- [ ] データベースマイグレーションが成功する
- [ ] モデルが正しく作成される
- [ ] CRUD操作が動作する

#### **フェーズ3完了基準**
- [ ] 全APIエンドポイントが応答する
- [ ] JWT認証が動作する
- [ ] API仕様書通りのレスポンスを返す

#### **フェーズ4完了基準**
- [ ] Playwrightでブラウザが起動する
- [ ] SALON BOARDにログインできる
- [ ] 1件のスタイル投稿が成功する

#### **フェーズ5完了基準**
- [ ] Celeryワーカーが起動する
- [ ] タスクがキューイングされる
- [ ] バックグラウンドでスタイル投稿が実行される

#### **フェーズ6完了基準**
- [ ] ログインページが表示される
- [ ] メインページでタスク作成ができる
- [ ] 進捗がリアルタイムで表示される

#### **フェーズ7完了基準**
- [ ] 初回管理者アカウントが作成できる
- [ ] マイグレーションが正常に実行される
- [ ] READMEの手順で環境構築できる

#### **フェーズ8完了基準**
- [ ] 全ユニットテストが成功する
- [ ] サンプルデータでの実行が成功する
- [ ] エラーが適切にハンドリングされる

---

## **4. リスクと対策**

| リスク | 影響度 | 対策 |
|:------|:------|:-----|
| Playwright実装の複雑性 | 高 | セレクタをYAMLで外部管理、段階的実装 |
| SALON BOARDのUI変更 | 高 | セレクタの柔軟な設計、エラーハンドリング強化 |
| Docker環境の構築問題 | 中 | 公式イメージ使用、明確なドキュメント |
| Celeryタスクのデバッグ困難 | 中 | 詳細なログ出力、ローカルテスト環境 |
| データベース接続エラー | 中 | リトライ機構、接続プール設定 |

---

## **5. 進捗管理**

### **進捗状況サマリー**
- **フェーズ1**: 0/4 ステップ完了
- **フェーズ2**: 0/4 ステップ完了
- **フェーズ3**: 0/5 ステップ完了
- **フェーズ4**: 0/2 ステップ完了
- **フェーズ5**: 0/2 ステップ完了
- **フェーズ6**: 0/3 ステップ完了
- **フェーズ7**: 0/3 ステップ完了
- **フェーズ8**: 0/3 ステップ完了

### **全体進捗**
- **総タスク数**: 約180個
- **完了タスク数**: 0個
- **進捗率**: 0%

---

## **6. 変更履歴**

| バージョン | 日付 | 変更内容 | 変更者 |
|:---------|:-----|:---------|:------|
| 1.0 | 2025-01-20 | 初版作成 | 開発チーム |

---

**文書作成日:** 2025年1月20日
**作成者:** 開発チーム
**承認者:** プロジェクトマネージャー
