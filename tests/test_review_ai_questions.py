"""AI 加练题（收藏库）的存储层回归：收藏 / 去重 / 列表 / 读取 / 删除 / 出题上下文。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-ai-questions-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")

import review_content  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402

POINT = {
    "code": "py.mutability.default-arg", "title": "可变默认参数与求值时机",
    "minutes": 20, "module": "函数", "level": "基础",
    "taskRefs": [{"taskId": "1103", "relation": "introduces"}],
    "concept": {"prompt": "默认参数什么时候求值？", "answer": ["函数定义时求值一次"]},
    "predict": {"prompt": "写出输出", "code": "print(1)", "expected": ["1"], "explain": "常量"},
    "debug": {"prompt": "找 bug", "code": "x = 1", "rootCause": "无", "fix": "无"},
    "code_task": {"prompt": "写实现", "acceptance": ["能跑"], "reference": "def f(): return 1"},
    "pitfalls": ["默认值是可变对象"],
}
REFERENCE = {"answer": ["定义时求值一次"], "expected": ["[1]", "[1, 2]"],
             "explain": "两次调用共享同一个列表",
             "reference": "def f(items=None):\n    items = [] if items is None else items"}


class AiQuestionStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_point_tasks")
            connection.execute("DELETE FROM review_attempts")
            connection.execute("DELETE FROM review_states")
            connection.execute("DELETE FROM review_ai_questions")
        review_storage.import_content([POINT], week=1)

    def _collect(self, prompt: str = "现场出的题：写出 f() 两次调用的输出",
                 kind: str = "predict") -> dict:
        return review_storage.collect_ai_question(
            POINT["code"], kind, prompt, "def f(items=[]):\n    items.append(1)\n    return items",
            "可变默认参数", dict(REFERENCE))

    def test_collect_then_list_without_reference(self) -> None:
        saved = self._collect()
        self.assertFalse(saved["duplicated"])
        items = review_storage.list_ai_questions(POINT["code"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], saved["id"])
        self.assertEqual(items[0]["questionType"], "predict")
        self.assertEqual(items[0]["focus"], "可变默认参数")
        self.assertNotIn("reference", items[0], "列表不能吐参考答案")
        self.assertNotIn("reference", items[0].get("content_json", ""), items[0])

    def test_collect_is_idempotent_for_identical_question(self) -> None:
        first = self._collect()
        second = self._collect()
        self.assertTrue(second["duplicated"])
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(len(review_storage.list_ai_questions(POINT["code"])), 1)

    def test_collect_rejects_unknown_point_and_empty_reference(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            review_storage.collect_ai_question("py.nope.nope", "predict", "题面", "", "", dict(REFERENCE))
        self.assertIn("知识点不存在", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx2:
            review_storage.collect_ai_question(POINT["code"], "predict", "题面", "", "", {})
        self.assertIn("参考解", str(ctx2.exception))

    def test_read_and_delete_question(self) -> None:
        saved = self._collect()
        stored = review_storage.read_ai_question(saved["id"])
        self.assertEqual(stored["prompt"], "现场出的题：写出 f() 两次调用的输出")
        self.assertEqual(stored["reference"]["expected"], ["[1]", "[1, 2]"])
        self.assertEqual(stored["pointCode"], POINT["code"])
        self.assertEqual(stored["code"], "def f(items=[]):\n    items.append(1)\n    return items",
                         "题面代码与知识点 code 不能互相覆盖")
        self.assertIsNone(review_storage.read_ai_question("no-such-id"))
        result = review_storage.delete_ai_question(saved["id"])
        self.assertEqual(result["code"], POINT["code"])
        self.assertEqual(result["items"], [])
        self.assertIsNone(review_storage.read_ai_question(saved["id"]))
        with self.assertRaises(ValueError) as ctx:
            review_storage.delete_ai_question("no-such-id")
        self.assertIn("不存在", str(ctx.exception))

    def test_list_all_when_code_omitted(self) -> None:
        self._collect("第一题")
        self._collect("第二题")
        self.assertEqual(len(review_storage.list_ai_questions()), 2)
        self.assertEqual(len(review_storage.list_ai_questions(POINT["code"])), 2)

    def test_context_carries_point_prompts_and_recent_history(self) -> None:
        review_storage.apply_grade(POINT["code"], "concept", 2, today="2026-09-19",
                                   answer="我答错了")
        # 注意：`weak` 不是"答过一次 2 分"就会有 —— 现有语义要求 lapses≥WEAK_LAPSES(2)
        # 或显式 mark_weak（见 review_storage.mark_weak 的说明）。这里显式标弱，
        # 才能同时覆盖"最近作答"与"薄弱标记"两条上下文来源。
        review_storage.mark_weak([POINT["code"]])
        context = review_storage.ai_question_context(POINT["code"])
        self.assertEqual(context["title"], POINT["title"])
        self.assertEqual(context["module"], "函数")
        self.assertEqual(context["pitfalls"], ["默认值是可变对象"])
        self.assertTrue(context["existingPrompts"]["concept"], "要带上现有题面做风格参考")
        self.assertNotIn("answer", context["existingPrompts"], "上下文不能泄露参考答案")
        self.assertEqual(len(context["history"]), 1)
        self.assertEqual(context["history"][0]["questionType"], "concept")
        self.assertEqual(context["history"][0]["grade"], 2)
        self.assertEqual(context["history"][0]["answer"], "我答错了")
        self.assertTrue(context["weak"])

    def test_context_rejects_unknown_code(self) -> None:
        with self.assertRaises(ValueError):
            review_storage.ai_question_context("py.nope.nope")

    def test_collect_dispatches_reference_through_validator(self) -> None:
        errors = review_content.validate_ai_question(
            review_content.normalize_ai_question({"questionType": "predict", "prompt": "x"}),
            require_reference=True)
        self.assertTrue(errors, "没有参考解时必须被闸门拦住")


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    _TEMP.cleanup()
