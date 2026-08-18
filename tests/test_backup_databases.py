import json
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.backup_databases import create_archive, prune_local_archives, upload_archive


class BackupDatabasesTests(unittest.TestCase):
    def create_database(self, path: Path, value: str) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
            connection.execute("INSERT INTO sample (value) VALUES (?)", (value,))
            connection.commit()
        finally:
            connection.close()

    def test_archive_contains_two_verified_databases_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            database_dir = temp_dir / "database"
            backup_dir = temp_dir / "backups"
            database_dir.mkdir()
            self.create_database(database_dir / "planner.db", "planner")
            self.create_database(database_dir / "studio.db", "studio")

            archive_path = create_archive(
                database_dir,
                backup_dir,
                datetime(2026, 8, 18, 3, 0, tzinfo=ZoneInfo("Europe/Moscow")),
            )

            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    set(archive.namelist()), {"manifest.json", "planner.db", "studio.db"}
                )
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(
                    [item["name"] for item in manifest["databases"]],
                    ["planner.db", "studio.db"],
                )
                self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["databases"]))

    def test_retention_keeps_only_newest_archives(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            backup_dir = Path(temp_dir_name)
            month_dir = backup_dir / "2026" / "08"
            month_dir.mkdir(parents=True)
            for index in range(10):
                archive = month_dir / f"fitness_studio_2026-08-{index + 1:02d}_03-00-00_MSK.zip"
                archive.write_bytes(str(index).encode())
                archive.touch()

            removed = prune_local_archives(backup_dir, keep=7)

            self.assertEqual(len(removed), 3)
            self.assertEqual(len(list(backup_dir.glob("*/*/*.zip"))), 7)

    @patch("scripts.backup_databases.subprocess.run")
    @patch("scripts.backup_databases.shutil.which", return_value="/usr/bin/rclone")
    def test_upload_copies_and_checks_only_created_archive(self, _which, run):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            archive = Path(temp_dir_name) / "fitness_studio_2026-08-18_03-00-00_MSK.zip"
            archive.write_bytes(b"backup")
            timestamp = datetime(2026, 8, 18, 3, 0, tzinfo=ZoneInfo("Europe/Moscow"))

            remote_path = upload_archive(archive, "yandex:Fitness Studio/Backups", timestamp)

            self.assertEqual(
                remote_path,
                "yandex:Fitness Studio/Backups/2026/08/fitness_studio_2026-08-18_03-00-00_MSK.zip",
            )
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[0][0:2], ["rclone", "copyto"])
            self.assertIn("--checksum", run.call_args_list[0].args[0])
            self.assertEqual(run.call_args_list[1].args[0][0:2], ["rclone", "check"])
            self.assertIn(archive.name, run.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
