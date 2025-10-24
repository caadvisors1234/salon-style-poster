# SALON BOARD Style Poster プロジェクト概要

## プロジェクトの目的
SALON BOARDへのスタイル投稿を自動化するWebアプリケーション。美容サロンのスタイリストがExcel/CSVファイルと画像ファイルをアップロードすることで、Playwright（ブラウザ自動化）を使用して複数のスタイルを自動的に投稿できるシステム。

## 技術スタック
- **バックエンド**: Python 3.11+, FastAPI, Uvicorn
- **データベース**: PostgreSQL 15+, SQLAlchemy, Alembic
- **タスクキュー**: Celery, Redis
- **ブラウザ自動化**: Playwright (Firefox)
- **認証**: JWT (python-jose), bcrypt (passlib)
- **暗号化**: Fernet (cryptography)
- **フロントエンド**: Jinja2, HTML5/CSS3/JavaScript
- **コンテナ**: Docker, Docker Compose, Nginx

## アーキテクチャ
- Nginxコンテナ（リバースプロキシ、SSL終端、静的ファイル配信）
- Webコンテナ（FastAPI）
- Workerコンテナ（Celery + Playwright）
- PostgreSQLコンテナ
- Redisコンテナ

## 主要機能
1. **ユーザー管理**: 管理者による一般ユーザーの作成・管理
2. **SALON BOARD設定管理**: ユーザーごとのSALON BOARDログイン情報管理（パスワード暗号化）
3. **バッチ投稿**: Excel/CSVファイルと画像をアップロードして一括投稿
4. **進捗管理**: リアルタイムで投稿進捗を表示
5. **エラーレポート**: 投稿失敗時の詳細なエラー情報とスクリーンショット保存
6. **タスク中止**: 実行中のタスクを安全に中止可能

## データベース設計
- **users**: ユーザー情報（管理者・一般ユーザー）
- **salon_board_settings**: SALON BOARD接続設定（暗号化されたパスワード）
- **current_tasks**: 現在実行中のタスク状態（ユーザー単位のシングルタスク保証）

## セキュリティ
- パスワードハッシュ化（bcrypt）
- SALON BOARDパスワード暗号化（Fernet）
- JWT認証
- ユーザー単位のシングルタスク実行制限