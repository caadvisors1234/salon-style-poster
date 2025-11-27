## **SALON BOARDスタイル自動投稿Webアプリケーション API仕様書**

### **1. 概要**

#### **1.1. API概要**
本APIは、SALON BOARDへのスタイル自動投稿を行うWebアプリケーションのバックエンドインターフェースです。RESTful API設計原則に基づき、JSON形式でのデータ交換を行います。

#### **1.2. ベースURL**
```
/api/v1
```

#### **1.3. 認証方式**
JWT (JSON Web Token) Bearer認証を使用します。

**認証ヘッダー形式:**
```
Authorization: Bearer <access_token>
```

#### **1.4. 共通レスポンスフォーマット**

**成功レスポンス:**
```json
{
  "data": { ... },
  "message": "Success message"
}
```

**エラーレスポンス:**
```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE"
}
```

#### **1.5. 共通HTTPステータスコード**

| コード | 意味 | 使用ケース |
|:------|:-----|:---------|
| 200 | OK | リクエスト成功（取得、更新） |
| 201 | Created | リソース作成成功 |
| 202 | Accepted | 非同期処理受付成功 |
| 204 | No Content | 成功（レスポンスボディなし） |
| 400 | Bad Request | リクエストパラメータ不正 |
| 401 | Unauthorized | 認証失敗 |
| 403 | Forbidden | 権限不足 |
| 404 | Not Found | リソースが存在しない |
| 409 | Conflict | リソース競合（タスク実行中など） |
| 422 | Unprocessable Entity | バリデーションエラー |
| 500 | Internal Server Error | サーバーエラー |

---

### **2. 認証API**

#### **2.1. トークン取得（ログイン）**

**エンドポイント:**
```
POST /api/v1/auth/token
```

**説明:**
ユーザー認証を行い、アクセストークンを発行します。

**リクエスト:**
- **Content-Type:** `application/x-www-form-urlencoded`
- **認証:** 不要

**パラメータ:**

| パラメータ名 | 型 | 必須 | 説明 |
|:-----------|:---|:-----|:-----|
| username | string | ○ | ユーザーのメールアドレス |
| password | string | ○ | パスワード |

**リクエスト例:**
```
username=user@example.com&password=securepassword123
```

