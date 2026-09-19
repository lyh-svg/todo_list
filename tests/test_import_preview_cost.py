"""P9 回归：导入预览不许为了统计数量把每个项目整棵树重建一遍。

旧实现：replace 模式为算"将被删除的节点数"，对每个被移除的项目 read_project() 重建整棵树；
merge/replace 的同 ID 项目也逐个读本地树。51 个项目 / 111,220 节点实测：
50 个项目全移除 2107.7 ms、50 个项目同 ID 2739.2 ms（单次 read_project 9.7 ms）。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-import-preview-cost-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import storage  # noqa: E402

TODAY = date.today().isoformat()
Base = storage._ManagedConnection


class CountingConnection(Base):
    statements: list[str] = []

    def execute(self, sql, *args, **kwargs):
        CountingConnection.statements.append(" ".join(str(sql).split()).upper())
        return super().execute(sql, *args, **kwargs)


def make_project(project_id: str, item_count: int, *, text: str = "任务") -> dict:
    items = [{"id": f"{project_id}-i{index}", "type": "item", "text": f"{text} {index}",
              "completed": False, "completedAt": None, "optional": False,
              "assessmentRequired": False, "assessmentHistory": 0, "createdAt": TODAY,
              "children": []} for index in range(item_count)]
    return {
        "id": project_id, "name": f"项目 {project_id}", "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": False,
        "tree": [{"id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
                  "expanded": False, "createdAt": TODAY, "children": [
                      {"id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                       "expanded": False, "createdAt": TODAY, "children": items}]}],
    }


def node_count(project: dict) -> int:
    return len(storage._walk_nodes(project.get("tree") or []))


class ImportPreviewCostTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        storage.ensure_schema()

    def count_sql(self, func):
        original = storage._ManagedConnection
        storage._ManagedConnection = CountingConnection
        CountingConnection.statements = []
        try:
            result = func()
        finally:
            storage._ManagedConnection = original
        return result, list(CountingConnection.statements)

    def test_deleted_nodes_count_matches_project_contents(self) -> None:
        local = [make_project("keep", 5), make_project("gone1", 7), make_project("gone2", 11)]
        storage.write_project(local[0], None)
        storage.write_project(local[1], None)
        storage.write_project(local[2], None)
        expected = node_count(local[1]) + node_count(local[2])
        preview = storage.preview_import([make_project("keep", 5)], "replace")
        self.assertEqual([entry["id"] for entry in preview["removedProjects"]], ["gone1", "gone2"])
        self.assertEqual(preview["totals"]["deletedNodes"], expected,
                         "将被删除的节点数必须仍然等于被移除项目的全部节点数")

    def test_replace_preview_does_not_rebuild_removed_projects(self) -> None:
        for index in range(8):
            storage.write_project(make_project(f"p{index}", 40), None)
        calls: list[str] = []
        original = storage.read_project
        storage.read_project = lambda project_id: (calls.append(str(project_id)), original(project_id))[1]
        try:
            preview, statements = self.count_sql(
                lambda: storage.preview_import([make_project("brand-new", 3)], "replace"))
        finally:
            storage.read_project = original
        self.assertEqual(len(preview["removedProjects"]), 8)
        self.assertEqual(preview["totals"]["deletedNodes"], 8 * node_count(make_project("p0", 40)))
        self.assertEqual(calls, [], "不许为了数节点逐个 read_project")
        selects = [sql for sql in statements if sql.startswith("SELECT")]
        self.assertLessEqual(len(selects), 6, f"预览的 SQL 条数应≤6，实际 {len(selects)}：{selects}")

    def test_matching_projects_are_diffed_without_reading_trees(self) -> None:
        local = [make_project(f"p{index}", 30) for index in range(10)]
        for project in local:
            storage.write_project(project, None)
        incoming = []
        for project in local:
            clone = storage._decode_object(storage._json(project), "夹具损坏")
            clone["tree"][0]["children"][0]["children"][0]["text"] = "改过的任务"
            incoming.append(clone)
        calls: list[str] = []
        original = storage.read_project
        storage.read_project = lambda project_id: (calls.append(str(project_id)), original(project_id))[1]
        try:
            preview, statements = self.count_sql(
                lambda: storage.preview_import(incoming, "merge"))
        finally:
            storage.read_project = original
        self.assertEqual(len(preview["updatedProjects"]), 10)
        entry = preview["updatedProjects"][0]
        self.assertEqual(entry["updatedNodes"], node_count(local[0]), "同 ID 项目仍要逐节点比对")
        self.assertEqual(entry["addedNodes"], 0)
        self.assertEqual(preview["totals"]["keptLocalOnlyNodes"], 0)
        self.assertEqual(calls, [], "不许为了比对逐个读本地树")
        selects = [sql for sql in statements if sql.startswith("SELECT")]
        self.assertLessEqual(len(selects), 8, f"预览的 SQL 条数应≤8，实际 {len(selects)}：{selects}")

    def test_preview_still_counts_added_and_local_only_nodes(self) -> None:
        storage.write_project(make_project("p1", 3), None)
        incoming = make_project("p1", 3)
        incoming["tree"][0]["children"][0]["children"].append({
            "id": "p1-extra", "type": "item", "text": "新任务", "completed": False,
            "completedAt": None, "optional": False, "assessmentRequired": False,
            "assessmentHistory": 0, "createdAt": TODAY, "children": []})
        preview = storage.preview_import([incoming], "merge")
        entry = preview["updatedProjects"][0]
        self.assertEqual(entry["addedNodes"], 1)
        self.assertEqual(entry["updatedNodes"], node_count(make_project("p1", 3)))
        # 本地独有：本地有 3 个任务节点 + 周/单元 = 5，导入文件里少了本地独有节点的情况
        local_only = make_project("p1", 3)
        local_only["tree"][0]["children"][0]["children"] = local_only["tree"][0]["children"][0]["children"][:1]
        preview = storage.preview_import([local_only], "merge")
        self.assertEqual(preview["totals"]["keptLocalOnlyNodes"], 2, "本地独有的任务节点必须照旧保留")


if __name__ == "__main__":
    unittest.main(verbosity=2)
