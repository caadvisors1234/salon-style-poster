#!/bin/sh
set -e

# 清掃: 古いロックファイルを削除
rm -f /tmp/.X99-lock
rm -f /tmp/.X11-unix/X99

# Xvfbをバックグラウンドで起動
# -ac: アクセス制御を無効化 (Docker内での実行に便利)
# -screen 0: スクリーン設定
echo "Starting Xvfb on :99..."
Xvfb :99 -ac -screen 0 1280x960x24 > /dev/null 2>&1 &

# Xvfbが起動するまで待機
echo "Waiting for Xvfb..."
i=0
while [ $i -lt 10 ]; do
    if [ -S /tmp/.X11-unix/X99 ]; then
        echo "Xvfb is ready."
        break
    fi
    sleep 0.5
    i=$((i + 1))
done

if [ ! -S /tmp/.X11-unix/X99 ]; then
    echo "Error: Xvfb failed to start."
    exit 1
fi

# DISPLAY環境変数を設定
export DISPLAY=:99

# Celeryワーカーを起動
echo "Starting Celery worker..."
exec celery -A app.worker worker --loglevel=info