**レスポンス (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**レスポンスフィールド:**

| フィールド名 | 型 | 説明 |
|:-----------|:---|:-----|
| access_token | string | JWTアクセストークン |
| token_type | string | トークンタイプ（常に"bearer"） |

**エラーレスポンス (401 Unauthorized):**
```json
{
  "detail": "Incorrect email or password",
  "error_code": "INVALID_CREDENTIALS"
}
```

---

#### **2.2. 現在のユーザー情報取得**

**エンドポイント:**
```
GET /api/v1/auth/me
```

**説明:**
現在ログイン中のユーザー情報を取得します。

**リクエスト:**
- **認証:** 必要

**レスポンス (200 OK):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "role": "user",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**レスポンスフィールド:**

| フィールド名 | 型 | 説明 |
|:-----------|:---|:-----|
| id | integer | ユーザーID |
| email | string | メールアドレス |
| role | string | ユーザー役割（"admin" or "user"） |
| created_at | string | アカウント作成日時（ISO 8601形式） |

---

### **3. ユーザー管理API（管理者専用）**

#### **3.1. ユーザー一覧取得**

**エンドポイント:**
```
GET /api/v1/users
```

**説明:**
システムに登録されている全ユーザーの一覧を取得します。

**リクエスト:**
- **認証:** 必要（管理者のみ）

**クエリパラメータ:**

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|:-----------|:---|:-----|:---------|:-----|
| skip | integer | × | 0 | スキップ件数（ページネーション用） |
| limit | integer | × | 100 | 取得件数上限 |
| role | string | × | - | 役割でフィルタ（"admin" or "user"） |

**レスポンス (200 OK):**
```json
{
  "total": 15,
  "users": [
    {
      "id": 1,
      "email": "admin@example.com",
      "role": "admin",
      "created_at": "2025-01-10T09:00:00Z"
    },
    {
      "id": 2,
      "email": "user1@example.com",
      "role": "user",
      "created_at": "2025-01-12T14:30:00Z"
    }
  ]
}
```

**エラーレスポンス (403 Forbidden):**
```json
{
  "detail": "Admin privileges required",
  "error_code": "INSUFFICIENT_PRIVILEGES"
}
```

---

#### **3.2. ユーザー作成**

**エンドポイント:**
```
POST /api/v1/users
```

**説明:**
新規ユーザーアカウントを作成します。

**リクエスト:**
- **Content-Type:** `application/json`
- **認証:** 必要（管理者のみ）

**リクエストボディ:**
```json
{
  "email": "newuser@example.com",
  "password": "securePassword123!",
  "role": "user"
}
```

**リクエストフィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|:-----------|:---|:-----|:-----|
| email | string | ○ | メールアドレス（ログインID） |
| password | string | ○ | 初期パスワード（8文字以上） |
| role | string | ○ | ユーザー役割（"admin" or "user"） |

**レスポンス (201 Created):**
```json
{
  "id": 3,
  "email": "newuser@example.com",
  "role": "user",
  "created_at": "2025-01-20T11:15:00Z"
}
```

**エラーレスポンス (409 Conflict):**
```json
{
  "detail": "User with this email already exists",
  "error_code": "USER_ALREADY_EXISTS"
}
```

**バリデーションエラー (422 Unprocessable Entity):**
```json
{
  "detail": [
    {
      "loc": ["body", "password"],
      "msg": "Password must be at least 8 characters long",
      "type": "value_error"
    }
  ]
}
```

---

#### **3.3. ユーザー情報取得**

**エンドポイント:**
```
GET /api/v1/users/{user_id}
```

**説明:**
特定のユーザー情報を取得します。

**リクエスト:**
- **認証:** 必要（管理者のみ）

**パスパラメータ:**

| パラメータ名 | 型 | 説明 |
|:-----------|:---|:-----|
| user_id | integer | ユーザーID |

**レスポンス (200 OK):**
```json
{
  "id": 2,
  "email": "user1@example.com",
  "role": "user",
  "created_at": "2025-01-12T14:30:00Z"
}
```

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "User not found",
  "error_code": "USER_NOT_FOUND"
}
```

---

#### **3.4. ユーザー情報更新**

**エンドポイント:**
```
PUT /api/v1/users/{user_id}
```

**説明:**
指定ユーザーの情報を更新します。

**リクエスト:**
- **Content-Type:** `application/json`
- **認証:** 必要（管理者のみ）

**パスパラメータ:**

| パラメータ名 | 型 | 説明 |
|:-----------|:---|:-----|
| user_id | integer | ユーザーID |

**リクエストボディ:**
```json
{
  "email": "updated@example.com",
  "password": "newSecurePassword456!",
  "role": "user",
  "is_active": true
}
```

**リクエストフィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|:-----------|:---|:-----|:-----|
| email | string | × | メールアドレス |
| password | string | × | 新しいパスワード（8文字以上） |
| role | string | × | ユーザー役割（"admin" or "user"） |
| is_active | boolean | × | アカウント有効状態 |

**注意:** すべてのフィールドは任意です。指定したフィールドのみが更新されます。

**レスポンス (200 OK):**
```json
{
  "id": 2,
  "email": "updated@example.com",
  "role": "user",
  "is_active": true,
  "created_at": "2025-01-12T14:30:00Z"
}
```

---

#### **3.5. ユーザー削除**

**エンドポイント:**
```
DELETE /api/v1/users/{user_id}
```

**説明:**
ユーザーアカウントを削除します。関連するSALON BOARD設定と実行中タスクも同時に削除されます（CASCADE削除）。

**リクエスト:**
- **認証:** 必要（管理者のみ）

**パスパラメータ:**

| パラメータ名 | 型 | 説明 |
|:-----------|:---|:-----|
| user_id | integer | ユーザーID |

**レスポンス (204 No Content):**
レスポンスボディなし

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "User not found",
  "error_code": "USER_NOT_FOUND"
}
```

