"""schema 版本安全（⑤）与导入 ID 校验（④）的回归测试。

覆盖第三阶段：
  - 高于当前版本的库必须拒绝打开（绝不降级）；
  - 低版本按阶梯迁移，迁移前自动快照，失败回滚；
  - 导入时重复项目/节点 ID 报具体路径并拒绝，缺失 ID 自动生成。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-schema-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "summary.sqlite3")

import memo_storage  # noqa: E402
import storage  # noqa: E402
import summary_storage  # noqa: E402

DB = Path(storage.DATABASE_FILE)


def wipe() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{DB}{suffix}").unlink(missing_ok=True)
    for stale in Path(storage.BACKUP_DIR).glob("*"):
        stale.unlink(missing_ok=True)


def make_project(project_id: str, name: str = "项目") -> dict:
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


class SchemaVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        wipe()

    def test_future_version_is_refused(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION + 1}")
        with self.assertRaises(storage.SchemaVersionError):
            storage.open_state_database()
        with self.assertRaises(storage.SchemaVersionError):
            storage.ensure_schema()
        # 拒绝打开不能把版本号改小
        self.assertEqual(storage.database_user_version(), storage.SCHEMA_VERSION + 1)

    def test_current_version_is_a_noop(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        self.assertEqual(storage.database_user_version(), storage.SCHEMA_VERSION)

    def _canonical_project_json(self, project_id: str, name: str) -> str:
        """用当前实现生成"规范形状"的项目 JSON（迁移校验要求逐字节可重建）。"""
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.replace_projects([make_project(project_id, name)])
        canonical = storage.read_project(project_id)[0]
        wipe()
        return json.dumps(canonical, ensure_ascii=False)

    def test_low_version_migrates_and_takes_snapshot(self) -> None:
        # 造一个 v0 的 legacy 库：project_state 单表 JSON
        payload = self._canonical_project_json("legacy-1", "老项目")
        with sqlite3.connect(DB) as connection:
            connection.execute(
                "CREATE TABLE project_state (project_id TEXT PRIMARY KEY, position INTEGER, "
                "payload TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                "INSERT INTO project_state(project_id,position,payload,updated_at,revision) VALUES(?,?,?,?,?)",
                ("legacy-1", 0, payload, "2026-09-01T00:00:00", 3),
            )
            connection.execute("PRAGMA user_version=0")

        storage.ensure_schema()

        self.assertEqual(storage.database_user_version(), storage.SCHEMA_VERSION)
        loaded = storage.read_project("legacy-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded[0]["name"], "老项目")
        self.assertEqual(loaded[1], 3)
        snapshots = sorted(path.name for path in Path(storage.BACKUP_DIR).glob("before-migrate-v0-*.sqlite3"))
        self.assertEqual(len(snapshots), 1, "迁移前必须留一份快照")

    def test_failed_migration_rolls_back_to_snapshot(self) -> None:
        with sqlite3.connect(DB) as connection:
            connection.execute(
                "CREATE TABLE project_state (project_id TEXT PRIMARY KEY, position INTEGER, "
                "payload TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0)"
            )
            # 坏的 payload：迁移过程中会解析失败
            connection.execute(
                "INSERT INTO project_state(project_id,position,payload,updated_at,revision) VALUES(?,?,?,?,?)",
                ("broken", 0, "{不是合法 JSON", "2026-09-01T00:00:00", 1),
            )
            connection.execute("PRAGMA user_version=0")

        with self.assertRaises((ValueError, RuntimeError, sqlite3.Error)):
            storage.ensure_schema()

        # 回滚后：版本没被改成 5，legacy 表和坏数据原样保留（可人工修复）
        self.assertEqual(storage.database_user_version(), 0)
        with sqlite3.connect(DB) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("project_state", tables)
            row = connection.execute("SELECT payload FROM project_state WHERE project_id='broken'").fetchone()
            self.assertEqual(row[0], "{不是合法 JSON")
        self.assertEqual(list(Path(storage.BACKUP_DIR).glob("before-migrate-v0-*.sqlite3")) != [], True,
                         "回滚前应先有快照")

    def test_memo_and_summary_refuse_future_version(self) -> None:
        for module, attribute in ((memo_storage, "MEMO_SCHEMA_VERSION"), (summary_storage, "SUMMARY_SCHEMA_VERSION")):
            path = Path(module.MEMO_DATABASE_FILE if hasattr(module, "MEMO_DATABASE_FILE") else module.SUMMARY_DATABASE_FILE)
            path.unlink(missing_ok=True)
            with module.open_memo_database() if hasattr(module, "open_memo_database") else module.open_summary_database() as connection:
                connection.execute(f"PRAGMA user_version={getattr(module, attribute) + 1}")
            opener = module.open_memo_database if hasattr(module, "open_memo_database") else module.open_summary_database
            with self.assertRaises(RuntimeError):
                opener()


class ImportValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        wipe()
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def test_duplicate_project_id_is_rejected(self) -> None:
        first, second = make_project("dup", "第一个"), make_project("dup", "第二个")
        with self.assertRaises(ValueError) as ctx:
            storage.replace_projects([first, second])
        message = str(ctx.exception)
        self.assertIn("重复的项目 ID", message)
        self.assertIn("dup", message)
        self.assertIn("第一个", message)
        self.assertIn("第二个", message)
        # 拒绝就应该是"什么都没写"
        self.assertEqual(storage.read_project_summaries(), [])

    def test_duplicate_node_id_reports_full_path(self) -> None:
        project = make_project("p1", "项目一")
        day = project["tree"][0]["children"][0]
        day["children"].append({
            "id": day["children"][0]["id"], "type": "item", "text": "任务2", "completed": False,
            "completedAt": None, "optional": False, "assessmentRequired": False,
            "assessmentHistory": 0, "assessment": None, "createdAt": "2026-09-15", "children": [],
        })
        with self.assertRaises(ValueError) as ctx:
            storage.replace_projects([project])
        message = str(ctx.exception)
        self.assertIn("节点 ID 重复", message)
        self.assertIn("第1周 / 单元1 / 任务2", message)

    def test_duplicate_node_id_across_projects_is_allowed(self) -> None:
        first, second = make_project("p1"), make_project("p2")
        storage.replace_projects([first, second])
        self.assertEqual(len(storage.read_project_summaries()), 2)

    def test_missing_ids_are_generated(self) -> None:
        project = make_project("placeholder")
        project.pop("id")
        project["tree"][0].pop("id")
        project["tree"][0]["children"][0].pop("id")
        storage.replace_projects([project])
        summaries = storage.read_project_summaries()
        self.assertEqual(len(summaries), 1)
        stored = storage.read_project(summaries[0]["id"])[0]
        self.assertEqual(len(str(stored["id"])), 36, "缺失的项目 ID 应生成 uuid")
        self.assertEqual(len(str(stored["tree"][0]["id"])), 36, "缺失的周 ID 应生成 uuid")
        self.assertEqual(len(str(stored["tree"][0]["children"][0]["id"])), 36, "缺失的单元 ID 应生成 uuid")
        self.assertEqual(stored["tree"][0]["children"][0]["children"][0]["text"], "任务1")

    def test_valid_import_still_works(self) -> None:
        storage.replace_projects([make_project("p1", "项目一"), make_project("p2", "项目二")])
        self.assertEqual(sorted(item["name"] for item in storage.read_project_summaries()), ["项目一", "项目二"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
