## **Playwright実装詳細仕様書**

### **1. 目的**

本仕様書は、Webアプリケーションのバックグラウンドタスクとして実行される クラスの構造、メソッド、および処理フローを詳細に定義する。開発者は本仕様書に基づき、SALON BOARDの画面操作を自動化するPythonコードを実装する。

### **2. クラス設計**

### **2.1. クラス名**

`SalonBoardStylePoster`(変更可)

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
| `browser` | `Browser` | 起動したブラウザのインスタンス（Firefox）。 |
| `page` | `Page` | 現在操作中のブラウザページのインスタンス。 |
| `progress_callback` | `Callable` | （オプション）進捗を呼び出し元に通知するためのコールバック関数。 |

### **2.4. 外部インターフェース（Public Methods）**

- `__init__(self, selectors, screenshot_dir, headless, slow_mo)`:
クラスを初期化する。
- `run(self, user_id, password, data_filepath, image_dir, salon_info)`:
自動投稿の全プロセスを実行するエントリーポイント。内部でブラウザの起動から終了までを管理する。

### **3. 内部実装仕様**

### **3.1. 初期化と終了処理 (`_start_browser`, `_close_browser`)**

- **ブラウザ起動 (`_start_browser`)**:
    - `sync_playwright().start()` でPlaywrightを起動する。
    - `playwright.firefox.launch()` でFirefoxブラウザを起動する。
    - `browser.new_context()` で新しいブラウザコンテキストを作成し、以下の自動化検知対策を**必ず**適用する。
        - **User-Agent**: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0` に固定する。
        - **WebDriverフラグ**: `context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")` を実行し、`navigator.webdriver` プロパティを隠蔽する。
    - `context.new_page()` で新しいページを作成し、`self.page` に格納する。
    - `page.set_default_timeout()` で、デフォルトのタイムアウトを `180000` ミリ秒（3分）に設定する。
- **ブラウザ終了 (`_close_browser`)**:
    - `browser.close()` と `playwright.stop()` を呼び出し、リソースを安全に解放する。

### **3.2. 汎用ヘルパーメソッド**

- **スクリーンショット撮影 (`_take_screenshot`)**:
    - エラー発生時に呼び出される。
    - 現在の日時を含む一意のファイル名を生成し、指定された `screenshot_dir` に `page.screenshot()` でPNG画像を保存する。
- **ロボット認証検出 (`_check_robot_detection`)**:
    - ページ遷移のたびに呼び出される。
    - `selectors.yaml` の `robot_detection` セクションに定義されたテキスト（`画像認証`など）やセレクタ（`div.g-recaptcha`など）がページ内に存在するかを `page.locator().count()` で確認する。
    - いずれかが検出された場合は `True` を返し、エラーログを出力する。
- **クリック＆待機 (`_click_and_wait`)**:
    - ページ遷移を伴うクリック操作で汎用的に使用する。
    - 引数で渡されたセレクタに対し、`.first.click()` を実行する。`.first` を使用することで、セレクタが複数の要素に一致した場合でもエラーにならず、最初の要素を確実にクリックできる。
    - クリック後、`page.wait_for_load_state("networkidle")` を実行し、ネットワーク通信が落ち着くまで待機する。これにより、次の操作がページ読み込み完了前に行われることを防ぐ。
    - 待機完了後、`_check_robot_detection()` を呼び出す。

### **3.3. 主要ステップメソッド**

### **3.3.1. `step_login`**

1. `page.goto()` でログインURLへ移動する。
2. `_check_robot_detection()` を実行する。
3. `user_id_input` と `password_input` セレクタの要素に `fill()` でIDとパスワードを入力する。
4. `_click_and_wait()` を使用して `login_button` をクリックする。
5. **サロン選択ロジック**:
    - `salon_list_table` セレクタの存在を確認する。存在する場合、複数店舗アカウントと判断する。
    - `salon_list_row` で全店舗の行を取得し、ループ処理を行う。
    - 各行から `salon_id_cell` と `salon_name_cell` のテキストを取得する。
    - 引数 `salon_info` の `id` または `name` と一致する行を探し、その行のリンク (`a` タグ) をクリックする。
    - `page.wait_for_load_state("networkidle")` でダッシュボードへの遷移を待つ。
6. `dashboard_global_navi` セレクタの存在を `wait_for_selector()` で確認し、ログイン成功を確定する。