**エラーレスポンス (400 Bad Request):**
```json
{
  "detail": "Cannot delete your own account",
  "error_code": "CANNOT_DELETE_SELF"
}
```

---

### **4. SALON BOARD設定管理API**

#### **4.1. 設定一覧取得**

**エンドポイント:**
```
GET /api/v1/sb-settings
```

**説明:**
ログイン中のユーザーのSALON BOARD設定一覧を取得します。

**リクエスト:**
- **認証:** 必要

**レスポンス (200 OK):**
```json
{
  "settings": [
    {
      "id": 1,
      "setting_name": "A店",
      "sb_user_id": "salon_a@example.com",
      "salon_id": "12345",
      "salon_name": "サロンA 高崎店",
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-18T15:30:00Z"
    },
    {
      "id": 2,
      "setting_name": "B店",
      "sb_user_id": "salon_b@example.com",
      "salon_id": null,
      "salon_name": null,
      "created_at": "2025-01-16T11:00:00Z",
      "updated_at": "2025-01-16T11:00:00Z"
    }
  ]
}
```

**レスポンスフィールド:**

| フィールド名 | 型 | 説明 |
|:-----------|:---|:-----|
| id | integer | 設定ID |
| setting_name | string | 設定名 |
| sb_user_id | string | SALON BOARDログインID |
| salon_id | string \| null | サロンID（任意） |
| salon_name | string \| null | サロン名（任意） |
| created_at | string | 作成日時（ISO 8601形式） |
| updated_at | string | 更新日時（ISO 8601形式） |

**注意:** パスワードは返却されません（セキュリティ対策）。

---

#### **4.2. 設定作成**

**エンドポイント:**
```
POST /api/v1/sb-settings
```

**説明:**
新しいSALON BOARD設定を作成します。

**リクエスト:**
- **Content-Type:** `application/json`
- **認証:** 必要

**リクエストボディ:**
```json
{
  "setting_name": "C店",
  "sb_user_id": "salon_c@example.com",
  "sb_password": "salonPassword123!",
  "salon_id": "67890",
  "salon_name": "サロンC 前橋店"
}
```

**リクエストフィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|:-----------|:---|:-----|:-----|
| setting_name | string | ○ | 設定名（最大100文字） |
| sb_user_id | string | ○ | SALON BOARDログインID |
| sb_password | string | ○ | SALON BOARDパスワード（暗号化して保存） |
| salon_id | string | × | サロンID（複数店舗アカウント用） |
| salon_name | string | × | サロン名（複数店舗アカウント用） |

**レスポンス (201 Created):**
```json
{
  "id": 3,
  "setting_name": "C店",
  "sb_user_id": "salon_c@example.com",
  "salon_id": "67890",
  "salon_name": "サロンC 前橋店",
  "created_at": "2025-01-20T12:00:00Z",
  "updated_at": "2025-01-20T12:00:00Z"
}
```

**バリデーションエラー (422 Unprocessable Entity):**
```json
{
  "detail": [
    {
      "loc": ["body", "setting_name"],
      "msg": "Setting name is required",
      "type": "value_error"
    }
  ]
}
```

---

#### **4.3. 設定更新**

**エンドポイント:**
```
PUT /api/v1/sb-settings/{setting_id}
```

**説明:**
既存のSALON BOARD設定を更新します。

**リクエスト:**
- **Content-Type:** `application/json`
- **認証:** 必要

**パスパラメータ:**

| パラメータ名 | 型 | 説明 |
|:-----------|:---|:-----|
| setting_id | integer | 設定ID |

**リクエストボディ:**
```json
{
  "setting_name": "A店（更新）",
  "sb_user_id": "salon_a_new@example.com",
  "sb_password": "newPassword456!",
  "salon_id": "54321",
  "salon_name": "サロンA 高崎本店"
}
```

**リクエストフィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|:-----------|:---|:-----|:-----|
| setting_name | string | × | 設定名 |
| sb_user_id | string | × | SALON BOARDログインID |
| sb_password | string | × | SALON BOARDパスワード（指定時のみ更新） |
| salon_id | string | × | サロンID |
| salon_name | string | × | サロン名 |

**注意:** 全フィールド任意。指定されたフィールドのみ更新されます。

**レスポンス (200 OK):**
```json
{
  "id": 1,
  "setting_name": "A店（更新）",
  "sb_user_id": "salon_a_new@example.com",
  "salon_id": "54321",
  "salon_name": "サロンA 高崎本店",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-20T13:00:00Z"
}
```

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "Setting not found",
  "error_code": "SETTING_NOT_FOUND"
}
```

**エラーレスポンス (403 Forbidden):**
```json
{
  "detail": "You can only update your own settings",
  "error_code": "PERMISSION_DENIED"
}
```

---

#### **4.4. 設定削除**

**エンドポイント:**
```
DELETE /api/v1/sb-settings/{setting_id}
```

**説明:**
SALON BOARD設定を削除します。

**リクエスト:**
- **認証:** 必要

**パスパラメータ:**

| パラメータ名 | 型 | 説明 |
|:-----------|:---|:-----|
| setting_id | integer | 設定ID |

**レスポンス (204 No Content):**
レスポンスボディなし

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "Setting not found",
  "error_code": "SETTING_NOT_FOUND"
}
```

**エラーレスポンス (403 Forbidden):**
```json
{
  "detail": "You can only delete your own settings",
  "error_code": "PERMISSION_DENIED"
}
```

---

### **5. タスク管理API**

#### **5.1. スタイル投稿タスク作成・実行**

**エンドポイント:**
```
POST /api/v1/tasks/style-post
```

**説明:**
新規スタイル投稿タスクを作成し、バックグラウンドで実行を開始します。

**リクエスト:**
- **Content-Type:** `multipart/form-data`
- **認証:** 必要

**フォームデータ:**

| フィールド名 | 型 | 必須 | 説明 |
|:-----------|:---|:-----|:-----|
| setting_id | integer | ○ | 使用するSALON BOARD設定ID |
| style_data_file | file | ○ | スタイル情報ファイル（CSV or Excel） |
| image_files | file[] | ○ | 画像ファイル（複数アップロード可） |

**リクエスト例（cURL）:**
```bash
curl -X POST "https://example.com/api/v1/tasks/style-post" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "setting_id=1" \
  -F "style_data_file=@styles.csv" \
  -F "image_files=@style1.jpg" \
  -F "image_files=@style2.png"
```

**バリデーション処理:**
1. 指定された`setting_id`がユーザーの設定として存在するか確認
2. スタイル情報ファイルの形式確認（CSV/Excel）
3. 必須カラムの存在確認
4. 画像ファイル形式確認（JPEG/PNG）
5. スタイル情報ファイル内の`画像名`が、アップロードされた画像ファイルに全て存在するか確認

**レスポンス (202 Accepted):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Task accepted and started"
}
```

**レスポンスフィールド:**

| フィールド名 | 型 | 説明 |
|:-----------|:---|:-----|
| task_id | string | タスクID（UUID形式） |
| message | string | 成功メッセージ |

**エラーレスポンス (409 Conflict):**
```json
{
  "detail": "You already have a task in progress",
  "error_code": "TASK_ALREADY_RUNNING"
}
```

**エラーレスポンス (422 Unprocessable Entity):**
```json
{
  "detail": "Missing image file: style3.jpg referenced in CSV",
  "error_code": "MISSING_IMAGE_FILE"
}
```

**エラーレスポンス (400 Bad Request):**
```json
{
  "detail": "Invalid file format. Only CSV and Excel files are supported",
  "error_code": "INVALID_FILE_FORMAT"
}
```

---

#### **5.2. タスク進捗状況取得**

**エンドポイント:**
```
GET /api/v1/tasks/status
```

**説明:**
ログイン中のユーザーの実行中タスクの進捗状況を取得します。

**リクエスト:**
- **認証:** 必要

**レスポンス (200 OK):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "PROCESSING",
  "total_items": 20,
  "completed_items": 5,
  "progress": 25.0,
  "has_errors": false,
  "created_at": "2025-01-20T14:00:00Z"
}
```

