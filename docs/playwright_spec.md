## **Playwright実装詳細仕様書**

### **1. 目的**

本仕様書は、Webアプリケーションのバックグラウンドタスクとして実行される `SalonBoardStylePoster` クラスの構造、メソッド、および処理フローを詳細に定義する。開発者は本仕様書に基づき、SALON BOARDの画面操作を自動化するPythonコードを実装する。

### **2. クラス設計**

### **2.1. クラス名**

`SalonBoardStylePoster`

### **2.2. 責務**

SALON BOARDへのログインから、指定された複数スタイルの連続投稿まで、一連のブラウザ操作を完遂する。処理の進捗や結果は、呼び出し元（タスク管理システム）に報告する責任を負う。

### **2.3. 主要なプロパティ**

| プロパティ名 | 型 | 説明 |
| --- | --- | --- |
| `selectors` | `Dict` | `selectors.yaml` から読み込まれたセレクタ設定。 |
| `screenshot_dir` | `str` | エラー発生時のスクリーンショット保存先ディレクトリパス。 |
| `headless` | `bool` | ヘッドレスモードで実行するかどうか。 |
| `slow_mo` | `int` | 操作間の遅延時間（ミリ秒）。 |
| `playwright` | `Playwright` | Playwrightのメインインスタンス。 |
| `browser` | `Browser` | 起動したChromiumベースのブラウザインスタンス。 |
| `page` | `Page` | 現在操作中のブラウザページのインスタンス。 |
| `progress_callback` | `Callable` | （オプション）進捗を呼び出し元に通知するためのコールバック関数。 |

### **2.4. 外部インターフェース（Public Methods）**

- `__init__(self, selectors, screenshot_dir, headless, slow_mo)`:
  クラスを初期化する。
- `run(self, user_id, password, data_filepath, image_dir, salon_info, progress_callback)`:
  自動投稿の全プロセスを実行するエントリーポイント。内部でブラウザの起動から終了までを管理する。

### **3. 内部実装仕様**

### **3.1. 初期化と終了処理 (`_start_browser`, `_close_browser`)**

- **ブラウザ起動 (`_start_browser`)**:
    - `sync_playwright().start()` でPlaywrightを起動する。
    - `playwright.chromium.launch(channel="chrome", **launch_kwargs)` でChromeチャンネルのChromiumを優先的に起動し、失敗した場合は `playwright.chromium.launch(**launch_kwargs)` にフォールバックする。
    - `browser.new_context(...)` では **デスクトップChrome相当の環境** を再現するため、以下のパラメータを設定する：`viewport={"width": 1366, "height": 768}`、デスクトップ用User-Agent、`device_scale_factor=1.0`、`is_mobile=False`、`has_touch=False`、`locale="ja-JP"`、`timezone_id="Asia/Tokyo"`。
    - `context.add_init_script(...)` で `navigator.webdriver` の隠蔽や `platform`・`maxTouchPoints` の補正、`ontouchstart`・`matchMedia` のポリフィルを適用する。
    - `context.new_page()` でページを生成し、`self.page` に格納した後、`requestfailed`・`response`・`request` イベントリスナーを登録し `stealth_sync(self.page)` を適用する。
    - `page.set_default_timeout(180000)` を設定し、全操作のデフォルトタイムアウトを3分に統一する。
- **ブラウザ終了 (`_close_browser`)**:
    - `context.close()` → `browser.close()` → `playwright.stop()` の順でクリーンアップし、各ステップで例外が発生した場合もログを残しつつリソースを解放する。

### **3.2. 汎用ヘルパーメソッド**

- **スクリーンショット撮影 (`_take_screenshot`)**: エラー発生時に呼び出され、日時を含んだファイル名で `screenshot_dir` 配下へPNGを保存する。
- **ロボット認証検出 (`_check_robot_detection`)**: セレクタおよびテキストの両方を対象に `locator.first.is_visible()` で表示状態を確認し、検出時はスクリーンショットを採取したうえで `True` を返す。
- **人間的なウェイト (`_human_pause`)**: 基本待機時間・ゆらぎ・最小値を元にランダムな遅延を挿入し、Akamai Bot Managerへのヒットを避ける。
- **Akamai対策 (`_stimulate_akamai_sensor`, `_warmup_akamai_endpoints`, `_ensure_akamai_readiness`, `_wait_for_akamai_clearance`)**: タップ／スクロールイベントやバックグラウンドリクエストで `_abck` Cookie の状態を `~0~` または `~1~` へ誘導し、画像アップロード前後でセッションを安定させる。
- **クリック＆待機 (`_click_and_wait`)**: 操作前後に `_human_pause()` を挟みつつ `.first.click()`、`wait_for_load_state("networkidle")` を順に実行し、遷移後は `_check_robot_detection()` を呼び出す。
- **復旧ナビゲーション (`_navigate_back_to_style_list_after_error`)**: 通常ナビゲーションが失敗した場合に直接URL遷移へフォールバックするロジックを提供する。

