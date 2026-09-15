"""统一 ZIP 备份（⑧）与自动快照/保留策略（⑨）的回归测试。

运行：python3 -m unittest discover -s tests -v
只用标准库；所有路径指向临时目录，不碰 data/。
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-backup-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "summary.sqlite3")

import backup_service  # noqa: E402
import memo_storage  # noqa: E402
import storage  # noqa: E402
import summary_storage  # noqa: E402

BACKUP_DIR = Path(backup_service.BACKUP_DIR)


def make_project(project_id: str, name: str) -> dict:
    return {
        "id": project_id, "name": name, "description": "", "createdAt": "2026-09-15",
        "assessmentEnabled": False, "reviewEnabled": False,
        "tree": [{
            "id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": "2026-09-15", "children": [{
                "id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": "2026-09-15", "children": [{
                    "id": f"{project_id}-i", "type": "item", "text": "任务1", "completed": False,
                    "completedAt": None, "optional": False, "assessmentRequired": False,
                    "assessmentHistory": 0, "assessment": None, "createdAt": "2026-09-15",
                    "children": [],
                }],
            }],
        }],
    }


class FullBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertNotEqual(Path(backup_service.DATABASE_FILES["todo.sqlite3"]), APP_DIR / "data" / "todo.sqlite3",
                            "测试必须使用临时数据库")
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
        for filename in ("todo.sqlite3", "memo.sqlite3", "summary.sqlite3"):
            path = Path(_TEMP_DIR.name) / filename
            for suffix in ("", "-wal", "-shm"):
                Path(f"{path}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        memo_storage.initialize()
        summary_storage.initialize()
        storage.replace_projects([make_project("p1", "项目一")])
        memo_storage.write_memo({"title": "备忘", "content": "很长的正文" * 50, "pinned": False})
        summary_storage.upsert_summary("题目", "摘要内容")

    def test_create_writes_manifest_with_checksums(self) -> None:
        name = backup_service.create_full_backup("manual")
        self.assertTrue(name.endswith(".zip"))
        path = BACKUP_DIR / name
        self.assertTrue(path.is_file())
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            self.assertEqual(names, {"todo.sqlite3", "memo.sqlite3", "summary.sqlite3", "manifest.json"})
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        self.assertEqual(manifest["format"], backup_service.BACKUP_FORMAT_VERSION)
        self.assertEqual(manifest["appSchemaVersion"], storage.SCHEMA_VERSION)
        self.assertEqual(manifest["counts"]["projects"], 1)
        self.assertEqual(manifest["counts"]["memos"], 2)   # initialize() 的占位 + 新建的
        self.assertEqual(manifest["counts"]["summaries"], 1)
        for file_name in ("todo.sqlite3", "memo.sqlite3", "summary.sqlite3"):
            self.assertEqual(len(manifest["files"][file_name]["sha256"]), 64)
            self.assertGreater(manifest["files"][file_name]["bytes"], 0)

    def test_describe_reports_checksum_and_counts(self) -> None:
        name = backup_service.create_full_backup("manual")
        preview = backup_service.describe_backup(name)
        self.assertTrue(preview["checksumOk"])
        self.assertEqual(preview["kind"], "full")
        self.assertEqual(preview["counts"]["projects"], 1)
        self.assertTrue(all(item["ok"] for item in preview["files"]))
        self.assertTrue(preview["createdAt"])

    def test_tampered_backup_is_detected_and_refused(self) -> None:
        name = backup_service.create_full_backup("manual")
        path = BACKUP_DIR / name
        # 篡改内容但不改 manifest → 校验和应当不匹配
        with zipfile.ZipFile(path) as archive:
            entries = {item.filename: archive.read(item.filename) for item in archive.infolist()}
        entries["todo.sqlite3"] = entries["todo.sqlite3"] + b"tampered"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_name, data in entries.items():
                archive.writestr(file_name, data)
        self.assertFalse(backup_service.describe_backup(name)["checksumOk"])
        with self.assertRaises(ValueError) as ctx:
            backup_service.restore_full_backup(name)
        self.assertIn("校验和", str(ctx.exception))
        # 数据没被动过
        self.assertEqual(len(storage.read_project_summaries()), 1)

    def test_restore_roundtrip_brings_back_deleted_data(self) -> None:
        name = backup_service.create_full_backup("manual")
        revision = storage.read_project_summaries()[0]["_revision"]
        storage.delete_project("p1", revision)
        summary_storage.clear_summaries()
        self.assertEqual(storage.read_project_summaries(), [])
        self.assertEqual(summary_storage.list_summaries(), [])

        result = backup_service.restore_full_backup(name)

        self.assertEqual(result["kind"], "full")
        self.assertEqual([item["name"] for item in storage.read_project_summaries()], ["项目一"])
        self.assertEqual(len(summary_storage.list_summaries()), 1)
        self.assertTrue(result["emergency"].endswith(".zip"))

    def test_restore_failure_rolls_back(self) -> None:
        good = backup_service.create_full_backup("manual")
        # 改掉当前数据，随后用"校验和正确但内部损坏"的备份来恢复
        storage.replace_projects([make_project("p1", "改过的项目"), make_project("p2", "第二个")])
        good_bytes = {}
        with zipfile.ZipFile(BACKUP_DIR / good) as archive:
            for item in archive.infolist():
                good_bytes[item.filename] = archive.read(item.filename)
        manifest = json.loads(good_bytes["manifest.json"].decode("utf-8"))
        broken = b"this-is-not-a-sqlite-file"
        good_bytes["todo.sqlite3"] = broken
        import hashlib
        manifest["files"]["todo.sqlite3"] = {"sha256": hashlib.sha256(broken).hexdigest(), "bytes": len(broken)}
        good_bytes["manifest.json"] = json.dumps(manifest).encode("utf-8")
        broken_path = BACKUP_DIR / "manual-broken.zip"
        with zipfile.ZipFile(broken_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_name, data in good_bytes.items():
                archive.writestr(file_name, data)

        with self.assertRaises((RuntimeError, ValueError, OSError, sqlite3.DatabaseError)):
            backup_service.restore_full_backup(broken_path.name)

        # 回滚后：恢复前的数据必须还在（两个项目，不是备份里的一个）
        self.assertEqual(sorted(item["name"] for item in storage.read_project_summaries()),
                         ["改过的项目", "第二个"])

    def test_legacy_single_database_backup_still_restorable(self) -> None:
        legacy_name = storage.create_manual_database_backup("legacy")
        self.assertTrue(legacy_name.endswith(".sqlite3"))
        preview = backup_service.describe_backup(legacy_name)
        self.assertEqual(preview["kind"], "legacy")
        self.assertIn("只包含任务数据库", preview["note"])
        result = backup_service.restore_full_backup(legacy_name)
        self.assertEqual(result["restored"], ["todo.sqlite3"])

    def test_hidden_temp_files_cannot_be_used_as_backups(self) -> None:
        """恢复/回滚的临时文件（.restore-* / .rollback-*）不能当备份恢复：可能是半个库。"""
        hidden_db = BACKUP_DIR / ".restore-deadbeef-todo.sqlite3"
        hidden_db.write_bytes(b"not a real database")
        hidden_zip = BACKUP_DIR / ".rollback-deadbeef.zip"
        hidden_zip.write_bytes(b"PK\x03\x04fake")
        for name in (hidden_db.name, hidden_zip.name):
            with self.assertRaises(ValueError, msg=f"{name} 不该被接受"):
                backup_service.describe_backup(name)
        with self.assertRaises(ValueError):
            backup_service.restore_full_backup(hidden_db.name)
        with self.assertRaises(ValueError):
            storage.restore_database_backup(hidden_db.name)
        # 也不该出现在任何列表里
        names = [entry["name"] for entry in backup_service.list_backups()]
        self.assertNotIn(hidden_db.name, names)
        self.assertNotIn(hidden_zip.name, names)


class RetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _fake(self, name: str, age_days: float, *, hour: int = 3) -> Path:
        path = BACKUP_DIR / name
        path.write_bytes(b"PK\x03\x04fake")
        stamp = (datetime.now() - timedelta(days=age_days)).replace(hour=hour, minute=0, second=0, microsecond=0)
        os.utime(path, (stamp.timestamp(), stamp.timestamp()))
        return path

    def test_keeps_recent_daily_and_weekly_buckets(self) -> None:
        self._fake("manual-recent.zip", 2)
        self._fake("daily-same-day-a.zip", 10, hour=1)
        self._fake("daily-same-day-b.zip", 10, hour=5)
        self._fake("daily-same-day-c.zip", 10, hour=9)
        self._fake("weekly-same-week-a.zip", 40, hour=1)
        self._fake("weekly-same-week-b.zip", 40, hour=5)
        self._fake("too-old.zip", 200)

        result = backup_service.prune_backups()

        remaining = sorted(path.name for path in BACKUP_DIR.glob("*.zip"))
        self.assertIn("manual-recent.zip", remaining)
        self.assertEqual(len([name for name in remaining if name.startswith("daily-same-day")]), 1,
                         "同一天只保留最新一份")
        self.assertEqual(len([name for name in remaining if name.startswith("weekly-same-week")]), 1,
                         "同一周只保留最新一份")
        self.assertNotIn("too-old.zip", remaining)
        self.assertEqual(result["kept"], 3, "近 7 天 1 份 + 每日桶 1 份 + 每周桶 1 份")
        self.assertEqual(result["removed"], 4)

    def test_recent_backups_are_never_removed(self) -> None:
        for index in range(5):
            self._fake(f"manual-today-{index}.zip", 0, hour=index + 1)
        result = backup_service.prune_backups()
        self.assertEqual(result["removed"], 0)
        self.assertEqual(len(list(BACKUP_DIR.glob("*.zip"))), 5)


class DailySnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        storage.replace_projects([make_project("p1", "项目一")])

    def test_daily_snapshot_is_idempotent(self) -> None:
        first = backup_service.create_daily_snapshot()
        second = backup_service.create_daily_snapshot()
        self.assertTrue(first and first.endswith(".zip"))
        self.assertIsNone(second, "同一天不应该再生成第二份")
        self.assertEqual(len(list(BACKUP_DIR.glob("daily-*.zip"))), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
