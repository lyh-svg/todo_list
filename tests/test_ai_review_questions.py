"""AI 出题 / 批改层：mock 通道、结构校验、失败可读化（全部离线，不发真实请求）。"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import ai_service  # noqa: E402
import review_content  # noqa: E402

CONTEXT = {
    "code": "py.mutability.default-arg", "title": "可变默认参数与求值时机",
    "module": "函数", "level": "基础", "minutes": 20,
    "pitfalls": ["默认值是可变对象"],
    "existingPrompts": {"concept": "默认参数什么时候求值？", "predict": "写出输出",
                        "debug": "找 bug", "code_task": "写实现"},
    "weak": True, "due": "2026-09-19",
    "history": [{"questionType": "concept", "grade": 2, "answer": "答错了", "reviewedOn": "2026-09-18"}],
}


def good_question() -> dict:
    return {"questionType": "predict", "prompt": "写出两次调用的输出",
            "code": "def f(items=[]):\n    items.append(1)\n    return items",
            "focus": "默认参数的求值时机"}


def good_verdict() -> dict:
    return {"verdict": {"correct": False, "summary": "机制说反了",
                        "missing": ["定义时求值一次"], "wrongAt": "把共享说成每次新建",
                        "hint": "想想默认值在何时创建"},
            "focus": "默认参数的求值时机",
            "reference": {"answer": ["定义时求值一次"], "expected": ["[1]", "[1, 2]"],
                          "explain": "两次调用共享同一个列表",
                          "reference": "def f(items=None):\n    items = [] if items is None else items"}}

class AiGenerateQuestionTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TODO_AI_MOCK"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("TODO_AI_MOCK", None)

    def test_mock_mode_returns_renderable_question(self) -> None:
        question = ai_service.generate_ai_question(context=CONTEXT)
        self.assertEqual(review_content.validate_ai_question(question), [])
        self.assertIn(question["questionType"], review_content.QUESTION_TYPES)
        self.assertTrue(question["prompt"])
        self.assertTrue(question["code"], "mock 也要给可运行的代码片段")
        self.assertIn("默认参数", question["focus"])

    def test_mock_mode_honours_explicit_type(self) -> None:
        question = ai_service.generate_ai_question(context=CONTEXT, question_type="debug")
        self.assertEqual(question["questionType"], "debug")

    def test_structure_failure_raises_readable_error(self) -> None:
        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": ""}, clear=False), \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=False), \
                mock.patch.object(ai_service, "_post_json",
                                  return_value={"questionType": "essay", "prompt": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                ai_service.generate_ai_question(context=CONTEXT)
        self.assertIn("不合规", str(ctx.exception))

    def test_real_branch_passes_context_without_answers(self) -> None:
        captured = {}

        def fake_post(settings, body, **kwargs):
            captured["body"] = body
            return good_question()

        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": "", "DEEPSEEK_API_KEY": "test-key"},
                             clear=False), \
                mock.patch.object(ai_service, "_post_json", side_effect=fake_post):
            question = ai_service.generate_ai_question(context=CONTEXT)
        self.assertEqual(question["questionType"], "predict")
        user_payload = json.loads(captured["body"]["messages"][1]["content"])
        self.assertEqual(user_payload["知识点"], CONTEXT["title"])
        self.assertIn("concept", user_payload["现有题面（风格参考，请勿重复）"])
        self.assertEqual(user_payload["最近作答"][0]["grade"], 2)
        self.assertTrue(user_payload["薄弱"])
        self.assertNotIn("answer", user_payload["现有题面（风格参考，请勿重复）"],
                         "风格参考只给题面，不能带上参考答案")


class AiReviewAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TODO_AI_MOCK"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("TODO_AI_MOCK", None)

    def test_mock_verdict_contains_demo_solution(self) -> None:
        result = ai_service.review_ai_answer(context=CONTEXT, question=good_question(), answer="")
        self.assertFalse(result["verdict"]["correct"], "空作答不能算对")
        self.assertTrue(result["verdict"]["missing"])
        errors = review_content.validate_ai_question(
            {"questionType": "predict", "prompt": "x", "reference": result["reference"]},
            require_reference=True)
        self.assertEqual(errors, [], "示范解法必须能直接用于收藏")

    def test_mock_verdict_marks_non_empty_answer_correct(self) -> None:
        result = ai_service.review_ai_answer(context=CONTEXT, question=good_question(),
                                             answer="默认参数在定义时求值一次")
        self.assertTrue(result["verdict"]["correct"])

    def test_real_branch_normalizes_and_requires_demo(self) -> None:
        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": "", "DEEPSEEK_API_KEY": "test-key"},
                             clear=False), \
                mock.patch.object(ai_service, "_post_json", return_value=good_verdict()):
            result = ai_service.review_ai_answer(context=CONTEXT, question=good_question(),
                                                 answer="我的答案")
        self.assertEqual(result["verdict"]["missing"], ["定义时求值一次"])
        self.assertEqual(result["reference"]["expected"], ["[1]", "[1, 2]"])
        self.assertEqual(result["focus"], "默认参数的求值时机")

    def test_real_branch_without_demo_raises_readable_error(self) -> None:
        broken = {"verdict": {"correct": True}, "focus": "x", "reference": {}}
        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": "", "DEEPSEEK_API_KEY": "test-key"},
                             clear=False), \
                mock.patch.object(ai_service, "_post_json", return_value=broken):
            with self.assertRaises(RuntimeError) as ctx:
                ai_service.review_ai_answer(context=CONTEXT, question=good_question(), answer="x")
        self.assertIn("不合规", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
