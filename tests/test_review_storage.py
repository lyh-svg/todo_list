import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-store-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402


def point(code="py.a.b", title="示例点", minutes=10, task_id="1103", relation="introduces"):
    return {
        "code": code, "title": title, "minutes": minutes, "module": "容器", "level": "基础",
        "taskRefs": ([{"taskId": task_id, "relation": relation}] if task_id else []),
        "concept": {"prompt": "概念题", "answer": ["要点"]},
        "predict": {"prompt": "预测题", "code": "print(1)", "expected": ["1"], "explain": "因为"},
        "debug": {"prompt": "排查题", "code": "x =", "rootCause": "语法错误", "fix": "改成 x = 1"},
        "code_task": {"prompt": "编程题", "acceptance": ["能跑"], "reference": "def f(): return 1"},
        "pitfalls": ["易错点"],
    }


class ReviewStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_point_tasks")

    def test_import_is_idempotent(self) -> None:
        first = review_storage.import_content([point()])
        second = review_storage.import_content([point()])
        self.assertEqual(first["inserted"], 1)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(review_storage.list_points()["total"], 1)

    def test_import_updates_changed_content_and_task_refs(self) -> None:
        review_storage.import_content([point(task_id="1103")])
        review_storage.import_content([point(title="改过的标题", minutes=15, task_id="1303")])
        listed = review_storage.list_points()
        self.assertEqual(listed["points"][0]["title"], "改过的标题")
        self.assertEqual(listed["points"][0]["minutes"], 15)
        with storage.open_state_database() as connection:
            rows = connection.execute("SELECT task_id, relation FROM review_point_tasks").fetchall()
        self.assertEqual([(row["task_id"], row["relation"]) for row in rows], [("1303", "introduces")])

    def test_point_without_taskref_is_allowed(self) -> None:
        review_storage.import_content([point(code="py.extra.json", task_id=None)])
        with storage.open_state_database() as connection:
            count = connection.execute("SELECT COUNT(*) FROM review_point_tasks").fetchone()[0]
        self.assertEqual(count, 0)
        self.assertEqual(review_storage.list_points(module="容器")["total"], 1)

    def test_ensure_content_imported_seeds_real_file(self) -> None:
        review_storage.ensure_content_imported()
        listed = review_storage.list_points()
        self.assertGreaterEqual(listed["total"], 1)
        self.assertTrue(any(entry["code"] == "py.mutability.default-arg" for entry in listed["points"]))

    def test_list_points_filters_by_query(self) -> None:
        review_storage.import_content([point(code="py.mutability.default-arg", title="可变默认参数"),
                                       point(code="py.dict.basics", title="字典基础")])
        self.assertEqual(review_storage.list_points(query="默认")["total"], 1)


if __name__ == "__main__":
    unittest.main()
