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
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"


def seed(code="py.a.b"):
    review_storage.import_content([{
        "code": code, "title": "示例点", "minutes": 10, "module": "容器", "level": "基础",
        "taskRefs": [], "concept": {"prompt": "p", "answer": ["a"]},
        "predict": {"prompt": "p", "code": "print(1)", "expected": ["1"], "explain": "e"},
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


if __name__ == "__main__":
    unittest.main()
