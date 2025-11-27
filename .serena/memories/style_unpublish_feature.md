# スタイル非掲載機能メモ

## 概要
- 投稿タスクと別ページ `/unpublish` を新設。ヘッダーメニューに「スタイル非掲載」を追加。
- UI: SALON BOARD設定選択、HotPepperサロンURL入力→「件数取得」でスタイル数をスクレイピングし、範囲入力の上限を自動設定。開始/終了番号・除外番号（カンマ区切り）指定で非掲載タスクを起動。
- 進捗/キャンセル/エラーレポートは既存タスクAPIと共通表示。

## バックエンド
- 新API `GET /api/v1/tasks/style-count`: HotPepperのスタイル件数取得。hostnameを`beauty.hotpepper.jp`に厳格一致、ユーザー情報付きURLを拒否。正規表現で`numberOfResult`から件数抽出。
- 新API `POST /api/v1/tasks/style-unpublish`: SALON BOARD設定、サロンURL、開始/終了、除外番号で非掲載タスクをキューイング。`salon_id/salon_name`を渡し複数店舗アカウントで店舗選択可能。
- 非掲載ロジック `app/services/style_unpublisher.py`: Playwrightで一覧を巡回し範囲・除外を評価、非掲載クリックを最大3回リトライ。スタイル件数は`/style-count`で取得。
- SSRF対策: style-countのバリデーションを厳格化。

## テスト
- `tests/api/v1/test_tasks.py` に style-count成功/ドメイン不正/SSRF風URL拒否のテストを追加（`-k style_count`）。

## ドキュメント
- READMEにスタイル非掲載手順を追記。
- `docs/api_specification.md` に style-count / style-unpublish 概要を補足。
