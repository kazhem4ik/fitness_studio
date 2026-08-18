#!/usr/bin/env python3
"""Create consistent SQLite backups and upload one archive with rclone."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_DIR = PROJECT_ROOT / "database"
DEFAULT_LOCAL_BACKUP_DIR = Path.home() / "backups" / "fitness_studio"
DATABASE_NAMES = ("planner.db", "studio.db")
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-dir",
        type=Path,
        default=Path(os.getenv("FITNESS_BACKUP_DATABASE_DIR", DEFAULT_DATABASE_DIR)),
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path(os.getenv("FITNESS_BACKUP_LOCAL_DIR", DEFAULT_LOCAL_BACKUP_DIR)),
    )
    parser.add_argument(
        "--rclone-remote",
        default=os.getenv("FITNESS_BACKUP_RCLONE_REMOTE", "yandex:Fitness Studio/Backups"),
        help="Remote root, for example: yandex:Fitness Studio/Backups",
    )
    parser.add_argument(
        "--keep-local",
        type=int,
        default=int(os.getenv("FITNESS_BACKUP_KEEP_LOCAL", "7")),
    )
    parser.add_argument("--skip-upload", action="store_true")
    return parser.parse_args()


def verify_database(path: Path) -> None:
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if not result or result[0] != "ok":
        raise RuntimeError(f"SQLite integrity check failed for {path}: {result}")


def snapshot_database(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Database not found: {source}")
    verify_database(source)
    with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True)) as source_db:
        with closing(sqlite3.connect(destination)) as destination_db:
            source_db.backup(destination_db)
    verify_database(destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_archive(database_dir: Path, backup_dir: Path, timestamp: datetime) -> Path:
    month_dir = backup_dir / timestamp.strftime("%Y") / timestamp.strftime("%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    archive_path = month_dir / f"fitness_studio_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}_MSK.zip"

    with tempfile.TemporaryDirectory(prefix="fitness-studio-backup-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        manifest = {
            "created_at": timestamp.isoformat(),
            "timezone": "Europe/Moscow",
            "databases": [],
        }
        for database_name in DATABASE_NAMES:
            snapshot_path = temp_dir / database_name
            snapshot_database(database_dir / database_name, snapshot_path)
            manifest["databases"].append(
                {
                    "name": database_name,
                    "size": snapshot_path.stat().st_size,
                    "sha256": sha256(snapshot_path),
                }
            )

        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(temp_dir.iterdir()):
                archive.write(file_path, arcname=file_path.name)

    return archive_path


def upload_archive(archive_path: Path, remote_root: str, timestamp: datetime) -> str:
    if not shutil.which("rclone"):
        raise RuntimeError("rclone is not installed or not available in PATH")
    remote_directory = (
        f"{remote_root.rstrip('/')}/{timestamp.strftime('%Y')}/"
        f"{timestamp.strftime('%m')}"
    )
    remote_path = f"{remote_directory}/{archive_path.name}"
    subprocess.run(
        ["rclone", "copyto", str(archive_path), remote_path, "--checksum"],
        check=True,
    )
    subprocess.run(
        [
            "rclone",
            "check",
            str(archive_path.parent),
            remote_directory,
            "--include",
            archive_path.name,
            "--one-way",
        ],
        check=True,
    )
    return remote_path


def prune_local_archives(backup_dir: Path, keep: int) -> list[Path]:
    if keep < 1:
        raise ValueError("keep-local must be at least 1")
    archives = sorted(
        backup_dir.glob("*/*/fitness_studio_*_MSK.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed = []
    for archive in archives[keep:]:
        archive.unlink()
        removed.append(archive)
    for directory in sorted(backup_dir.glob("*/*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    for directory in sorted(backup_dir.glob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    return removed


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(MOSCOW_TZ)
    try:
        archive_path = create_archive(args.database_dir, args.backup_dir, timestamp)
        print(f"Created and verified: {archive_path}")
        if not args.skip_upload:
            remote_path = upload_archive(archive_path, args.rclone_remote, timestamp)
            print(f"Uploaded and verified: {remote_path}")
        removed = prune_local_archives(args.backup_dir, args.keep_local)
        print(f"Local retention: kept {args.keep_local}, removed {len(removed)}")
        return 0
    except Exception as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