### **3.3. 主要ステップメソッド**

### **3.3.1. `step_login`**

1. `page.goto()` でログインURLへ移動し、ロボット認証を即座に確認する。
2. `user_id_input` と `password_input` へ `fill()` で認証情報を入力し、`_click_and_wait()` で `login_button` を押下する。
3. 複数店舗アカウントの場合は `salon_list_table` の行を走査し、`salon_info` の `id` または `name` と一致するサロンを選択する。
4. `dashboard_global_navi` の表示を `wait_for_selector()` で確認しログイン成功を確定する。
5. ログイン直後に `_ensure_akamai_readiness(attempts=2, timeout_ms=10000)` を呼び出し、Bot Managerの検証状態を安定させる。

### **3.3.2. `step_navigate_to_style_list_page`**

- `run()` メソッドのループ開始前、およびエラー後の復旧時に呼び出される。
1. 通常ルートでは `_click_and_wait()` を2回呼び出し、掲載管理 → スタイル管理の順で画面遷移する。
2. ナビゲーションに失敗した場合は `use_direct_url=True` で呼び出し、現在のベースURLから `/CNB/draft/styleList/` へ直接遷移する。

### **3.3.3. `step_process_single_style`**

- `run()` メソッドのループ内でスタイル1件ごとに実行される。
1. **新規登録ページへ**: `_click_and_wait()` で `style_form.new_style_button` を押下し、遷移後のロボット認証を確認する。
2. **画像アップロード**:
    - 事前に `_ensure_akamai_readiness()` と `_human_pause()` を挟み、通信を安定化させる。
    - `upload_area` をクリックしモーダルを開いた後、`file_input.set_input_files(image_path)` で画像を選択する。
    - `submit_button_active` が `visible` になるまで `wait_for()` し、`page.expect_response()` で `imgUpload` エンドポイントを監視しながら送信ボタンをクリックする。
    - レスポンスステータスが200以外の場合や `_abck` Cookie が異常値の場合は例外を投げ、必要に応じて `_last_failed_upload_reason` をログへ出力する。
    - モーダルが閉じるまで待機し、エラーダイアログが表示された際はメッセージを取得して `StylePostError` を送出する。
3. **フォーム入力**: スタイリスト名、コメント、スタイル名、メニュー詳細を順に入力し、カテゴリ・長さは性別ごとにラジオボタンとセレクトボックスを組み合わせて設定する。
4. **クーポン選択**: モーダルを開いたのち、`item_label_template` を利用した `locator` で対象クーポンを選択し、設定ボタンで確定する。
5. **ハッシュタグ入力**: カンマ区切りで分割したタグを `input_area` に入力し、`add_button` をクリックするたびに `_human_pause()` で反映を待つ。
6. **登録完了**: `_click_and_wait()` で `register_button` を押下し、「登録が完了しました。」の表示を確認した後、`back_to_list_button` で一覧画面へ戻る。戻り操作が失敗した場合は `_navigate_back_to_style_list_after_error()` が後続でリトライする。

### **3.4. 統括メソッド (`run`)**

1. `progress_callback` 引数を `self.progress_callback` に保存する。
2. `_start_browser()` を呼び出してブラウザを起動する。
3. `step_login()` を実行する。失敗した場合はスクリーンショットを撮影し、処理を中断する。
4. 入力データファイル（CSV/Excel）をPandasで読み込む。
5. `step_navigate_to_style_list_page()` を実行する。失敗した場合はスクリーンショットを撮影し、処理を中断する。
6. 読み込んだデータを1行ずつループ処理する。
    - **ループ開始時に進捗コールバック呼び出し**（try-exceptの外）：中止リクエストのチェック。
    - ループ内で `step_process_single_style()` を呼び出す。
    - `step_process_single_style()` が失敗した場合は、スクリーンショットを撮影し、エラーログを出力して**次の行の処理へ進む (continue)**。
    - 成功時は進捗コールバックで完了件数を更新。
7. `finally` 句で `_close_browser()` を必ず呼び出し、ブラウザを終了させる。

### **3.5. 進捗コールバックの仕様**

進捗コールバック関数は以下のシグネチャを持つ：

```python
def progress_callback(completed: int, total: int, error: dict = None):
    """
    進捗更新とエラー記録

    Args:
        completed: 完了件数（処理中の場合は現在のインデックス）
        total: 総件数
        error: エラー情報（任意）。以下のキーを含む辞書：
            - row_number: エラー行番号（Excelの行番号、ヘッダー考慮）
            - style_name: スタイル名
            - field: エラーフィールド
            - reason: エラー理由
            - screenshot_path: スクリーンショットパス

    Raises:
        Exception: タスクが中止された場合（"タスクが中止されました"）
    """
```

