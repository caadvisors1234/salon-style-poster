# Camoufox実装プロンプト

## 概要

PlaywrightからCamoufoxへ移行し、Akamai Bot Managerの検知回避を実現する。

---

## 目標

1. **Playwright → Camoufox への移行**
   - `browser_manager.py` をCamoufoxを使用するように書き換え
   - Mixin構造を維持し、既存コードとの互換性を保つ

2. **バイパス率の向上**
   - 現在のPlaywrightのバイパス率 → Camoufoxの83.3%へ

3. **Docker環境での動作**
   - xvfb環境で動作するように構成

---

## 重要な注意点

### 安定版の使用

```bash
# PyPIパッケージは安定版バイナリで、Linux対応済み
pip install camoufox[geoip]
python3 -m camoufox fetch
```

- メインブランチ（Firefox v146）は**実験的**でMacOSのみ
- **安定版（releases/135 / PyPI）**を使用すること

### Playwright API互換性

CamoufoxはPlaywrightと完全互換のAPIを持つため、Mixin構造（`BrowserUtilsMixin`、`LoginHandlerMixin`、`StyleFormHandlerMixin`）は変更なしで維持できます。

---

## 変更するファイル

| ファイル | 変更内容 |
|---------|----------|
| `requirements.txt` | `playwright`、`playwright-stealth` → `camoufox[geoip]` |
| `Dockerfile` | Firefox依存関係の追加、Camoufoxのインストール |
| `docker-compose.yml` | `camoufox_cache` ボリュームの追加 |
| `app/services/salonboard/browser_manager.py` | Playwright → Camoufox への書き換え |

---

## 実装手順

### Phase 1: requirements.txt の更新

```diff
- playwright==1.41.0
- playwright-stealth==1.0.6
+ camoufox[geoip]
```

### Phase 2: Dockerfile の更新

```diff
 # Browser Automation
- RUN playwright install --with-deps chromium firefox
+ # Firefox依存関係（Camoufox用）
+ RUN apt-get install -y \
+     libgtk-3-0 \
+     libx11-xcb1 \
+     libasound2
+
+ # Camoufoxのインストールとブラウザ取得
+ RUN pip install --no-cache-dir -U "camoufox[geoip]"
+ RUN python3 -m camoufox fetch
+
+ # キャッシュディレクトリのボリュームマウント（ビルド時間短縮）
+ VOLUME /root/.cache/camoufox
```

### Phase 3: docker-compose.yml の更新

```yaml
volumes:
  postgres_data:
  camoufox_cache:  # 追加

services:
  worker:
    # ... 既存の設定 ...
    volumes:
      - .:/app
      - ./logs:/app/logs
      - camoufox_cache:/root/.cache/camoufox  # 追加
```

### Phase 4: browser_manager.py の書き換え

#### 変更点の概要

| 変更箇所 | 変更内容 |
|---------|----------|
| インポート | `playwright.sync_api` → `camoufox.sync_api` |
| `playwright_stealth` | **削除**（Camoufoxに組み込み済み） |
| `_start_browser()` | `sync_playwright()` → `Camoufox()` |
| `_close_browser()` | Camoufoxのコンテキスト管理に対応 |
| `_create_page()` | `stealth_sync()` の削除 |

#### 具体的なコード変更

**1. インポートの書き換え**

```diff
 from playwright.sync_api import (
     Browser,
     BrowserContext,
     Page,
     Playwright,
     Request,
     sync_playwright,
 )
-from playwright_stealth import stealth_sync
+from camoufox.sync_api import Camoufox
```

**2. _start_browser() の書き換え**

```python
def _start_browser(self):
    """ブラウザ起動（Camoufox版）"""
    # CamoufoxはPlaywrightのsync_playwright()を使用しない
    self.browser = Camoufox(
        headless=not self.headless,  # headless=Falseでxvfb使用、headless="virtual"も可
        os="windows",                 # OS偽装
        locale="ja-JP",               # 日本語ロケール
        humanize=True,                # 人間らしいカーソル移動
        block_webrtc=True,            # WebRTCブロック
        # Camoufoxが内部で以下を自動設定：
        # - User-Agent
        # - navigatorプロパティ
        # - TLSフィンガープリント
        # - その他の検知回避機能
    )

    # コンテキストの取得（Playwright API互換）
    self.context = self.browser

    # 新しいページ作成
    self.page = self._create_page()

    logger.info("ブラウザ起動完了（Camoufox）")
```

**3. _close_browser() の書き換え**

```python
def _close_browser(self):
    """ブラウザ終了（Camoufox版）"""
    if self.page:
        try:
            self.page.close()
        except Exception as e:
            logger.warning("ページ終了時に警告: %s", e)
        finally:
            self.page = None

    if self.context:
        try:
            self.context.close()
        except Exception as e:
            logger.warning("ブラウザコンテキスト終了時に警告: %s", e)
        finally:
            self.context = None

    if self.browser:
        try:
            self.browser.close()
        except Exception as e:
            logger.warning("ブラウザ終了時に警告: %s", e)
        finally:
            self.browser = None

    logger.info("ブラウザ終了（Camoufox）")
```

**4. _create_page() の書き換え**

```diff
 def _create_page(self) -> Page:
     """セッションを維持した新規ページ生成"""
     if not self.context:
         raise Exception("ブラウザコンテキストが初期化されていません")
     page = self.context.new_page()
     page.on("requestfailed", self._handle_request_failed)
-    stealth_sync(page)
     page.set_default_timeout(180000)
     return page
```

**5. 型ヒントの更新**

```diff
 from typing import Callable, Dict, Optional

-from camoufox.sync_api import Camoufox
+from camoufox.sync_api import AsyncBrowser as Browser

 class SalonBoardBrowserManager:
     def __init__(self, ...):
         ...
-        self.playwright: Optional[Playwright] = None
-        self.browser: Optional[Browser] = None
+        self.browser: Optional[Camoufox] = None
         self.context: Optional[BrowserContext] = None
         self.page: Optional[Page] = None
```

### Phase 5: 動作確認

```bash
# Dockerイメージの再ビルド
docker-compose down
docker-compose build --no-cache worker
docker-compose up -d worker

# ログで起動を確認
docker-compose logs -f worker

# 「ブラウザ起動完了（Camoufox）」が表示されることを確認
```

---

## 検証チェックリスト

- [ ] requirements.txtの更新
- [ ] Dockerfileの更新
- [ ] docker-compose.ymlの更新
- [ ] browser_manager.pyの書き換え
- [ ] Dockerイメージのビルド成功
- [ ] コンテナの起動成功
- [ ] スタイル投稿テストで画像アップロード成功

---

## トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'playwright'`

`requirements.txt`から`playwright`を削除したのに、他のファイルでインポートしていないか確認してください。

### エラー: `Firefox not found`

```bash
docker-compose exec worker python3 -m camoufox fetch
```

### エラー: `libgtk-3-0: not found`

DockerfileでFirefox依存関係が正しくインストールされているか確認してください。

---

## 参考資料

- [Camoufox GitHub](https://github.com/daijro/camoufox)
- [Camoufox Python Interface](https://camoufox.com/python/)
- [docs/akamai_bot_detection_research.md](./akamai_bot_detection_research.md)
