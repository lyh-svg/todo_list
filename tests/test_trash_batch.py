"""回收站批量操作与到期提示（⑩）的回归测试。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-trash-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")

import storage  # noqa: E402


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


class TrashBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def _trash_one(self, project_id: str, name: str) -> str:
        storage.replace_projects([make_project(project_id, name)])
        revision = storage.read_project_summaries()[0]["_revision"]
        storage.delete_project(project_id, revision)
        items = storage.list_trash_items()
        return next(item["id"] for item in items if item["projectId"] == project_id)

    def test_items_report_expiry(self) -> None:
        self._trash_one("p1", "待删项目")
        item = storage.list_trash_items()[0]
        self.assertTrue(item["expiresAt"], "列表必须给出自动清理时间，UI 才能提示")
        self.assertEqual(storage.TRASH_RETENTION_DAYS, 7)

    def test_batch_restore_reports_per_item_result(self) -> None:
        first = self._trash_one("p1", "第一个")
        second = self._trash_one("p2", "第二个")

        result = storage.restore_trash_items([first, second, "不存在的-id"])

        self.assertEqual(sorted(result["restored"]), sorted([first, second]))
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["id"], "不存在的-id")
        self.assertEqual(sorted(item["name"] for item in storage.read_project_summaries()),
                         ["第一个", "第二个"])

    def test_batch_restore_conflict_is_reported_not_fatal(self) -> None:
        first = self._trash_one("p1", "第一个")
        second = self._trash_one("p2", "第二个")
        # 先恢复一个，让第二个的恢复与现有项目冲突
        storage.replace_projects([make_project("p2", "占位")])

        result = storage.restore_trash_items([first, second])

        self.assertEqual(result["restored"], [first])
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["id"], second)
        self.assertIn("已经存在", result["failed"][0]["error"])
        self.assertTrue(any(item["name"] == "第一个" for item in storage.read_project_summaries()))

    def test_batch_delete_removes_only_listed_items(self) -> None:
        first = self._trash_one("p1", "第一个")
        second = self._trash_one("p2", "第二个")

        result = storage.delete_trash_items([first])

        self.assertEqual(result["deleted"], [first])
        self.assertEqual(result["failed"], [])
        remaining = [item["id"] for item in storage.list_trash_items()]
        self.assertEqual(remaining, [second])

    def test_clear_trash_items_empties_everything(self) -> None:
        self._trash_one("p1", "第一个")
        self._trash_one("p2", "第二个")
        removed = storage.clear_trash_items()
        self.assertEqual(removed, 2)
        self.assertEqual(storage.list_trash_items(), [])

    def test_deleted_project_payload_is_restorable_with_tree(self) -> None:
        """回收站里的项目必须是完整树，恢复后节点一个不少。"""
        trash_id = self._trash_one("p1", "带树的项目")
        storage.restore_trash_items([trash_id])
        restored = storage.read_project_summaries()
        self.assertEqual(len(restored), 1)
        project = storage.read_project(restored[0]["id"])[0]
        self.assertEqual(project["tree"][0]["text"], "第1周")
        self.assertEqual(project["tree"][0]["children"][0]["children"][0]["text"], "任务1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
