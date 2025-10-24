# コードベース構造

## ディレクトリ構造
```
app/
├── api/v1/endpoints/     # APIエンドポイント
│   ├── auth.py           # 認証API
│   ├── users.py          # ユーザー管理API（管理者専用）
│   ├── sb_settings.py    # SALON BOARD設定API
│   └── tasks.py          # タスク管理API
├── core/                 # コア機能
│   ├── config.py         # 設定管理
│   ├── security.py       # セキュリティ（認証・暗号化）
│   └── celery_app.py     # Celery設定
├── models/               # SQLAlchemyモデル
│   ├── user.py           # ユーザーモデル
│   ├── salon_board_setting.py  # SALON BOARD設定モデル
│   └── current_task.py   # タスクモデル
├── schemas/              # Pydanticスキーマ
├── crud/                 # データベース操作
├── services/             # ビジネスロジック
│   ├── style_poster.py   # Playwright自動化
│   └── tasks.py          # Celeryタスク
├── static/               # 静的ファイル
├── templates/            # Jinja2テンプレート
└── selectors.yaml        # Playwrightセレクタ設定
```

## 主要コンポーネント

### APIエンドポイント
- **認証**: `/api/v1/auth/token`, `/api/v1/auth/me`
- **ユーザー管理**: `/api/v1/users/*` (管理者専用)
- **SALON BOARD設定**: `/api/v1/sb-settings/*`
- **タスク管理**: `/api/v1/tasks/*`

### データモデル
- **User**: ユーザー情報（email, role, hashed_password）
- **SalonBoardSetting**: SALON BOARD設定（暗号化されたパスワード）
- **CurrentTask**: 実行中タスク（進捗、エラー情報）

### セキュリティ機能
- **認証**: JWT (python-jose)
- **パスワードハッシュ化**: bcrypt (passlib)
- **暗号化**: Fernet (cryptography)
- **アクセス制御**: 管理者・一般ユーザー権限分離

### 非同期処理
- **Celery**: バックグラウンドタスク実行
- **Redis**: タスクキュー・結果バックエンド
- **Playwright**: ブラウザ自動化（Firefox）