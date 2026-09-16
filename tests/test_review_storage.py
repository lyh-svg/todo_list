import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_taskrefs_only_change_rebuilds_links(self) -> None:
        review_storage.import_content([point(task_id="1103")])
        result = review_storage.import_content([point(task_id="1303")])
        with storage.open_state_database() as connection:
            rows = connection.execute("SELECT task_id, relation FROM review_point_tasks").fetchall()
        self.assertEqual([(row["task_id"], row["relation"]) for row in rows], [("1303", "introduces")])
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["unchanged"], 1)

    def test_repeated_import_does_not_duplicate_taskrefs(self) -> None:
        review_storage.import_content([point(task_id="1103")])
        review_storage.import_content([point(task_id="1103")])
        with storage.open_state_database() as connection:
            task_rows = connection.execute("SELECT COUNT(*) FROM review_point_tasks").fetchone()[0]
            point_rows = connection.execute("SELECT COUNT(*) FROM review_points").fetchone()[0]
        self.assertEqual(task_rows, 1)
        self.assertEqual(point_rows, 1)

    def test_import_does_not_overwrite_origin(self) -> None:
        review_storage.import_content([point()], origin="builtin")
        result = review_storage.import_content([point()], origin="ai")
        with storage.open_state_database() as connection:
            stored = connection.execute(
                "SELECT origin FROM review_points WHERE code=?", (point()["code"],)).fetchone()[0]
        self.assertEqual(stored, "builtin")
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["unchanged"], 1)


class SummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            for table in ("review_points", "review_states", "review_attempts"):
                connection.execute(f"DELETE FROM {table}")
        review_storage.import_content([point(code="py.a.b")])

    def test_summary_counts_buckets(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute("UPDATE review_states SET due='2026-09-10' WHERE code='py.a.b'")
        data = review_storage.summary("2026-09-16")
        self.assertEqual(data["overdue"], 1)
        self.assertEqual(data["dueToday"], 0)
        self.assertEqual(data["learned"], 1)

    def test_recent_wrong_and_mastered(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 1, today="2026-09-16", answer="错的")
        review_storage.apply_grade("py.a.b", "predict", 5, today="2026-09-16")
        self.assertEqual(len(review_storage.recent_attempts("wrong", "2026-09-16")), 1)
        self.assertEqual(len(review_storage.recent_attempts("mastered", "2026-09-16")), 1)

    def test_history_returns_answers_and_pitfalls(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 2, today="2026-09-16", answer="我写的")
        data = review_storage.history("py.a.b")
        self.assertEqual(data["attempts"][0]["answer"], "我写的")
        self.assertEqual(data["pitfalls"], ["易错点"])

    def test_settings_defaults_only_when_missing(self) -> None:
        cases = [
            ({}, {"limit": 10, "newPerDay": 2}),
            ({"reviewDailyLimit": 5, "reviewNewPerDay": 0}, {"limit": 5, "newPerDay": 0}),
            ({"reviewDailyLimit": "7", "reviewNewPerDay": "0"}, {"limit": 7, "newPerDay": 0}),
            ({"reviewDailyLimit": 99, "reviewNewPerDay": -5}, {"limit": 15, "newPerDay": 0}),
            ({"reviewDailyLimit": "abc", "reviewNewPerDay": None}, {"limit": 10, "newPerDay": 2}),
        ]
        for settings, expected in cases:
            with self.subTest(settings=settings):
                with mock.patch.object(storage, "read_app_settings", return_value=settings):
                    self.assertEqual(review_storage._settings(), expected)

    def test_streak_counts_consecutive_days(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 3, today="2026-09-15")
        review_storage.apply_grade("py.a.b", "predict", 3, today="2026-09-16")
        self.assertEqual(review_storage.streak_days("2026-09-16"), 2)


if __name__ == "__main__":
    unittest.main()
