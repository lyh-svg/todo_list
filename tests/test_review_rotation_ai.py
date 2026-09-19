"""第二批：轮换必须在「固定题 + 已收藏 AI 题」里挑最近最少用过的一道。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-rotation-ai-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

POINT = {
    "code": "py.rotation.point", "title": "轮换用知识点", "minutes": 15, "module": "函数",
    "level": "基础", "taskRefs": [{"taskId": "9001", "relation": "introduces"}],
    "concept": {"prompt": "固定概念题", "answer": ["固定答案"]},
    "predict": {"prompt": "固定预测题", "code": "print(1)", "expected": ["1"], "explain": "常量"},
    "debug": {"prompt": "固定找错题", "code": "x = 1", "rootCause": "无", "fix": "无"},
    "code_task": {"prompt": "固定写实现题", "acceptance": ["能跑"], "reference": "def f(): return 1"},
    "pitfalls": ["易错点"],
}
AI_REFERENCE = {"answer": ["AI 要点"], "expected": ["[1]"], "explain": "AI 解释",
                "reference": "def f(items=None):\n    return items"}


class RotationWithAiQuestionTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            for table in ("review_points", "review_point_tasks", "review_attempts",
                          "review_states", "review_ai_questions"):
                connection.execute(f"DELETE FROM {table}")
        review_storage.import_content([POINT], week=1)
        # 让这个点进入"今天到期"，build_queue 才会带上它
        review_storage.apply_grade(POINT["code"], "concept", 4, today="2026-09-15",
                                   answer="先答一次概念题")

    def _collect(self, prompt: str, kind: str = "concept") -> str:
        return review_storage.collect_ai_question(
            POINT["code"], kind, prompt, "", "考察点", dict(AI_REFERENCE))["id"]

    def _queue_item(self, **kwargs) -> dict:
        with storage.open_state_database() as connection:
            picked = review_storage.pick_questions(
                connection, [POINT["code"]], forced_type=kwargs.get("forced_type", ""))
        return picked[POINT["code"]]

    def test_pick_is_deterministic_and_uses_ai_question_when_never_used(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        picked = self._queue_item(forced_type="concept")
        # 固定概念题已经用过一次（setUp 那次），AI 题从未用过 → 必须先挑 AI 题
        self.assertEqual(picked["questionType"], "concept")
        self.assertEqual(picked["questionRef"], ai_id)

    def _clear_attempts(self) -> None:
        """清掉 setUp 里那条"真实时间"的作答：否则它的 created_at 比测试写死的时间戳新，
        LRU 断言就会变成在考时钟而不是在考轮换规则。"""
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_attempts WHERE code=?", (POINT["code"],))

    def _record_attempt(self, kind: str, question_ref: str, created_at: str) -> None:
        """直接写一条作答历史，时间戳可控。

        `apply_grade` 用的 `_now()` 只有秒级精度：同一秒内连做两次，谁"更久没用"就分不出来，
        测试会退化成在考并列规则而不是考 LRU。这里显式给 created_at。
        """
        with storage.open_state_database() as connection:
            connection.execute(
                "INSERT INTO review_attempts(id,code,task_id,project_id,question_type,question_ref,"
                "grade,answer,ai_verdict,reviewed_on,duration_ms,session_id,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"attempt-{kind}-{question_ref or 'fixed'}-{created_at}", POINT["code"], "", "",
                 kind, question_ref, 4, "作答", "", created_at[:10], 0, "", created_at))

    def test_fixed_question_wins_when_it_is_the_least_recently_used(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        self._clear_attempts()
        # 固定题 10:00:00 用过，AI 题 10:00:05 用过 → 固定题更久没用，必须挑固定题
        self._record_attempt("concept", "", "2026-09-19T10:00:00")
        self._record_attempt("concept", ai_id, "2026-09-19T10:00:05")
        self.assertEqual(self._queue_item(forced_type="concept")["questionRef"], "")

    def test_ai_question_wins_when_the_fixed_one_was_used_more_recently(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        self._clear_attempts()
        # 反过来：AI 题 10:00:00、固定题 10:00:05 → 必须挑 AI 题（真正的 LRU，不是并列规则）
        self._record_attempt("concept", ai_id, "2026-09-19T10:00:00")
        self._record_attempt("concept", "", "2026-09-19T10:00:05")
        self.assertEqual(self._queue_item(forced_type="concept")["questionRef"], ai_id)

    def test_deleted_question_is_not_a_candidate_but_history_survives(self) -> None:
        ai_id = self._collect("会被删掉的 AI 题")
        review_storage.apply_grade(POINT["code"], "concept", 3, today="2026-09-16",
                                   answer="做过再删", question_ref=ai_id)
        review_storage.delete_ai_question(ai_id)
        picked = self._queue_item(forced_type="concept")
        self.assertEqual(picked["questionRef"], "", "已删除的题不能再被抽中")
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT question_ref FROM review_attempts WHERE question_ref=?", (ai_id,)).fetchone()
        self.assertIsNotNone(row, "删除题库条目不能连带删掉历史作答")

    def test_queue_item_carries_question_ref_and_ai_prompt(self) -> None:
        ai_id = self._collect("AI 现场概念题：说说定义时求值")
        # build_queue 不强制题型时，题型轮换先挑"最近最少用过的题型"：setUp 只动过 concept，
        # predict/debug/code_task 都没用过，按声明顺序会先选 predict（见下一个用例）。
        # 这里先把另外三种题型也各用一次，让 concept 成为最久没用的题型，
        # 队列才会走到 concept 这一支，验证"题面来自被挑中的那道 AI 题"。
        for kind in ("predict", "debug", "code_task"):
            review_storage.apply_grade(POINT["code"], kind, 4, today="2026-09-16",
                                       answer=f"先用一次 {kind}")
        queue = review_storage.build_queue("2026-09-19", limit=10, code=POINT["code"])
        item = next(entry for entry in queue["items"] if entry["code"] == POINT["code"])
        self.assertEqual(item["questionRef"], ai_id)
        self.assertEqual(item["prompt"], "AI 现场概念题：说说定义时求值")
        self.assertEqual(item["questionType"], "concept")

    def test_type_selection_still_prefers_never_used_type(self) -> None:
        self._collect("AI 概念题")
        picked = self._queue_item()
        # 概念题已用过（固定+AI 都算这个题型用过），predict/debug/code_task 全没用过 →
        # 先选题型仍是"从未用过"的那几种之一（按声明顺序 = predict），与旧行为一致
        self.assertEqual(picked["questionType"], "predict")
        self.assertEqual(picked["questionRef"], "")

    def test_reveal_ai_question_returns_its_own_reference(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        revealed = review_storage.reveal(POINT["code"], "concept", ai_id)
        self.assertEqual(revealed["source"], "ai")
        self.assertEqual(revealed["questionRef"], ai_id)
        self.assertEqual(revealed["reference"], "def f(items=None):\n    return items")
        self.assertIn("AI 要点", revealed["answer"])
        self.assertEqual(revealed["pointCode"], POINT["code"])
        self.assertEqual(revealed["type"], "concept")

    def test_reveal_falls_back_when_ai_question_is_gone(self) -> None:
        ai_id = self._collect("会被删掉的 AI 题")
        review_storage.delete_ai_question(ai_id)
        revealed = review_storage.reveal(POINT["code"], "concept", ai_id)
        self.assertTrue(revealed.get("questionRefFallback"), "已删题必须回退固定题并标记")
        self.assertEqual(revealed.get("answer"), ["固定答案"], "回退后给的是固定题参考答案")

    def test_apply_grade_records_question_ref(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        review_storage.apply_grade(POINT["code"], "concept", 5, today="2026-09-20",
                                   answer="这次会了", question_ref=ai_id)
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT question_ref FROM review_attempts WHERE answer='这次会了'").fetchone()
        self.assertEqual(row["question_ref"], ai_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    _TEMP.cleanup()
