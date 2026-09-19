"""P13 回归：三处"慢慢变大"的无界增长。

① activity_log 每次排序/复制/批量/删除都写一行，只有手动清空能减 —— 永不裁剪；
② create_daily_snapshot 的 .daily-YYYYMMDD marker 一天一个、永不清理；
③ prune_backups 只 glob *.zip，旧格式 *.sqlite3（导入前/迁移前自动留的整库副本）永不裁剪。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-growth-bounds-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import backup_service  # noqa: E402
import storage  # noqa: E402

BACKUP_DIR = Path(backup_service.BACKUP_DIR)


class ActivityLogBoundsTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        storage.ensure_schema()

    def test_activity_log_is_trimmed_to_keep_rows(self) -> None:
        keep = storage.ACTIVITY_KEEP_ROWS
        with storage.open_state_database() as connection:
            for index in range(keep + 37):
                storage.log_activity("bulk", f"第 {index} 条活动", connection=connection)
        with storage.open_state_database() as connection:
            rows = connection.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
            newest = connection.execute(
                "SELECT summary FROM activity_log ORDER BY id DESC LIMIT 1").fetchone()[0]
            oldest = connection.execute(
                "SELECT summary FROM activity_log ORDER BY id ASC LIMIT 1").fetchone()[0]
        self.assertEqual(rows, keep, f"应该只留最近 {keep} 条，实际 {rows} 条")
        self.assertEqual(newest, f"第 {keep + 36} 条活动", "最新的必须留着")
        self.assertEqual(oldest, "第 37 条活动", "最旧的应该已经被裁掉")

    def test_trim_also_applies_on_its_own_connection(self) -> None:
        keep = storage.ACTIVITY_KEEP_ROWS
        with storage.open_state_database() as connection:
            for index in range(keep):
                storage.log_activity("bulk", f"批量 {index}", connection=connection)
        storage.log_activity("single", "单独写一条（自己开库）")
        with storage.open_state_database() as connection:
            rows = connection.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
            newest = connection.execute(
                "SELECT summary FROM activity_log ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertEqual(rows, keep)
        self.assertEqual(newest, "单独写一条（自己开库）")

class BackupRetentionBoundsTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _touch(self, name: str, age_days: int) -> Path:
        path = BACKUP_DIR / name
        path.write_bytes(b"x" * 64)
        stamp = (datetime.now() - timedelta(days=age_days)).timestamp()
        os.utime(path, (stamp, stamp))
        return path

    def test_old_daily_markers_are_pruned(self) -> None:
        today = datetime.now().strftime("%Y%m%d")
        recent = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        old = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
        kept_today = self._touch(f".daily-{today}", 0)
        kept_recent = self._touch(f".daily-{recent}", 10)
        gone = self._touch(f".daily-{old}", 400)
        weird = self._touch(".daily-not-a-date", 400)

        result = backup_service.prune_backups()

        self.assertTrue(kept_today.exists())
        self.assertTrue(kept_recent.exists())
        self.assertFalse(gone.exists(), "400 天前的每日 marker 应该被清掉")
        self.assertTrue(weird.exists(), "认不出日期的 marker 不动它（保守）")
        self.assertEqual(result["markersRemoved"], 1)

    def test_legacy_sqlite3_backups_are_pruned(self) -> None:
        old_import = self._touch("before-import-20200101-000000.sqlite3", 400)
        old_migrate = self._touch("before-migrate-v5-20200101-000000.sqlite3", 400)
        old_zip = self._touch("manual-old.zip", 400)
        recent_sqlite = self._touch("before-import-20990101-000000.sqlite3", 1)
        recent_zip = self._touch("manual-recent.zip", 1)

        result = backup_service.prune_backups()

        self.assertFalse(old_import.exists(), "旧格式 .sqlite3 也要按同一套保留策略清理")
        self.assertFalse(old_migrate.exists())
        self.assertFalse(old_zip.exists())
        self.assertTrue(recent_sqlite.exists())
        self.assertTrue(recent_zip.exists())
        self.assertEqual(result["removed"], 3)
        self.assertEqual(result["kept"], 2)

    def test_hidden_and_staging_files_are_left_alone(self) -> None:
        hidden = self._touch(".restore-abc-todo.sqlite3", 400)
        rollback = self._touch(".rollback-abc-memo.sqlite3", 400)
        backup_service.prune_backups()
        self.assertTrue(hidden.exists(), "隐藏的恢复暂存文件不能被当成备份删掉")
        self.assertTrue(rollback.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