**進捗コールバックの重要な役割**:
- データベースのタスクステータスをチェックし、`CANCELLING` ステータスの場合は例外を発生させる
- これにより、ユーザーによるタスク中止リクエストに即座に応答できる

---

### **4. `selectors.yaml` の役割**

本クラスは、すべてのセレクタを `selectors.yaml` から動的に読み込むことを前提とする。これにより、SALON BOARDのUIが変更された場合でも、**Pythonコードを一切変更することなく**、YAMLファイルの修正のみで対応が可能となる。開発者は、本仕様書で定義されたセレクタキー（例: `login.user_id_input`）を用いて、辞書からセレクタを取得して使用する。

### **4.1. 現在のセレクタ構造**

```yaml
# ==============================================================================
# SALON BOARD スタイル自動投稿 - セレクタ設定ファイル
# ==============================================================================

login:
  url: "https://salonboard.com/login/"
  user_id_input: "input[name='userId']"
  password_input: "#jsiPwInput"
  login_button: "a.common-CNCcommon__primaryBtn.loginBtnSize"
  login_form: "#idPasswordInputForm"
  dashboard_global_navi: "#globalNavi"

salon_selection:
  salon_list_table: "#biyouStoreInfoArea"
  salon_list_row: "#biyouStoreInfoArea > tbody > tr"
  salon_name_cell: "td.storeName"
  salon_id_cell: "td.mod_center"

navigation:
  keisai_kanri: "#globalNavi > ul.common-CLPcommon__globalNavi > li:nth-child(2) > a"
  style: "a.moveBtn[href='/CNB/draft/styleList/']"

style_form:
  new_style_button: "img[alt='スタイル新規追加']"
  # 画像アップロード関連
  image:
    upload_area: "#FRONT_IMG_ID_IMG"
    modal_container: ".imageUploaderModalContainer"
    file_input: "input#formFile"
    submit_button_active: "input.imageUploaderModalSubmitButton.isActive"
  # フォーム項目
  stylist_name_select: "#stylistCheckCd"
  stylist_comment_textarea: "#stylistCommentTxt"
  style_name_input: "#styleNameTxt"
  category_ladies_radio: "#styleCategoryCd01"
  category_mens_radio: "#styleCategoryCd02"
  length_select_ladies: "#ladiesHairLengthCd"
  length_select_mens: "#mensHairLengthCd"
  menu_checkbox_template: "input[name='frmStyleEditStyleDto.menuContentsCdList'][value='{value}']"
  menu_detail_textarea: "#menuDetailTxt"
  # クーポン関連
  coupon:
    select_button: "a.jsc_SB_modal_single_coupon"
    modal_container: ".couponContents.jsc_SB_modal_target"
    # :has-text() はPlaywrightの強力なセレクタで、指定テキストを持つ要素を絞り込める
    item_label_template: "label:has-text('{name}')"
    setting_button: "a.jsc_SB_modal_setting_btn:not(.is_disable)"
  # ハッシュタグ関連
  hashtag:
    input_area: "#hashTagTxt"
    add_button: "button.jsc_style_edit-editCommon__tag--addBtn:not(.common-CNBcommon__secondaryBtn--disabled)"
  # 登録・完了関連
  register_button: "img[alt='登録']"
  complete_text: "text=登録が完了しました。"
  back_to_list_button: "input[value='スタイル掲載情報一覧画面へ']"

robot_detection:
  selectors:
    - "iframe[src*='recaptcha']"
    - "div.g-recaptcha"
    - "div#recaptcha"
    - ".captcha-container"
    - ".capy-captcha"
    - "form#captchaForm"
    - "input[name='capy_captchakey']"
  texts:
    - "画像認証"

widget:
  selectors:
    - ".karte-widget__container"
    - "[class*='_reception-Skin']"
    - "[id^='karte-']"
```

### **4.2. セレクタ実装の重要な注意事項**

#### **画像アップロードの実装**

画像アップロード処理では、Akamaiセッションの安定化とレスポンス監視を組み合わせた以下の実装を行う：

