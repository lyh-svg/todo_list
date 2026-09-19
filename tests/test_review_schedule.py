import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-sched-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"


def seed(code="py.a.b"):
    review_storage.import_content([{
        "code": code, "title": "示例点", "minutes": 10, "module": "容器", "level": "基础",
        "taskRefs": [], "concept": {"prompt": "p", "answer": ["a"]},
        "predict": {"prompt": "写出下面代码的输出", "code": "def add(a, b):\n    return a + b\n\nprint(add(1, 2))",
                    "expected": ["3"], "explain": "e"},
        "debug": {"prompt": "p", "code": "x =", "rootCause": "r", "fix": "f"},
        "code_task": {"prompt": "p", "acceptance": ["a"], "reference": "r"}, "pitfalls": ["p"],
    }])


class NextScheduleTests(unittest.TestCase):
    def test_grade_intervals(self) -> None:
        cases = {2: 3, 3: 7, 4: 14, 5: 30}
        for grade, interval in cases.items():
            result = review_storage.next_schedule(
                grade, interval_days=0, streak=0, lapses=0, today=TODAY, answered_today=False)
            self.assertEqual(result["intervalDays"], interval, grade)
        self.assertEqual(review_storage.next_schedule(
            3, interval_days=0, streak=0, lapses=0, today=TODAY, answered_today=False)["due"], "2026-09-23")

    def test_grade_one_same_day_when_not_answered_yet(self) -> None:
        result = review_storage.next_schedule(
            1, interval_days=7, streak=3, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(result["due"], TODAY)
        self.assertEqual(result["lapses"], 1)
        self.assertEqual(result["streak"], 0)

    def test_grade_one_defers_to_tomorrow_when_already_answered(self) -> None:
        result = review_storage.next_schedule(
            1, interval_days=7, streak=3, lapses=0, today=TODAY, answered_today=True)
        self.assertEqual(result["due"], "2026-09-17")

    def test_high_grades_grow_interval_with_caps(self) -> None:
        grown = review_storage.next_schedule(
            4, interval_days=14, streak=1, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(grown["intervalDays"], 21)
        capped = review_storage.next_schedule(
            4, interval_days=40, streak=5, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(capped["intervalDays"], 60)
        top = review_storage.next_schedule(
            5, interval_days=60, streak=5, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(top["intervalDays"], 90)

    def test_weak_after_two_lapses(self) -> None:
        first = review_storage.next_schedule(
            1, interval_days=0, streak=0, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(first["weak"], False)
        second = review_storage.next_schedule(
            1, interval_days=1, streak=0, lapses=first["lapses"], today=TODAY, answered_today=True)
        self.assertEqual(second["weak"], True)


class ApplyGradeTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_states")
            connection.execute("DELETE FROM review_attempts")
        seed()

    def test_apply_grade_records_attempt_and_state(self) -> None:
        result = review_storage.apply_grade(
            "py.a.b", "concept", 4, today=TODAY, answer="我的答案", duration_ms=2500, session_id="s1")
        self.assertEqual(result["intervalDays"], 14)
        self.assertEqual(result["due"], "2026-09-30")
        state = review_storage.read_state("py.a.b")
        self.assertEqual(state["lastGrade"], 4)
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT code,question_type,grade,answer,duration_ms,session_id,reviewed_on "
                "FROM review_attempts").fetchone()
        self.assertEqual((row["code"], row["question_type"], row["grade"], row["answer"]),
                         ("py.a.b", "concept", 4, "我的答案"))
        self.assertEqual(row["reviewed_on"], TODAY)

    def test_repeated_failures_mark_weak_and_clear_after_two_good(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 1, today=TODAY)
        review_storage.apply_grade("py.a.b", "predict", 2, today=TODAY)
        self.assertTrue(review_storage.read_state("py.a.b")["weak"])
        review_storage.apply_grade("py.a.b", "debug", 4, today=TODAY)
        review_storage.apply_grade("py.a.b", "code_task", 5, today=TODAY)
        self.assertFalse(review_storage.read_state("py.a.b")["weak"])

    def test_recovery_sticks_after_two_good_grades(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 1, today=TODAY)
        review_storage.apply_grade("py.a.b", "predict", 2, today=TODAY)
        self.assertTrue(review_storage.read_state("py.a.b")["weak"])
        review_storage.apply_grade("py.a.b", "debug", 4, today=TODAY)
        review_storage.apply_grade("py.a.b", "code_task", 4, today=TODAY)
        state = review_storage.read_state("py.a.b")
        self.assertFalse(state["weak"])
        self.assertEqual(state["lapses"], 0)
        review_storage.apply_grade("py.a.b", "predict", 3, today=TODAY)
        state = review_storage.read_state("py.a.b")
        self.assertFalse(state["weak"])
        self.assertEqual(state["lapses"], 0)

    def test_rejects_out_of_range_grade(self) -> None:
        with self.assertRaises(ValueError):
            review_storage.apply_grade("py.a.b", "concept", 9, today=TODAY)


class QueueTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            for table in ("review_points", "review_states", "review_attempts", "review_sessions"):
                connection.execute(f"DELETE FROM {table}")
        for code in ("py.a.overdue", "py.a.today", "py.a.weak", "py.a.future", "py.a.new"):
            seed(code)

    def _set_state(self, code, due, weak=0, interval=0):
        with storage.open_state_database() as connection:
            connection.execute(
                "UPDATE review_states SET due=?,weak=?,interval_days=? WHERE code=?",
                (due, weak, interval, code))

    def test_queue_orders_overdue_then_today_then_weak(self) -> None:
        self._set_state("py.a.overdue", "2026-09-10")
        self._set_state("py.a.today", TODAY)
        self._set_state("py.a.weak", "2026-10-30", weak=1)
        self._set_state("py.a.future", "2026-10-01")
        queue = review_storage.build_queue(TODAY, limit=3, new_per_day=0)
        self.assertEqual([item["code"] for item in queue["items"]],
                         ["py.a.overdue", "py.a.today", "py.a.weak"])
        self.assertEqual([item["reason"] for item in queue["items"]], ["overdue", "today", "weak"])

    def test_queue_respects_limit_and_reports_truncation(self) -> None:
        self._set_state("py.a.overdue", "2026-09-10")
        self._set_state("py.a.today", TODAY)
        queue = review_storage.build_queue(TODAY, limit=1)
        self.assertEqual(len(queue["items"]), 1)
        self.assertTrue(queue["truncated"])

    def test_queue_includes_new_points_up_to_new_per_day(self) -> None:
        queue = review_storage.build_queue(TODAY, limit=5, new_per_day=1)
        reasons = [item["reason"] for item in queue["items"]]
        self.assertEqual(reasons.count("new"), 1, reasons)

    def test_queue_never_returns_answers(self) -> None:
        self._set_state("py.a.today", TODAY)
        item = review_storage.build_queue(TODAY, limit=1)["items"][0]
        for key in ("answer", "expected", "explain", "rootCause", "fix", "acceptance", "reference"):
            self.assertNotIn(key, item)
        self.assertTrue(item["prompt"])

    def test_queue_includes_question_body_code_but_not_answers(self) -> None:
        # predict/debug 的题面代码片段必须随队列下发：只给 prompt 的话用户根本看不到要预测的代码。
        self._set_state("py.a.today", TODAY)
        item = review_storage.build_queue(TODAY, limit=1, question_type="predict")["items"][0]
        self.assertEqual(item["questionType"], "predict")
        self.assertIn("def add(", item["body"])
        # 题面代码 ≠ 答案：禁用键一个都不能出现。
        for key in ("answer", "expected", "explain", "rootCause", "fix", "acceptance", "reference"):
            self.assertNotIn(key, item)

    def test_today_bucket_sorted_by_code_and_stable(self) -> None:
        for code in ("py.a.overdue", "py.a.weak", "py.a.today"):
            self._set_state(code, TODAY)
        first = review_storage.build_queue(TODAY, limit=5, new_per_day=0)
        codes = [item["code"] for item in first["items"]]
        self.assertEqual([item["reason"] for item in first["items"]], ["today"] * 3)
        self.assertEqual(codes, sorted(codes))
        second = review_storage.build_queue(TODAY, limit=5, new_per_day=0)
        self.assertEqual(codes, [item["code"] for item in second["items"]])

    def test_rejects_invalid_explicit_question_type(self) -> None:
        with self.assertRaises(ValueError):
            review_storage.build_queue(TODAY, question_type="essay")

    def test_question_type_rotation_prefers_least_used(self) -> None:
        review_storage.apply_grade("py.a.today", "concept", 3, today=TODAY)
        self.assertNotEqual(review_storage.pick_question_type("py.a.today", TODAY), "concept")

    def test_question_type_defaults_to_concept_for_fresh_point(self) -> None:
        self.assertEqual(review_storage.pick_question_type("py.a.today", TODAY), "concept")

    def test_session_lifecycle(self) -> None:
        session_id = review_storage.start_session(planned=3)
        review_storage.finish_session(session_id, answered=2, grade_counts={3: 1, 4: 1}, duration_ms=5000)
        with storage.open_state_database() as connection:
            row = connection.execute("SELECT * FROM review_sessions WHERE id=?", (session_id,)).fetchone()
        self.assertEqual(row["answered"], 2)
        self.assertEqual(json.loads(row["grade_counts_json"]), {"3": 1, "4": 1})


if __name__ == "__main__":
    unittest.main()
