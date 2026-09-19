import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-migrate-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")

import storage  # noqa: E402

REVIEW_TABLES = ("review_points", "review_point_tasks", "review_states",
                 "review_attempts", "review_sessions")


class ReviewMigrationTests(unittest.TestCase):
    def test_schema_version_is_9(self) -> None:
        self.assertEqual(storage.SCHEMA_VERSION, 9)

    def test_v8_database_drops_removed_tables(self) -> None:
        """v9 迁移注销三个已取消功能的空表（背景图 / 筛选视图 / 自定义模板）。"""
        storage.ensure_schema()
        removed = ("app_asset", "saved_views", "project_templates")
        with storage.open_state_database() as connection:
            for table in removed:
                connection.execute(f"CREATE TABLE IF NOT EXISTS {table}(x TEXT)")
            connection.execute("PRAGMA user_version=8")
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(version, storage.SCHEMA_VERSION)
        for table in removed:
            self.assertNotIn(table, tables, f"{table} 应该被 v9 迁移删掉")
        self.assertTrue(storage.check_database_integrity())

    def test_v7_database_migrates_without_touching_projects(self) -> None:
        storage.ensure_schema()
        project = {
            "id": "p-old", "name": "旧项目", "description": "", "createdAt": "2026-09-16",
            "assessmentEnabled": False,
            "tree": [{"id": "w1", "type": "week", "text": "第1周", "completed": False,
                      "expanded": False, "createdAt": "2026-09-16", "children": [
                          {"id": "i1", "type": "item", "text": "任务", "completed": False,
                           "completedAt": None, "optional": False, "assessmentRequired": False,
                           "assessmentHistory": 0, "assessment": None,
                           "createdAt": "2026-09-16", "children": []}]}],
        }
        storage.write_project(project, None)
        before = storage.read_project("p-old")[0]
        # 伪造成"升级前的 v7 库"：删掉复习表并把版本退回去
        with storage.open_state_database() as connection:
            for table in REVIEW_TABLES:
                connection.execute(f"DROP TABLE IF EXISTS {table}")
            connection.execute("PRAGMA user_version=7")
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(version, storage.SCHEMA_VERSION)
        for table in REVIEW_TABLES:
            self.assertIn(table, tables)
        self.assertEqual(storage.read_project("p-old")[0], before, "迁移不得改动项目数据")
        self.assertTrue(storage.check_database_integrity())


if __name__ == "__main__":
    unittest.main()