```python
# 画像ファイル選択
self.page.locator(form_config["image"]["file_input"]).set_input_files(image_path)

# 送信ボタンが有効化されるまで待機（.isActive クラス付与を監視）
submit_button = self.page.locator(form_config["image"]["submit_button_active"])
submit_button.wait_for(state="visible", timeout=self.TIMEOUT_IMAGE_UPLOAD)

# imgUpload リクエストのレスポンスを監視しながら送信
def upload_predicate(response):
    return "/CNB/imgreg/imgUpload/" in response.url

with self.page.expect_response(upload_predicate, timeout=self.TIMEOUT_IMAGE_UPLOAD) as upload_waiter:
    submit_button.evaluate("el => el.click()")
upload_response = upload_waiter.value

# モーダルが閉じるのを待つ
self.page.wait_for_selector(
    form_config["image"]["modal_container"],
    state="hidden",
    timeout=self.TIMEOUT_IMAGE_UPLOAD,
)
```

**理由**:
- `.isActive` クラスの表示を待つことで、フロントエンドがファイル読み込みを完了したことを保証する。
- `expect_response` でAPIレスポンスを捕捉し、ステータスコードや本文をログに残すことで通信エラー時のトラブルシュートが容易になる。
- モーダルのクローズ待機にタイムアウトを設け、未完了時は `_abck` Cookie の状態を含めた詳細なエラーを発生させる。

---

### **5. エラーハンドリング**

### **5.1. エラーの種類**

1. **致命的エラー**: ブラウザ起動失敗、ログイン失敗、データファイル読み込み失敗など。処理を即座に中断する。
2. **スタイルごとのエラー**: 個別スタイルの処理失敗。エラーを記録して次のスタイルへ継続する。
3. **中止リクエスト**: ユーザーによるタスク中止。進捗コールバック内で検出し、例外を発生させる。

### **5.2. エラー記録**

すべてのエラーは以下の情報を含む：
- `row_number`: エラー発生行（Excelの行番号）
- `style_name`: スタイル名
- `field`: エラーフィールド
- `reason`: エラー理由
- `screenshot_path`: エラー時のスクリーンショットパス

### **5.3. スクリーンショット**

エラー発生時、`_take_screenshot()` メソッドが自動的に呼び出され、以下の形式でファイル名が生成される：

```
error-row{行番号}-{YYYYMMDDHHmmss}.png
fatal-error-{YYYYMMDDHHmmss}.png
```

---

### **6. タスク中止機能**

### **6.1. 中止フロー**

1. ユーザーがUIで「中止」ボタンをクリック
2. APIエンドポイントがタスクステータスを `CANCELLING` に更新
3. 進捗コールバック内で `CANCELLING` ステータスを検出
4. `Exception("タスクが中止されました")` を発生させる
5. `run()` メソッドの except 句でキャッチされ、処理が停止
6. タスクステータスが `FAILURE` に更新される

### **6.2. 即時中止（Force Termination）**

APIレベルでは、Celeryの `control.revoke()` メソッドを使用した強制終了もサポートされている：

```python
celery_app.control.revoke(str(task_id), terminate=True, signal='SIGKILL')
```

これにより、ハングしたタスクも確実に停止できる。

---

### **7. Docker環境での実行**

### **7.1. ブラウザバイナリ管理**

- デフォルトでは `channel="chrome"` を指定しているため、ホスト環境またはDockerイメージに Google Chrome Stable をインストールしておくことを推奨する。
- Chrome が存在しない場合は Playwright 同梱の Chromium を自動的にフォールバックとして利用する。コンテナビルド時には `playwright install chromium` を実行しておくと確実。
- 追加の起動フラグは不要だが、GPU を利用できない環境では `--disable-gpu` を `launch_kwargs` に渡すと安定するケースがある。

### **7.2. メモリ / パフォーマンスの目安**

- ブラウザ起動: 約3〜4秒（Chromeチャンネル起動時）。
- スタイル1件の処理: 約10〜50秒（画像アップロードサイズとAkamai検証状況に依存）。
- Dockerで実行する場合は `PLAYWRIGHT_BROWSERS_PATH=0` を設定し、ブラウザキャッシュをイメージ内に固定化すると起動時間が安定する。

---

### **8. 実装チェックリスト**

実装時、以下の点を確認すること：

- [ ] ChromeチャンネルのChromium起動を優先し、フォールバック時も自動化検知対策（User-Agent, webdriver隠蔽）を維持
- [ ] デスクトップChrome相当のコンテキスト（1366x768, desktop UA, is_mobile=False, has_touch=False）と `playwright_stealth` を適用
- [ ] デフォルトタイムアウトを180秒に設定し、主要操作前後に `_human_pause()` を挿入
- [ ] 画像アップロードで `.isActive` の可視化を待ち、`expect_response` で `imgUpload` API を監視
- [ ] 進捗コールバックをtry-exceptの外で呼び出し
- [ ] エラー時のスクリーンショット撮影を実装
- [ ] finally句でブラウザを必ず終了
- [ ] アップロードファイルのクリーンアップを実装
- [ ] ロボット認証検出機能を実装
- [ ] 中止リクエストへの応答を実装