### **3.3.2. `step_navigate_to_style_list_page`**

- `run()` メソッドの**ループ開始前に一度だけ**呼び出される。
1. `_click_and_wait()` を使用して `navigation.keisai_kanri` （掲載管理）をクリックする。
2. `_click_and_wait()` を使用して `navigation.style` （スタイル管理）をクリックする。

### **3.3.3. `step_process_single_style`**

- `run()` メソッドの**ループ内でスタイル1件ごと**に呼び出される。
1. **新規登録ページへ**: `_click_and_wait()` を使用して `style_form.new_style_button` （スタイル新規追加）をクリックする。
2. **画像アップロード**:
    - `style_form.image.upload_area` をクリックしてモーダルを開く。
    - `wait_for_selector()` で `modal_container` の表示を待つ。
    - `file_input` に `set_input_files()` で画像パスを設定する。
    - `submit_button_active` の表示を待ち、クリックする。
    - `wait_for_selector(state="hidden")` でモーダルが閉じるのを待つ。
3. **フォーム入力**:
    - **スタイリスト名**: `stylist_name_select` に `select_option(label=...)` で選択。
    - **テキスト入力**: `stylist_comment_textarea`, `style_name_input`, `menu_detail_textarea` に `fill()` で入力。
    - **カテゴリ/長さ**: `category_..._radio` をクリック後、対応する `length_select_...` を `select_option(label=...)` で選択。
4. **クーポン選択**:
    - `coupon.select_button` をクリックしてモーダルを開く。
    - `coupon.modal_container` の表示を待つ。
    - `coupon.item_label_template` にクーポン名を埋め込んだ動的セレクタを生成し、`.first.click()` で該当クーポンを選択する。
    - `coupon.setting_button` をクリックする。
    - モーダルが閉じるのを待つ。
5. **ハッシュタグ入力**:
    - カンマ区切りのハッシュタグを分割し、ループ処理を行う。
    - `hashtag.input_area` に `fill()` でタグを入力。
    - `hashtag.add_button` をクリック。
    - `time.sleep(0.5)` で反映を待つ。
6. **登録完了**:
    - `_click_and_wait()` で `register_button` をクリックする。
    - `wait_for_selector()` で `complete_text` （「登録が完了しました。」）の表示を待つ。
    - `_click_and_wait()` で `back_to_list_button` をクリックし、スタイル一覧画面に戻る。

### **3.4. 統括メソッド (`run`)**

1. `_start_browser()` を呼び出してブラウザを起動する。
2. `step_login()` を実行する。失敗した場合はスクリーンショットを撮影し、処理を中断する。
3. 入力データファイル（CSV/Excel）をPandasで読み込む。
4. `step_navigate_to_style_list_page()` を実行する。失敗した場合はスクリーンショットを撮影し、処理を中断する。
5. 読み込んだデータを1行ずつループ処理する。
    - ループ内で `step_process_single_style()` を呼び出す。
    - `step_process_single_style()` が失敗した場合は、スクリーンショットを撮影し、エラーログを出力して**次の行の処理へ進む (continue)**。
    - ただし、回復不能なエラー（再ナビゲーションの失敗など）の場合は、ループを**中断する (break)**。
6. `finally` 句で `_close_browser()` を必ず呼び出し、ブラウザを終了させる。

---

### **4. `selectors.yaml` の役割**

本クラスは、すべてのセレクタを `selectors.yaml` から動的に読み込むことを前提とする。これにより、SALON BOARDのUIが変更された場合でも、**Pythonコードを一切変更することなく**、YAMLファイルの修正のみで対応が可能となる。開発者は、本仕様書で定義されたセレクタキー（例: `login.user_id_input`）を用いて、辞書からセレクタを取得して使用する。

```yaml
# ==============================================================================
# SALON BOARD スタイル自動投稿 - セレクタ設定ファイル
# ==============================================================================

login:
  url: "https://salonboard.com/login/"
  user_id_input: "input[name='userId']"
  password_input:
    primary: "#jsiPwInput"
  login_button:
    primary: "a.common-CNCcommon__primaryBtn.loginBtnSize"
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
    - "img[alt*='認証']"
    - "form[action*='auth']"
  texts:
    - "画像認証"
    - "認証画像"

widget:
  selectors:
    - ".karte-widget__container"
    - "[class*='_reception-Skin']"
    - "[id^='karte-']"
```