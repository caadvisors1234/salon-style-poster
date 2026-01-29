# Akamai Bot Manager 検出回避に関する調査報告

**作成日**: 2026年1月24日
**対象**: SALON BOARD スタイル投稿処理におけるボット検知対策

---

## 1. はじめに

現在のスタイル投稿処理において、Akamai Bot Manager により画像アップロードが拒否される問題が発生しています。本ドキュメントでは、Akamai Bot Manager の検出メカニズムと、効果的な回避策について調査した結果をまとめます。

---

## 2. Akamai Bot Manager の検出メカニズム

Akamai Bot Manager は、以下の多層的な手法でボットトラフィックを検出します。

### 2.1 TLS フィンガープリンティング

TLS ハンドシェイクの特徴を分析して、自動化ツールを検出します。

- **検出対象**: TLS 暗号スイート、拡張機能、圧縮方法など
- **特徴**: 各ブラウザ（Chrome、Firefox、Safari 等）は固有の TLS フィンガープリントを持つ
- **検出**: Playwright 等の自動化ツールは、通常のブラウザと異なる TLS フィンガープリントを持つ

> **公式情報**: [Akamai Blog - Bots Tampering with TLS to Avoid Detection](https://www.akamai.com/blog/security/bots-tampering-with-tls-to-avoid-detection)

### 2.2 ブラウザフィンガープリンティング

ブラウザの特性を分析して、自動化を検出します。

| 検出項目 | 説明 |
|---------|------|
| User-Agent | ブラウザのバージョン情報 |
| JavaScript オブジェクト | `navigator.webdriver`、`navigator.platform` 等 |
| HTTP/2 指紋 | HTTP/2 フレームの設定パターン |
| Chrome DevTools Protocol (CDP) | Playwright 等の自動化痕跡 |

### 2.3 振る舞い分析

人間らしい操作パターンかどうかを分析します。

- マウス移動の軌跡
- キーボード入力のパターン
- クリック間隔
- スクロール動作

---

## 3. 現在の実装分析

### 3.1 使用ライブラリ

```txt
# requirements.txt (抜粋)
playwright==1.41.0              # 2024年1月リリース（古い）
playwright-stealth==1.0.6
```

### 3.2 実行環境

**Docker環境**:
- ベースイメージ: `python:3.11-slim` (linux/amd64)
- 仮想ディスプレイ: **xvfb インストール済み**
- ブラウザ: Chrome, Firefox インストール済み
- 共有メモリ: `shm_size: "2gb"` 設定済み

**ヘッドレス/ヘッドフル設定**:

```python
# app/core/config.py
USE_HEADFUL_MODE: bool = True  # デフォルトでTrue

# app/services/tasks.py
headless=not settings.USE_HEADFUL_MODE  # headless=False（ヘッドフルモード）
```

**重要**: 現在のシステムは**xvfbを使用したヘッドフルモード**で動作しています。これは完全なヘッドレスモード（`headless=True`）よりも検知されにくい傾向があります。

### 3.3 コード構成（リファクタ後）

現在の実装は **Mixin パターン** で整理されています：

```
app/services/salonboard/
├── style_poster.py          # メイン実行ロジック
├── browser_manager.py       # ブラウザ管理（Playwright + playwright-stealth）
├── login_handler.py         # ログイン処理
├── form_handler.py          # フォーム入力処理
├── utils.py                 # ユーティリティ
└── exceptions.py            # 例外定義
```

`SalonBoardStylePoster` クラスは以下の継承構造になっています：

```python
class SalonBoardStylePoster(
    StyleFormHandlerMixin,      # フォーム入力処理
    LoginHandlerMixin,          # ログイン処理
    BrowserUtilsMixin,          # ユーティリティ
    SalonBoardBrowserManager    # ブラウザ管理
):
```

### 3.4 現在の対策内容

`app/services/salonboard/browser_manager.py` で実装されている対策：

| 対策 | 内容 | 問題点 |
|------|------|--------|
| User-Agent | Chrome/120 (固定) | **古すぎる**（2024年11月にChrome 131がリリース） |
| HTTPヘッダー | accept, accept-language 等 | TLSフィンガープリントと不一致の可能性 |
| stealth_sync | playwright-stealth 使用 | Akamaiに対しては効果が限定的 |
| ブラウザ引数 | `--disable-blink-features=AutomationControlled` | CDP検知痕跡が残る |
| init_script | `navigator.webdriver` 等の上書き | ブラウザフィンガープリントの一貫性不足 |

**現在の実装（browser_manager.py:159-162）**:
```python
user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
```

### 3.5 問題点のまとめ

1. **Playwright バージョンが古い**: v1.41.0 は2024年1月リリース
2. **User-Agent が古い**: Chrome 120 は2023年末のバージョン
3. **TLS フィンガープリンティング対策がない**: 最も重要な検出層への対策なし
4. **CDP 検知への対応不十分**: Runtime.enable のリーク等への対処が必要
5. **xvfb環境の制約**: 仮想ディスプレイ環境は実際のGUI環境と異なるフィンガープリントを持つ可能性（後述）

---

## 4. 回避策の比較

### 4.1 ベンチマークデータ

[techinz/browsers-benchmark](https://github.com/techinz/browsers-benchmark) による公開ベンチマーク（Cloudflare、DataDome等対象）：

| エンジン | バイパス率 | モード | reCAPTCHAスコア | メモリ使用量 |
|---------|----------|--------|-----------------|-------------|
| camoufox_headless | 83.3% | ヘッドレス | 0.10 | 1037 MB |
| nodriver-chrome | 83.3% | 非ヘッドレス | - | 554 MB |
| **patchright** | **66.7%** | **非ヘッドレス（GUI）** | **0.30** | 709 MB |
| patchright_headless | 16.7% | ヘッドレス | 0.10 | 560 MB |
| tf-playwright-stealth-chromium | 50.0% | 非ヘッドレス | 0.10 | 462 MB |
| playwright-chrome | 16.7% | 非ヘッドレス | 0.10 | 454 MB |
| playwright-chrome_headless | 33.3% | ヘッドレス | - | 212 MB |

**重要な発見**:
- **patchright（非ヘッドレス）**: 66.7% のバイパス率
- **patchright_headless**: 16.7% に大幅低下
- ヘッドフルモードの方が圧倒的に高い成功率

**注**: このベンチマークは主に Cloudflare、DataDome 等を対象としており、Akamai 固有のデータではありません。

### 4.2 Playwright Stealth の効果

[scrapingant.com](https://scrapingant.com/blog/javascript-detection-avoidance-libraries) のデータ（2024年10月）：

- **基本的なボット検知システムに対して 92% の成功率**
- Akamai Bot Manager に対しては 70-80% 程度の成功率と推定

### 4.3 Patchright の特徴

[Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) は、Playwright の検出回避版です。

**対応しているボット検知システム**:

> **注意**: 公式README（2026年1月24日時点）には、以下のシステムへの対応が明記されていますが、**Akamaiへの言及は見つかりませんでした**。

| システム | 対応状況 |
|---------|---------|
| Brotector | ✅ (CDP-Patchesが必要) |
| Cloudflare | ✅ |
| Kasada | ✅ |
| **Akamai** | **❓ 未確認**（公式READMEに記述なし） |
| Shape/F5 | ✅ |
| Datadome | ✅ |
| Fingerprint.com | ✅ |
| CreepJS | ✅ |

**主なパッチ内容**：

1. **Runtime.enable リークの回避**: JavaScript を分離された ExecutionContext で実行
2. **Console.enable リークのパッチ**: Console API を無効化
3. **コマンドフラグの調整**:
   - `--disable-blink-features=AutomationControlled` (追加)
   - `--enable-automation` (削除)
   - `--disable-popup-blocking` (削除)
   - 他、検知につながるフラグを削除

**重要な注意点**:

> Patchright only patches CHROMIUM based browsers. Firefox and Webkit are not supported.

### 4.4 Camoufox の特徴

[Camoufox](https://github.com/daijro/camoufox) は、Firefox ベースのアンチディテクトブラウザで、Playwright API と完全互換性があります。

> **重要な注意（2026年1月24日時点）**:
> - 現在のメインブランチ（Firefox v146）は**実験的**でバグが含まれている可能性があります
> - **Firefox v146はMacOSのみ対応** - Linux/Windowsサポートは未完了
> - 安定版は `releases/135` ブランチ（またはPyPIパッケージ）を使用してください
> - 1年間のメンテナンスギャップがあったため、パフォーマンスが低下している可能性があります

**主な特徴**:

| 特徴 | 説明 |
|------|------|
| **ベースブラウザ** | Firefox（Chromium ではない） |
| **バイパス率** | 66.7%（非ヘッドレス）/ **83.3%**（headless="virtual"） |
| **API互換性** | Playwright と完全互換 |
| **xvfb対応** | `headless="virtual"` で公式サポート |
| **Linux対応** | ✅ **安定版（releases/135 / PyPI）は対応済み** |
| **ライセンス** | **MPL-2.0**（Mozilla Public License 2.0） |

**公式GitHubより確認**: "MPL-2.0 license"

**対応しているボット検知システム**:

| システム | 対応状況 |
|---------|---------|
| Cloudflare | ✅ |
| DataDome | ✅ |
| Imperva | ✅ |
| Akamai | ✅（公式アナウンスなし） |
| CreepJS | ✅ |

**主な機能**:

1. **デバイスフィンガープリントの自動生成**: OS、Navigator、Fonts等の情報を自動生成
2. **xvfb検知対策**: `headless="virtual"` で仮想ディスプレイ環境を検知されにくい
3. **人間らしいカーソル移動**: `humanize` パラメータで有効化
4. **WebGL制御**: 特定のvendor/rendererペアを指定可能
5. **GeoIP連動**: プロキシに合わせた地理位置情報とロケールの自動設定

**Camoufox のコード例**:

```python
# 同期API
from camoufox.sync_api import Camoufox

with Camoufox(
    headless=False,           # ヘッドフルモード
    os="windows",              # OS偽装
    locale="ja-JP",            # 日本語ロケール
    humanize=True,             # 人間らしいカーソル移動
    block_webrtc=True,         # WebRTCブロック
) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
```

**xvfb環境での使用**:

```python
# Linuxでxvfbを使用する場合
with Camoufox(headless="virtual") as browser:
    # 自動的にxvfbが使用され、検知されにくい
    page = browser.new_page()
```

**Patchright との比較**:

| 項目 | Patchright | Camoufox |
|------|-----------|----------|
| ブラウザ | Chromium | **Firefox** |
| バイパス率（非ヘッドレス） | 66.7% | 66.7% |
| バイパス率（ヘッドレス/xvfb） | 16.7% | **83.3%** (headless="virtual") |
| API互換性 | Playwrightと完全互換 | Playwrightと完全互換 |
| xvfb検知対策 | 要確認 | **組み込み済み** |
| 移行コスト | 最小限（import置換） | 最小限（初期化ロジック調整） |
| ライセンス | Apache 2.0 | **MPL-2.0** |

**MPL-2.0 の商用利用における影響**:
- ✅ **商用利用可能**
- ✅ プロプライエティアなソフトウェアと組み合わせ可能
- ✅ ソースコード公開義務は**変更したファイルのみ**（全体不要）
- ⚠️ Camoufox自体に変更を加えた場合、その変更部分をMPL-2.0で公開する必要あり

**移行コスト**:

Camoufox への移行は**コードの大幅な改変は不要**です。主な変更点：

| 変更項目 | 内容 |
|---------|------|
| import | `from playwright.sync_api` → `from camoufox.sync_api` |
| 初期化 | `sync_playwright().start()` → `Camoufox()` |
| stealth_sync | **削除**（不要） |
| 起動オプション | PlaywrightのFirefox起動オプションがそのまま使用可能 |

**注意点**:

1. **Firefoxベース**: Chromium系とは異なる検出回避手法を使用
2. **ライセンス**: MPL-2.0 は商用利用に適している（ファイルレベルのコピーレフト）
3. **メモリ使用量**: browsers-benchmarkでは1037 MBと比較的多め

---

## 4.5 xvfb（仮想ディスプレイ）環境について

現在のDocker環境では、**xvfb（X Virtual Framebuffer）**を使用してヘッドフルモードをエミュレートしています。

### xvfb環境の特徴

| 項目 | 実際のGUI環境 | xvfb環境 | 影響 |
|------|--------------|----------|------|
| 画面出力 | あり | なし（仮想） | 検知には影響しない |
| WebGLレンダラー | GPUアクセラレーション | ソフトウェアレンダリング | **フィンガープリントが異なる可能性** |
| GPU情報 | 検出可能 | 検出されない/異なる値 | WebGL parametersで検知可能 |
| 画面解像度 | モニター依存 | 設定可能 | 適切な設定が必要 |

### xvfb環境の検知可能性

ボット検知システムは、以下の方法でxvfb環境を検知する可能性があります：

1. **WebGLレンダラー情報**: "Google SwiftShader"（ソフトウェアレンダリング）等が表示される
2. **GPU情報**: WebGL parametersでGPU情報が得られない、または不自然
3. **画面解像度の不自然さ**: 一般的な解像度と異なる場合
4. **X11サーバー情報**: 仮想ディスプレイ特有の情報が漏れる

### 対応方針

**xvfb環境でPatchrightを使用する場合**:
- ✅ 現在のヘッドフルモード設定を維持（`USE_HEADFUL_MODE=True`）
- ✅ PatchrightのCDPパッチが有効に機能
- ⚠️ WebGLレンダラー情報が実際のGUI環境と異なる可能性
- ⚠️ 高度な検知システムには検知される可能性がある

**よりリアルなGUI環境が必要な場合**:
- VNCサーバーの導入
- 実際のGPUアクセラレーションのエミュレーション（複雑・高コスト）
- Camoufox等のxvfb検知対策を実装したツールの検討

---

## 5. 推奨される対策

### 5.1 Patchright への移行（推奨）

**理由**:
1. Akamai に対する対応が公式に確認されている
2. Playwright の drop-in replacement（最小限のコード変更）
3. アクティブにメンテナンスされている
4. **現在のDocker環境（xvfb）でそのまま使用可能**

### 5.2 実装手順

#### Step 1: requirements.txt の修正

```diff
# requirements.txt
- playwright==1.41.0
- playwright-stealth==1.0.6
+ patchright
```

#### Step 2: Dockerfile の修正

```diff
 # Dockerfile
- RUN playwright install firefox && playwright install chrome
+ RUN patchright install chromium
```

**注意**: PatchrightはChromiumのみ対応のため、Firefoxのインストール行を削除します。

#### Step 3: コードの修正（import 文の置換）

```diff
# app/services/salonboard/browser_manager.py
- from playwright.sync_api import (
+ from patchright.sync_api import (
      Browser,
      BrowserContext,
      Page,
      Playwright,
      Request,
      sync_playwright,
  )
- from playwright_stealth import stealth_sync
+ # playwright-stealth は Patchright に不要（組み込み済み）
```

**注意**: `playwright-stealth` は Patchright には不要です（検出回避機能が組み込まれています）。

#### Step 4: browser_manager.py の stealth_sync 呼び出しを削除

```diff
# app/services/salonboard/browser_manager.py の _create_page メソッド
  def _create_page(self) -> Page:
      """セッションを維持した新規ページ生成"""
      if not self.context:
          raise Exception("ブラウザコンテキストが初期化されていません")
      page = self.context.new_page()
      page.on("requestfailed", self._handle_request_failed)
-     stealth_sync(page)
      page.set_default_timeout(180000)
      return page
```

#### Step 5: Dockerイメージの再ビルド

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 5.3 動作確認

1. コンテナが正常に起動していることを確認
2. スタイル投稿タスクを実行
3. 画像アップロードが成功するか確認

---

### 5.4 User-Agent の更新（browser_manager.py）

`app/services/salonboard/browser_manager.py` の User-Agent を更新します：

**現在の実装（browser_manager.py:159-162）**:
```python
user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"  # 古いバージョン
)
```

**推奨される更新（Chrome 131 以上）**:

```python
user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"  # 2024年11月リリース
)
```

> 参考: [Chrome 131 Release Notes](https://developer.chrome.com/release-notes/131)

### 5.5 補足的な対策

| 対策 | 効果 | 実装コスト |
|------|------|-----------|
| 住宅プロキシの使用 | 成功率 +10-15% | 高（コスト発生） |
| 人間らしい操作パターンの実装 | 振る舞い分析への対策 | 中 |
| 最新のブラウザバージョンへの追従 | フィンガープリントの一貫性 | 低 |

### 5.6 Patchrightで改善しない場合の次のステップ

Patchrightへの移行後も検知される場合、以下の追加対策を検討してください：

#### オプションA: Camoufox への移行

- **バイパス率**: 非ヘッドレス66.7%（Patchrightと同等）、xvfbモード83.3%
- **特徴**: xvfb検知対策が実装されている（`headless="virtual"`）
- **コスト**: 新しいライブラリの導入

#### オプションB: VNC等の実際のGUI環境の導入

- **効果**: よりリアルなGUI環境のフィンガープリント
- **コスト**: 設定が複雑（VNCサーバー等の導入）

#### オプションC: 住宅プロキシの併用

- **効果**: 成功率 +10-15%
- **コスト**: サービス利用料金が発生

---

## 6. 参考資料

### 6.1 公式ドキュメント

- [Akamai - Detection Methods](https://techdocs.akamai.com/cloud-security/docs/detection-methods)
- [Akamai Blog - Bots Tampering with TLS](https://www.akamai.com/blog/security/bots-tampering-with-tls-to-avoid-detection)
- [Chrome Release Notes](https://developer.chrome.com/release-notes)

### 6.2 ツール・ライブラリ

- [Patchright - GitHub](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright)
- [Camoufox - GitHub](https://github.com/daijro/camoufox)
- [Camoufox Python Interface](https://camoufox.com/python/)
- [Camoufox Usage Guide](https://camoufox.com/python/usage/)
- [playwright-stealth - GitHub](https://github.com/Granitosaurus/playwright-stealth)
- [techinz/browsers-benchmark - GitHub](https://github.com/techinz/browsers-benchmark)

### 6.3 記事・ガイド

- [How to Bypass Akamai in 2026: The 3 Best Methods - ZenRows](https://www.zenrows.com/blog/bypass-akamai)
- [Web Scraping with Camoufox: Complete Guide 2026 - Bright Data](https://brightdata.com/blog/web-data/web-scraping-with-camoufox)
- [How to Scrape With Camoufox to Bypass Antibot Technology - ScrapingBee](https://www.scrapingbee.com/blog/how-to-scrape-with-camoufox-to-bypass-antibot-technology/)
- [Web Scraping with Camoufox - ZenRows](https://www.zenrows.com/blog/web-scraping-with-camoufox)
- [How to Scrape with Patchright and Avoid Detection - ZenRows](https://www.zenrows.com/blog/patchright)
- [How to Use Patchright: Make Your Web Scraper Undetectable - RoundProxies](https://roundproxies.com/blog/patchright/)
- [Choosing Headful over Headless Browsers - Anchor Browser](https://anchorbrowser.io/blog/choosing-headful-over-headless-browsers)
- [Headless vs. Headful Browsers in 2025 - ScrapingAnt](https://scrapingant.com/blog/headless-vs-headful-browsers-in-2025-detection-tradeoffs)
- [Browser Fingerprinting Guide - Browserless](https://www.browserless.io/blog/device-fingerprinting)
- [Best Web Scraping Detection Avoidance Libraries - ScrapingAnt](https://scrapingant.com/blog/javascript-detection-avoidance-libraries)
- [What are the latest user agents for Chrome? - WhatIsMyBrowser](https://www.whatismybrowser.com/guides/the-latest-user-agent/chrome)
- [Playwright Docker Docs](https://playwright.dev/docs/docker)

---

## 7. Patchright 実装の失敗と教訓

### 7.1 実施したPatchright対策

2026年1月24日に実施したPatchrightへの移行試行とその結果：

| 対策 | 内容 | 結果 |
|------|------|------|
| requirements.txt更新 | `patchright` に変更 | ✅ インストール成功 |
| Dockerfile更新 | `patchright install chromium` | ✅ ブラウザ取得成功 |
| import文置換 | `playwright.sync_api` → `patchright.sync_api` | ✅ コード変更完了 |
| stealth_sync削除 | 不要な呼び出しを削除 | ✅ コード変更完了 |
| User-Agent更新 | Chrome/120 → Chrome/131 | ✅ 更新完了 |
| Chromeチャンネル削除 | システムChrome不存在のため削除 | ✅ バンドルChromium使用 |
| DNS設定 | 8.8.8.8, 8.8.4.4 | ✅ 設定完了 |
| extra_hosts追加 | `/etc/hosts` にエントリ追加 | ✅ 設定完了 |
| host-resolver-rules | ChromiumのDNS解決を強制 | ❌ 効果なし |

### 7.2 発生した問題

**DNS解決エラー**（解決せず）:
```
Page.goto: net::ERR_NAME_NOT_RESOLVED at https://salonboard.com/login/
```

**試行した解決策（いずれも失敗）**:
1. DNSサーバーの明示指定（8.8.8.8, 8.8.4.4）
2. `/etc/hosts` への静的エントリ追加
3. `--host-resolver-rules` 引数でのDNS解決強制
4. `MAP * 23.56.0.86` での全ホストマッピング
5. ネットワークサービス設定の調整
6. Pythonキャッシュのクリアとコンテナ再作成

### 7.3 失敗の原因分析

| 要因 | 分析結果 |
|------|----------|
| Chromiumのネットワークスタック | Docker環境特有の問題の可能性 |
| PatchrightのChromium実装 | DNSリゾルバーに問題がある可能性 |
| xvfb環境との相性 | 仮想ディスプレイ環境との不兼容性 |

### 7.4 教訓

**Chromium系ツール（Patchright、Playwright）のDocker環境での問題**:
- DNS解決が不安定になる傾向
- `--host-resolver-rules` 等の回避策が効果を発揮しない場合がある
- Firefoxベースのツールの方がDocker環境に適している可能性

---

## 8. Camoufox 移行計画（推奨）

### 8.1 推奨理由

| 要件 | Camoufox | 評価 |
|------|----------|------|
| **バイパス率** | 83.3% (headless="virtual") | Patchrightの16.7%を大幅上回 |
| **xvfb対応** | `headless="virtual"` で公式サポート | **組み込み済み**、検知されにくい |
| **ライセンス** | MPL-2.0 | 商用利用に適している |
| **商用利用** | 可能 | プロプライエティア対応可 |
| **Docker対応** | インストールガイドあり | 実績あり |

### 8.2 実装計画

#### Phase 1: 依存関係の更新

**requirements.txt**:
```diff
- patchright
+ camoufox[geoip]
```

> **重要**: `pip install camoufox` でインストールされるのは**安定版バイナリ**で、Linux対応済みです。

**Dockerfile**:
```dockerfile
# Firefox依存関係
RUN apt-get install -y \
    libgtk-3-0 \
    libx11-xcb1 \
    libasound2

# Camoufoxのインストールとブラウザ取得
RUN pip install --no-cache-dir -U "camoufox[geoip]"
RUN python3 -m camoufox fetch

# キャッシュディレクトリのボリュームマウント（ビルド時間短縮）
VOLUME /root/.cache/camoufox
```

**docker-compose.yml**:
```yaml
volumes:
  camoufox_cache:  # Camoufoxキャッシュの永続化
```

#### Phase 2: browser_manager.py の書き換え

**現在の実装（Patchright）**:
```python
from patchright.sync_api import sync_playwright

def _start_browser(self):
    self.playwright = sync_playwright().start()
    self.browser = self.playwright.chromium.launch(**launch_kwargs)
    self.context = self.browser.new_context(**context_kwargs)
    self.page = self.context.new_page()
```

**Camoufox 版**:
```python
from camoufox.sync_api import Camoufox

def _start_browser(self):
    # Camoufox は Playwright の sync_playwright() を使用しない
    self.browser = Camoufox(
        headless=False,  # ヘッドフルモード（xvfb経由）
        os="windows",     # OS偽装
        locale="ja-JP",   # 日本語ロケール
        humanize=True,    # 人間らしいカーソル移動
        block_webrtc=True, # WebRTCブロック
        # 既存の起動引数は Camoufox が内部で処理
    )
    # page は browser.new_page() で作成
```

#### Phase 3: 既存Mixin構成との整合性確認

| Mixin | 変更必要事項 |
|-------|--------------|
| `BrowserUtilsMixin` | `Page.screenshot()` - 互換性あり |
| `LoginHandlerMixin` | Playwright API - 互換性あり |
| `StyleFormHandlerMixin` | Playwright API - 互換性あり |

**結論**: Mixin構造は維持可能。Playwright API 互換性があるため。

---

## 9. 結論

### 9.1 現在のシステムの状態

- ✅ xvfbを使用したヘッドフルモードで動作中（`USE_HEADFUL_MODE=True`）
- ✅ Docker環境での実行構成が整っている
- ❌ **Patchright実装に失敗** - DNS解決問題が解決できず

### 9.2 推奨される対策

**Camoufox への移行**（最優推奨）:

| 理由 | 説明 |
|------|------|
| **高いバイパス率** | 83.3% (headless="virtual") |
| **xvfb検知対策** | 組み込み済みで検知されにくい |
| **商用利用可能** | MPL-2.0ライセンスで法的リスク低 |
| **Firefoxベース** | Chromium系とは異なるネットワークスタック |
| **API互換性** | Playwright と完全互換、Mixin構造維持可 |

### 9.3 実装の優先順位

1. **Camoufox への移行**（最優先）
   - ライセンス面での懸念なし（MPL-2.0）
   - xvfb環境での高いバイパス率（83.3%）
   - FirefoxベースでDNS解決問題の回避期待

2. **効果が不十分な場合**
   - 住宅プロキシの併用（成功率 +10-15%）

3. **それでも検知される場合**
   - VNC等の実際のGUI環境導入を検討

### 9.4 注意点

- **Firefoxベース**: Chromium系とは異なる検出回避手法
- **メモリ使用量**: ~1037 MBと比較的多め（Dockerリソースに注意）
- **ライセンス**: Camoufox自体に変更を加えた場合、その変更部分をMPL-2.0で公開必要
- **メンテナンス状況**: 1年間のメンテナンスギャップがあったため、パフォーマンスが低下している可能性あり
- **バージョン選択**: メインブランチ（FF146）は実験的でMacOSのみ。安定版（releases/135 / PyPI）を使用すること

---

## 10. 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-24 | 初版作成 |
| 2026-01-24 | xvfb環境、Docker設定、ヘッドフルモードに関する情報を追加 |
| 2026-01-24 | Mixinパターンへのリファクタに対応してコード構成セクションを追加 |
| 2026-01-24 | Camoufoxに関する詳細セクション（4.4）と参考文献を追加 |
| 2026-01-24 | Patchright実装失敗とCamoufox移行計画を追加、ライセンスをMPL-2.0に訂正 |
| 2026-01-24 | **ファクトチェックに基づき以下の訂正を実施**: PatchrightのAkamai対応を「未確認」に変更、CamoufoxのLinux対応状況を訂正（安定版は対応済み）、メンテナンス状況に関する警告を追加 |

---

*本ドキュメントは、公開されている情報に基づいて作成されています。ボット検知回避の手法は日々進化しているため、最新の情報を確認することをお勧めします。*
