"""P7 回归：复习队列构建不再逐条目回查（limit=50 时 51 次开库 / 406 条 SQL → 1 次 / 几条）。

旧实现每个条目 3 次查询：pick_question_type（**还各自开一次库**）+ _prompt_of + _question_body；
一次 /api/review/queue 只为读 limit/newPerDay 还会先跑一遍完整 summary()。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-review-queue-batch-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import review_content  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-19"

CONNECTIONS: list[int] = []
STATEMENTS: list[str] = []
Base = storage._ManagedConnection


class CountingConnection(Base):
    def execute(self, sql, *args, **kwargs):
        STATEMENTS.append(" ".join(str(sql).split()).upper())
        return super().execute(sql, *args, **kwargs)


def reference_prompt(code: str, question_type: str) -> str:
    """独立复算：题面 prompt 必须来自 content_json[question_type].prompt。"""
    with storage.open_state_database() as connection:
        row = connection.execute("SELECT content_json FROM review_points WHERE code=?", (code,)).fetchone()
    if row is None:
        return ""
    return str((json.loads(row["content_json"]).get(question_type) or {}).get("prompt") or "")


def reference_body(code: str, question_type: str) -> str:
    with storage.open_state_database() as connection:
        row = connection.execute("SELECT content_json FROM review_points WHERE code=?", (code,)).fetchone()
    if row is None:
        return ""
    block = json.loads(row["content_json"]).get(question_type) or {}
    return str(block.get("code") or "")


class QueueBatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        storage.ensure_schema()
        review_storage.ensure_content_imported()

    def setUp(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_attempts")
            connection.execute("DELETE FROM review_states")

    def seed_due_points(self, count: int = 60, due: str = TODAY) -> list[str]:
        with storage.open_state_database() as connection:
            codes = [str(row[0]) for row in connection.execute(
                "SELECT code FROM review_points ORDER BY code LIMIT ?", (count,))]
            connection.executemany(
                "INSERT INTO review_states(code,due,interval_days,streak,lapses,weak,last_grade,last_reviewed_at) "
                "VALUES(?,?,1,0,0,0,0,'')", [(code, due) for code in codes])
        return codes

    def measure(self, func):
        global STATEMENTS
        original = storage._ManagedConnection
        storage._ManagedConnection = CountingConnection
        STATEMENTS = []
        CONNECTIONS.clear()
        try:
            result = func()
        finally:
            storage._ManagedConnection = original
        return result, list(STATEMENTS)

    def setUp_counted_open(self):
        self._original_open = storage.open_state_database

        def counted():
            CONNECTIONS.append(1)
            return self._original_open()

        storage.open_state_database = counted

    def tearDown_counted_open(self):
        storage.open_state_database = self._original_open

    # ---- ① 不再 N+1 ----

    def test_queue_build_uses_one_connection_and_few_queries(self) -> None:
        self.seed_due_points(60)
        self.setUp_counted_open()
        try:
            queue, statements = self.measure(
                lambda: review_storage.build_queue(TODAY, 50, new_per_day=0))
        finally:
            self.tearDown_counted_open()
        self.assertEqual(queue["total"], 50)
        selects = [sql for sql in statements if sql.startswith("SELECT")]
        self.assertEqual(len(CONNECTIONS), 1, f"应该只开一次库，实际 {len(CONNECTIONS)} 次")
        self.assertLessEqual(len(selects), 5, f"SQL 条数应≤5，实际 {len(selects)}：{selects}")
        self.assertLessEqual(
            sum(1 for sql in selects if "CONTENT_JSON" in sql), 1,
            "题面内容必须一次查完，不能逐条目回查")
        self.assertLessEqual(
            sum(1 for sql in selects if "REVIEW_ATTEMPTS" in sql), 1,
            "题型轮换必须一次查完")

    def test_queue_fields_match_reference(self) -> None:
        codes = self.seed_due_points(12)
        # 给其中两个点留下作答记录，让题型轮换真的起作用
        review_storage.apply_grade(codes[0], "concept", 3, today=TODAY)
        review_storage.apply_grade(codes[0], "predict", 4, today=TODAY)
        review_storage.apply_grade(codes[1], "debug", 2, today=TODAY)
        queue = review_storage.build_queue(TODAY, 12, new_per_day=0)
        self.assertEqual(len(queue["items"]), 12)
        for item in queue["items"]:
            kind = item["questionType"]
            self.assertIn(kind, review_content.QUESTION_TYPES)
            self.assertEqual(kind, review_storage.pick_question_type(item["code"], TODAY),
                             f"{item['code']} 的题型轮换结果变了")
            self.assertEqual(item["prompt"], reference_prompt(item["code"], kind), item["code"])
            self.assertEqual(item["body"], reference_body(item["code"], kind), item["code"])

    def test_batched_rotation_prefers_least_used_type(self) -> None:
        codes = self.seed_due_points(4)
        review_storage.apply_grade(codes[0], "concept", 3, today=TODAY)
        queue = review_storage.build_queue(TODAY, 4, new_per_day=0)
        by_code = {item["code"]: item["questionType"] for item in queue["items"]}
        self.assertNotEqual(by_code[codes[0]], "concept", "用过 concept 之后不该再选它")
        self.assertEqual(by_code[codes[1]], review_content.QUESTION_TYPES[0], "没用过的点按声明顺序")

    def test_explicit_question_type_skips_rotation_query(self) -> None:
        self.seed_due_points(3)
        queue, statements = self.measure(
            lambda: review_storage.build_queue(TODAY, 3, new_per_day=0, question_type="predict"))
        self.assertEqual([item["questionType"] for item in queue["items"]], ["predict"] * 3)
        self.assertEqual(
            [sql for sql in statements if "REVIEW_ATTEMPTS" in sql], [],
            "指定题型时不该再查轮换表")
        for item in queue["items"]:
            self.assertEqual(item["prompt"], reference_prompt(item["code"], "predict"))
            self.assertEqual(item["body"], reference_body(item["code"], "predict"))

    def test_queue_still_never_leaks_answers(self) -> None:
        codes = self.seed_due_points(3)
        for kind in review_content.QUESTION_TYPES:
            queue = review_storage.build_queue(TODAY, 3, new_per_day=0, question_type=kind)
            for item in queue["items"]:
                for key in ("answer", "expected", "explain", "rootCause", "fix",
                            "acceptance", "reference"):
                    self.assertNotIn(key, item, f"{codes} {kind} 泄漏了 {key}")
                self.assertTrue(item["prompt"])

    def test_limit_and_truncated_semantics_unchanged(self) -> None:
        """批量取内容不能改掉 limit / truncated 的口径（60 个到期点，分别取 10 / 50）。"""
        self.seed_due_points(60)
        small = review_storage.build_queue(TODAY, 10, new_per_day=0)
        self.assertEqual(small["limit"], 10)
        self.assertEqual(small["total"], 10)
        self.assertTrue(small["truncated"])
        full = review_storage.build_queue(TODAY, 50, new_per_day=0)
        self.assertEqual(full["limit"], 50)
        self.assertEqual(full["total"], 50)
        self.assertTrue(full["truncated"])
        for item in full["items"]:
            self.assertTrue(item["prompt"])
            self.assertTrue(item["questionType"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