**レスポンスフィールド:**

| フィールド名 | 型 | 説明 |
|:-----------|:---|:-----|
| task_id | string | タスクID（UUID形式） |
| status | string | タスク状態（"PROCESSING", "CANCELLING", "SUCCESS", "FAILURE"） |
| total_items | integer | 処理対象の総スタイル数 |
| completed_items | integer | 処理完了したスタイル数 |
| progress | float | 進捗率（0.0 ~ 100.0） |
| has_errors | boolean | エラー発生有無 |
| created_at | string | タスク作成日時（ISO 8601形式） |

**タスクステータス詳細:**

| ステータス | 説明 |
|:---------|:-----|
| PROCESSING | 処理中 |
| CANCELLING | 中止リクエスト受付済み（現在の処理完了後に停止） |
| SUCCESS | 正常完了 |
| FAILURE | エラー終了または中止完了 |

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "No active task found",
  "error_code": "NO_ACTIVE_TASK"
}
```

---

#### **5.3. タスク中止リクエスト**

**エンドポイント:**
```
POST /api/v1/tasks/cancel
```

**説明:**
実行中のタスクの中止をリクエストします。現在処理中のスタイルが完了した後、安全に停止します。

**リクエスト:**
- **Content-Type:** `application/json`
- **認証:** 必要

**リクエストボディ:**
不要（空のJSONオブジェクト `{}` または省略可）

**レスポンス (202 Accepted):**
```json
{
  "message": "Task cancellation requested. The task will stop after completing the current item."
}
```

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "No active task to cancel",
  "error_code": "NO_ACTIVE_TASK"
}
```

**エラーレスポンス (400 Bad Request):**
```json
{
  "detail": "Task is already being cancelled or has finished",
  "error_code": "TASK_NOT_CANCELLABLE"
}
```

---

#### **5.4. エラーレポート取得**

**エンドポイント:**
```
GET /api/v1/tasks/error-report
```

**説明:**
完了したタスクのエラーレポートを取得します。

**リクエスト:**
- **認証:** 必要

**レスポンス (200 OK):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "total_errors": 2,
  "errors": [
    {
      "row_number": 3,
      "style_name": "大人かわいいボブ",
      "field": "クーポン名",
      "reason": "指定されたクーポン名「カット＋カラー特別割引」が見つかりませんでした",
      "screenshot_url": "/static/screenshots/error-20250120-140530-001.png"
    },
    {
      "row_number": 7,
      "style_name": "無造作ツイストパーマ",
      "field": "スタイリスト名",
      "reason": "指定されたスタイリスト名「佐藤 太郎」が見つかりませんでした",
      "screenshot_url": "/static/screenshots/error-20250120-140615-002.png"
    }
  ]
}
```

**レスポンスフィールド:**

| フィールド名 | 型 | 説明 |
|:-----------|:---|:-----|
| task_id | string | タスクID |
| total_errors | integer | エラー総数 |
| errors | array | エラー詳細のリスト |

**エラーオブジェクトフィールド:**

| フィールド名 | 型 | 説明 |
|:-----------|:---|:-----|
| row_number | integer | CSVファイルの行番号 |
| style_name | string | スタイル名 |
| field | string | エラーが発生したフィールド名 |
| reason | string | エラー原因の詳細説明 |
| screenshot_url | string | エラー発生時のスクリーンショット画像URL |

**レスポンス (204 No Content):**
エラーが存在しない場合（レスポンスボディなし）

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "No completed task found",
  "error_code": "NO_COMPLETED_TASK"
}
```

