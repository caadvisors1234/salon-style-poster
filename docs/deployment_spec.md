`blog-automation`、`salon-style-poster`、`style-ai-generator` の3つのアプリケーションが同居する統合環境のシステム構成仕様書を作成しました。

このドキュメントは、**Nginx Proxy Manager（Gateway）** を入り口とし、各Dockerコンテナへリクエストを振り分ける構成を前提としています。

---

# 統合VPS環境 デプロイメント仕様書

## 1\. システム全体構成図

本環境は、1つのVPS上で複数のマイクロサービス（Dockerコンテナ）が稼働するマルチテナント構成です。
外部からのアクセスは全て **Gateway (Nginx Proxy Manager)** が一元管理し、ドメイン名に基づいて適切なアプリケーションコンテナへルーティングします。

```mermaid
graph TD
    User((User)) -->|HTTPS/443| Gateway[Gateway<br/>Nginx Proxy Manager]

    subgraph "Docker Network: blog_network"
        Gateway -.->|proxy_pass:8000| BlogWeb[Blog Automation<br/>(Django/Gunicorn)]
        BlogWeb --> BlogDB[(Postgres 16)]
        BlogWeb --> BlogRedis[(Redis)]
        BlogCelery[Celery Worker] --> BlogRedis
    end

    subgraph "Docker Network: poster_network"
        Gateway -.->|proxy_pass:8000| PosterWeb[Salon Style Poster<br/>(FastAPI/Uvicorn)]
        PosterWeb --> PosterDB[(Postgres 15)]
        PosterWeb --> PosterRedis[(Redis)]
        PosterWorker[Celery Worker] --> PosterRedis
    end

    subgraph "Docker Network: style_network"
        Gateway -.->|proxy_pass:8000| StyleWeb[Style AI Generator<br/>(Django)]
        StyleWeb --> StyleDB[(Postgres 14)]
        StyleWeb --> StyleRedis[(Redis)]
        StyleCelery[Celery Worker] --> StyleRedis
    end

```

## 2\. ディレクトリ構造 (VPSホスト側)

各アプリケーションは `/opt/` 配下の独立したディレクトリで管理されています。

```
/opt/
├── blog/                      # [App 1] Blog Automation
│   ├── docker-compose.yml
│   ├── .env
│   ├── logs/                  # 永続化ログ
│   ├── media/                 # 永続化メディア
│   └── ...
│
├── poster/        # [App 2] Salon Style Poster
│   ├── docker-compose.yml
│   ├── .env
│   └── ...
│
├── style/        # [App 3] Style AI Generator
│   ├── docker-compose.yml
│   ├── .env
│   └── ...
│
└── gateway/                   # [Common] Nginx Proxy Manager
    ├── docker-compose.yml
    ├── data/                  # SSL証明書/設定DB
    └── letsencrypt/           # Let's Encrypt 証明書実体

```

---

## 3\. 各アプリケーション詳細設定

すべてのアプリケーションは **内部ポート 8000** で待機し、ホスト側にはポートを公開しない（Gateway経由でのみアクセスさせる）設定が推奨されます。

### 3.1. Blog Automation (blog)

- **ディレクトリ:** `/opt/blog`
- **メインコンテナ名:** `blog_automation_web`
- **フレームワーク:** Django (Gunicorn + Uvicorn Worker)
- **静的ファイル:** WhiteNoiseによりアプリ配信
- **使用ポート:** `8000` (内部)

### 3.2. Salon Style Poster (poster)

- **ディレクトリ:** `/opt/poster`
- **メインコンテナ名:** `salon_board_web`
- **フレームワーク:** FastAPI (Uvicorn)
- **使用ポート:** `8000` (内部)
- **特記事項:**
    - `nginx/nginx.conf` がリポジトリに含まれていますが、Gateway (Nginx Proxy Manager) を使用しているため、**アプリ側のNginxコンテナは起動不要、もしくはGatewayからの直接振り分け**で対応可能です。
    - FastAPIのドキュメント(`/docs`)やAPIエンドポイントへアクセスします。

### 3.3. Style AI Generator (style)

- **ディレクトリ:** `/opt/style`
- **メインコンテナ名:** `style-web-1`
- **フレームワーク:** Django
- **使用ポート:** `8000` (内部)

---

## 4\. Nginx Proxy Manager (Gateway) 設定ガイド

Gatewayの管理画面（通常ポート81）から、以下の通り「Proxy Host」を設定してください。

### 共通設定項目

- **Scheme:** `http`
- **Forward Port:** `8000`
- **Block Common Exploits:** Enable
- **Websockets Support:** Enable (Django Channelsやリアルタイム通知のため必須)

### アプリ別設定表

| アプリ名 | Domain Names (例) | Forward Hostname (コンテナ名) | Docker Network接続要否 |
| --- | --- | --- | --- |
| **Blog** | `blog-automation.ai-beauty.tokyo`  | `blog_automation_web` | Gatewayを `blog_internal` に参加させる |
| **Poster** | `salon-style-poster.ai-beauty.tokyo`  | `salon_board_web` | Gatewayを `poster_network` に参加させる |
| **Style** | `style-ai-generator.ai-beauty.tokyo` | `style-web-1` | Gatewayを `style_network` に参加させる |

> ⚠️ 重要: ネットワーク接続について
Gatewayコンテナが各アプリのコンテナ名（blog_automation_webなど）を名前解決するには、Gatewayのコンテナが各アプリのDockerネットワークに所属している必要があります。
> 
> 
> **Gatewayへのネットワーク追加コマンド例:**
> 
> ```bash
> # ネットワーク名を確認
> docker network ls
> ```
> 

> Gatewayコンテナを各ネットワークに参加させる
> 
> 
> ```
> docker network connect blog\_internal gateway-app-1
> docker network connect poster\_default gateway-app-1
> docker network connect style\_default gateway-app-1
> ```
> 

---

## 5\. 運用・メンテナンスコマンド集

### 全サービスの確認

```bash
docker ps --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"
```

### ログの確認 (リアルタイム)

```bash
# Blog
docker logs -f --tail 100 blog_automation_web

# Poster
docker logs -f --tail 100 salon_board_web

# Style
docker logs -f --tail 100 style-web-1

# Gateway (SSLエラーなどの確認)
docker logs -f --tail 100 gateway-app-1
```

### アプリケーションの更新手順

ソースコードを `git pull` した後、以下の手順で反映します。

**Blog Automation**

```bash
cd /opt/blog
docker compose up -d --build
# マイグレーションが必要な場合
docker compose exec web python manage.py migrate
```

**Salon Style Poster**

```bash
cd /opt/poster
docker compose up -d --build
# マイグレーション
docker compose exec web alembic upgrade head
```

**Style AI Generator**

```bash
cd /opt/style
docker compose up -d --build
# マイグレーション
docker compose exec web python manage.py migrate
```

---

## 6\. トラブルシューティング

- **502 Bad Gateway が出る場合**
    1. 対象アプリのコンテナが起動しているか (`docker ps`) 確認してください。
    2. Gatewayコンテナから対象コンテナへPingが通るか確認してください。
    ※ `Unknown host` となる場合、前述の「ネットワーク接続」が行われていません。
        
        ```bash
        docker exec -it gateway-app-1 ping blog_automation_web
        ```
        
- **静的ファイル (CSS/JS) が 404 になる場合**
    - **Blog/Style (Django):** `WhiteNoise` の設定が有効か、`collectstatic` がビルド時に実行されているか確認してください。
    - **Poster (FastAPI):** `StaticFiles` のマウント設定 (`app.mount("/static", ...)` ) がコード内で正しいパスを指しているか確認してください。