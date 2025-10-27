from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.tasks import cleanup_screenshots


def create_file(path: Path, size: int, mtime: datetime) -> None:
    path.write_bytes(b"x" * size)
    timestamp = mtime.timestamp()
    os.utime(path, (timestamp, timestamp))


def test_cleanup_removes_files_older_than_retention(tmp_path):
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    old_file = tmp_path / "old.png"
    recent_file = tmp_path / "recent.png"

    create_file(old_file, size=1024, mtime=now - timedelta(days=40))
    create_file(recent_file, size=1024, mtime=now - timedelta(days=5))

    result = cleanup_screenshots(
        directory=tmp_path,
        retention_days=30,
        max_bytes=10_000,
        current_time=now,
    )

    assert not old_file.exists()
    assert recent_file.exists()
    assert result["removed_files"] == 1
    assert result["remaining_files"] == 1


def test_cleanup_enforces_directory_size_limit(tmp_path):
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    files = []
    for index in range(3):
        file_path = tmp_path / f"file_{index}.png"
        create_file(
            file_path,
            size=200,
            mtime=now - timedelta(hours=index),
        )
        files.append(file_path)

    result = cleanup_screenshots(
        directory=tmp_path,
        retention_days=-1,
        max_bytes=350,
        current_time=now,
    )

    remaining_files = [path for path in files if path.exists()]

    assert len(remaining_files) == result["remaining_files"]
    assert result["remaining_bytes"] <= 350
    # 最も古いファイルから削除される（indexが大きいもの）
    assert files[-1] not in remaining_files


def test_cleanup_removes_empty_directories(tmp_path):
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)
    nested_dir = tmp_path / "nested" / "deeper"
    nested_dir.mkdir(parents=True)
    file_path = nested_dir / "file.png"
    create_file(file_path, size=100, mtime=now - timedelta(days=60))

    cleanup_screenshots(
        directory=tmp_path,
        retention_days=30,
        max_bytes=10_000,
        current_time=now,
    )

    assert not file_path.exists()
    # 空ディレクトリが削除されていることを確認
    assert not nested_dir.exists()