---

#### **5.5. 完了タスク情報削除**

**エンドポイント:**
```
DELETE /api/v1/tasks/finished-task
```

**説明:**
完了したタスクの情報をデータベースから削除します。これにより、次のタスクを作成できるようになります。

**リクエスト:**
- **認証:** 必要

**レスポンス (204 No Content):**
レスポンスボディなし

**エラーレスポンス (404 Not Found):**
```json
{
  "detail": "No finished task to delete",
  "error_code": "NO_FINISHED_TASK"
}
```

**エラーレスポンス (400 Bad Request):**
```json
{
  "detail": "Cannot delete task that is still in progress",
  "error_code": "TASK_STILL_RUNNING"
}
```

---

### **6. データモデル定義**

#### **6.1. User（ユーザー）**

```typescript
interface User {
  id: number;
  email: string;
  role: "admin" | "user";
  created_at: string; // ISO 8601
}
```

#### **6.2. SalonBoardSetting（SALON BOARD設定）**

```typescript
interface SalonBoardSetting {
  id: number;
  setting_name: string;
  sb_user_id: string;
  salon_id: string | null;
  salon_name: string | null;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}
```

**注意:** `sb_password`は取得APIでは返却されません。

#### **6.3. TaskStatus（タスク状態）**

```typescript
interface TaskStatus {
  task_id: string; // UUID
  status: "PROCESSING" | "CANCELLING" | "SUCCESS" | "FAILURE";
  total_items: number;
  completed_items: number;
  progress: number; // 0.0 ~ 100.0
  has_errors: boolean;
  created_at: string; // ISO 8601
}
```

#### **6.4. ErrorReport（エラーレポート）**

```typescript
interface ErrorReport {
  task_id: string;
  total_errors: number;
  errors: ErrorDetail[];
}

interface ErrorDetail {
  row_number: number;
  style_name: string;
  field: string;
  reason: string;
  screenshot_url: string;
}
```

---

### **7. セキュリティ仕様**

#### **7.1. パスワードハッシュ化**
- **アルゴリズム:** bcrypt
- **ライブラリ:** `passlib[bcrypt]`
- **ソルトラウンド:** 12

#### **7.2. SALON BOARDパスワード暗号化**
- **アルゴリズム:** Fernet（対称鍵暗号）
- **ライブラリ:** `cryptography`
- **キー管理:** 環境変数`ENCRYPTION_KEY`で管理

#### **7.3. JWT設定**
- **アルゴリズム:** HS256
- **有効期限:** 60分（`ACCESS_TOKEN_EXPIRE_MINUTES=60`）
- **シークレットキー:** 環境変数`SECRET_KEY`で管理

#### **7.4. CORS設定**
開発環境では必要に応じて許可するが、本番環境では厳格に制限する。

---

### **8. レート制限**

#### **8.1. 認証エンドポイント**
- **制限:** 5回/分/IPアドレス
- **目的:** ブルートフォース攻撃の防止

#### **8.2. タスク作成エンドポイント**
- **制限:** 10回/時間/ユーザー
- **目的:** システムリソースの保護

---

### **9. エラーコード一覧**

