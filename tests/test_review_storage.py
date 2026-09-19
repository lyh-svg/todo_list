import contextlib
import io
import json
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
        review_storage.apply_grade("py.a.b", "predict", 5, today="2026-09-16", answer="对的")
        self.assertEqual(len(review_storage.recent_attempts("wrong", "2026-09-16")), 1)
        self.assertEqual(len(review_storage.recent_attempts("mastered", "2026-09-16")), 1)

    def test_summary_reports_recent_attempts_not_last_grade(self) -> None:
        """最近答错/最近掌握必须是作答记录（含题干/题型/档位/日期/答案），不是知识点 lastGrade。"""
        review_storage.apply_grade("py.a.b", "concept", 1, today="2026-09-16", answer="错的")
        review_storage.apply_grade("py.a.b", "predict", 5, today="2026-09-16", answer="对的")
        data = review_storage.summary("2026-09-16")
        # summary() 的键集合锁死为：10 个旧键 + 新增 recentWrong/recentMastered = 12 个。
        self.assertEqual(set(data), {
            "dueToday", "overdue", "upcoming", "weak", "total", "learned", "answeredToday",
            "streakDays", "limit", "newPerDay", "recentWrong", "recentMastered"})
        self.assertEqual([entry["answer"] for entry in data["recentWrong"]], ["错的"])
        self.assertEqual([entry["questionType"] for entry in data["recentWrong"]], ["concept"])
        self.assertEqual(data["recentWrong"][0]["grade"], 1)
        self.assertEqual(data["recentWrong"][0]["reviewedOn"], "2026-09-16")
        self.assertEqual(data["recentWrong"][0]["title"], "示例点")
        self.assertEqual([entry["answer"] for entry in data["recentMastered"]], ["对的"])
        self.assertEqual([entry["questionType"] for entry in data["recentMastered"]], ["predict"])
        self.assertEqual(data["recentMastered"][0]["grade"], 5)

    def test_recent_attempts_carry_module_for_group_filtering(self) -> None:
        """模块筛选必须作用于"最近答错/最近掌握"两组：记录要带 p.module。

        修复前 recent_attempts 的 SQL 不查 module，summary 的最近记录就没有模块字段，
        前端这两组只按题型过滤，"选了模块却还显示别的模块"。
        """
        review_storage.import_content([
            point(code="py.container.list", title="容器点"),            # point() 默认 module=容器
            {**point(code="py.func.def", title="函数点"), "module": "函数"},
        ])
        review_storage.apply_grade("py.container.list", "concept", 1, today="2026-09-16", answer="错的")
        review_storage.apply_grade("py.func.def", "concept", 5, today="2026-09-16", answer="对的")
        wrong = review_storage.recent_attempts("wrong", "2026-09-16")
        mastered = review_storage.recent_attempts("mastered", "2026-09-16")
        self.assertEqual([entry["module"] for entry in wrong], ["容器"])
        self.assertEqual([entry["module"] for entry in mastered], ["函数"])
        data = review_storage.summary("2026-09-16")
        self.assertEqual([entry["module"] for entry in data["recentWrong"]], ["容器"])
        self.assertEqual([entry["module"] for entry in data["recentMastered"]], ["函数"])

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

    def test_settings_control_queue_limit_and_new_slots(self) -> None:
        storage.update_app_settings({"reviewDailyLimit": 7, "reviewNewPerDay": 3})
        settings = review_storage._settings()
        self.assertEqual(settings["limit"], 7)
        self.assertEqual(settings["newPerDay"], 3)
        storage.update_app_settings({"reviewDailyLimit": 99, "reviewNewPerDay": -5})
        settings = review_storage._settings()
        self.assertEqual(settings["limit"], 15)
        self.assertEqual(settings["newPerDay"], 0)

    def test_streak_counts_consecutive_days(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 3, today="2026-09-15")
        review_storage.apply_grade("py.a.b", "predict", 3, today="2026-09-16")
        self.assertEqual(review_storage.streak_days("2026-09-16"), 2)


class MultiWeekContentImportTests(unittest.TestCase):
    """多周课程库：扫描 py-week*.json 逐个导入；单个文件损坏只跳过，不阻断启动。"""

    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_point_tasks")

    @staticmethod
    def write_week(directory: str, name: str, week: int, codes: list[str]) -> Path:
        payload = {"schemaVersion": 1, "week": week, "level": "实用",
                   "points": [point(code=code, title=code) for code in codes]}
        path = Path(directory) / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_scans_every_week_file_sorted_by_week_number(self) -> None:
        """按周编号排序：py-week10 必须排在 py-week2 之后（字典序会把它排到前面）。"""
        with tempfile.TemporaryDirectory(prefix="todo-review-weeks-") as work:
            self.write_week(work, "py-week10.json", 10, ["py.w10.a"])
            self.write_week(work, "py-week2.json", 2, ["py.w2.b", "py.w2.a"])
            self.write_week(work, "py-week1.json", 1, ["py.w1.a"])
            with mock.patch.object(review_storage, "WEEK1_PATH", Path(work) / "py-week1.json"):
                names = [path.name for path in review_storage.content_paths()]
                total = review_storage.ensure_content_imported()
        self.assertEqual(names, ["py-week1.json", "py-week2.json", "py-week10.json"],
                         "导入顺序必须按周编号，而不是文件名字典序")
        self.assertEqual(total, 4)
        self.assertEqual(review_storage.list_points()["total"], 4)

    def test_repeat_scan_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="todo-review-weeks-") as work:
            self.write_week(work, "py-week1.json", 1, ["py.w1.a"])
            self.write_week(work, "py-week2.json", 2, ["py.w2.a"])
            with mock.patch.object(review_storage, "WEEK1_PATH", Path(work) / "py-week1.json"):
                first = review_storage.ensure_content_imported()
                second = review_storage.ensure_content_imported()
        self.assertEqual(first, 2)
        self.assertEqual(second, 0)

    def test_broken_file_is_skipped_and_others_still_import(self) -> None:
        with tempfile.TemporaryDirectory(prefix="todo-review-weeks-") as work:
            good = self.write_week(work, "py-week1.json", 1, ["py.w1.a"])
            (Path(work) / "py-week2.json").write_text("{ 不是 JSON", encoding="utf-8")
            warning = io.StringIO()
            with mock.patch.object(review_storage, "WEEK1_PATH", good), \
                    contextlib.redirect_stderr(warning):
                total = review_storage.ensure_content_imported()
                ready = review_storage.ensure_review_content_ready()
        self.assertEqual(total, 1)
        self.assertEqual(ready, 0)
        self.assertIn("py-week2.json", warning.getvalue())
        self.assertIn("跳过", warning.getvalue())
        self.assertEqual(review_storage.list_points()["total"], 1)


if __name__ == "__main__":
    unittest.main()
