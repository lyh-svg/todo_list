"""启动导入课程库：空库幂等播种；内容文件缺失/损坏不阻断启动（临时库）。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-bootstrap-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

MIN_POINTS = 40


class ReviewBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_point_tasks")

    def test_bootstrap_seeds_empty_database_and_is_idempotent(self) -> None:
        self.assertEqual(review_storage.list_points()["total"], 0)
        first = review_storage.ensure_review_content_ready()
        self.assertGreater(first, 0)
        total = review_storage.list_points()["total"]
        self.assertGreaterEqual(total, MIN_POINTS)
        second = review_storage.ensure_review_content_ready()
        self.assertEqual(second, 0)
        self.assertEqual(review_storage.list_points()["total"], total)

    def test_missing_content_file_returns_zero_without_raising(self) -> None:
        missing = Path(_TEMP.name) / "no-such-content.json"
        with mock.patch.object(review_storage, "WEEK1_PATH", missing):
            self.assertEqual(review_storage.ensure_review_content_ready(), 0)

    def test_broken_content_file_returns_zero_without_raising(self) -> None:
        broken = Path(_TEMP.name) / "broken-content.json"
        broken.write_bytes(b"{ not json")
        with mock.patch.object(review_storage, "WEEK1_PATH", broken):
            self.assertEqual(review_storage.ensure_review_content_ready(), 0)

    def test_main_wires_startup_bootstrap(self) -> None:
        source = (APP_DIR / "local_server.py").read_text(encoding="utf-8")
        main_body = source.split("def main() -> None:", 1)[1]
        self.assertIn("ensure_review_content_ready()", main_body)


if __name__ == "__main__":
    unittest.main()