| エラーコード | HTTPステータス | 説明 |
|:-----------|:--------------|:-----|
| INVALID_CREDENTIALS | 401 | ログイン認証失敗 |
| INSUFFICIENT_PRIVILEGES | 403 | 権限不足 |
| PERMISSION_DENIED | 403 | リソースへのアクセス権限なし |
| USER_ALREADY_EXISTS | 409 | メールアドレスが既に登録済み |
| USER_NOT_FOUND | 404 | ユーザーが存在しない |
| CANNOT_DELETE_SELF | 400 | 自分自身のアカウントは削除不可 |
| SETTING_NOT_FOUND | 404 | SALON BOARD設定が存在しない |
| TASK_ALREADY_RUNNING | 409 | 既にタスク実行中 |
| NO_ACTIVE_TASK | 404 | 実行中のタスクが存在しない |
| NO_COMPLETED_TASK | 404 | 完了したタスクが存在しない |
| NO_FINISHED_TASK | 404 | 削除対象の完了タスクが存在しない |
| TASK_NOT_CANCELLABLE | 400 | タスクは中止できない状態 |
| TASK_STILL_RUNNING | 400 | タスクがまだ実行中 |
| MISSING_IMAGE_FILE | 422 | CSV内で参照された画像ファイルが不足 |
| INVALID_FILE_FORMAT | 400 | ファイル形式が不正 |
| VALIDATION_ERROR | 422 | リクエストデータのバリデーションエラー |

---

### **10. APIバージョニング**

#### **10.1. 現在のバージョン**
- **バージョン:** v1
- **ベースパス:** `/api/v1`

#### **10.2. 将来の拡張**
APIに破壊的変更が必要な場合は、`/api/v2`として新バージョンを提供し、v1との並行運用期間を設けます。

---

### **11. 付録: リクエスト/レスポンス例**

#### **11.1. 典型的なタスク実行フロー**

**1. ログイン**
```bash
POST /api/v1/auth/token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=mypassword
```

**レスポンス:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**2. SALON BOARD設定一覧取得**
```bash
GET /api/v1/sb-settings
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**レスポンス:**
```json
{
  "settings": [
    {
      "id": 1,
      "setting_name": "A店",
      "sb_user_id": "salon_a@example.com",
      "salon_id": "12345",
      "salon_name": "サロンA 高崎店",
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-18T15:30:00Z"
    }
  ]
}
```

**3. タスク作成**
```bash
POST /api/v1/tasks/style-post
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: multipart/form-data

setting_id=1
style_data_file=@styles.csv
image_files=@style1.jpg
image_files=@style2.png
```

**レスポンス:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Task accepted and started"
}
```

**4. 進捗確認（ポーリング）**
```bash
GET /api/v1/tasks/status
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**レスポンス:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "PROCESSING",
  "total_items": 2,
  "completed_items": 1,
  "progress": 50.0,
  "has_errors": false,
  "created_at": "2025-01-20T14:00:00Z"
}
```

**5. 完了確認**
```bash
GET /api/v1/tasks/status
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**レスポンス:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "SUCCESS",
  "total_items": 2,
  "completed_items": 2,
  "progress": 100.0,
  "has_errors": false,
  "created_at": "2025-01-20T14:00:00Z"
}
```

**6. 完了タスク削除（次のタスク準備）**
```bash
DELETE /api/v1/tasks/finished-task
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**レスポンス:**
```
204 No Content
```

---

### **11. 補足: スタイル非掲載関連エンドポイント**

#### **11.1. スタイル件数取得**
- `GET /api/v1/tasks/style-count`
- 認証必須。`salon_url` は `https://beauty.hotpepper.jp/slnHxxxxxxx/` 形式のみ許可（hostname 完全一致、ユーザー情報禁止）。
- レスポンス例:
```json
{ "style_count": 2105, "style_url": "https://beauty.hotpepper.jp/slnH000232182/style/" }
```

#### **11.2. スタイル非掲載タスク作成**
- `POST /api/v1/tasks/style-unpublish`
- フォーム: `setting_id`, `salon_url`, `range_start`, `range_end`, `exclude_numbers`(任意, カンマ区切り)。
- SALON BOARD設定の `salon_id/salon_name` を使用し、複数店舗アカウントでも自動選択。
- 進捗/キャンセル/エラーレポートは既存タスクAPIと共通。

---

### **12. 変更履歴**

| バージョン | 日付 | 変更内容 |
|:---------|:-----|:---------|
| 1.0 | 2025-01-20 | 初版作成 |

---

**文書作成日:** 2025年1月20日
**作成者:** 開発チーム
**承認者:** プロジェクトマネージャー
