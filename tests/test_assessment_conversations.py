"""验收对话（逐题 questionConversations）不能被"只改了 passed 的局部写入"删掉。

这是本轮审计发现的静默数据丢失：_write_assessment 以前无条件做差集删除，
payload 里没有 questionConversations 键时 valid_keys 为空，会把该节点已有的逐题对话全部删光。
"""

from __future__ import annotations

import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-assessment-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))
os.environ.setdefault("TODO_SUMMARY_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "summary.sqlite3"))

import storage  # noqa: E402

TODAY = "2026-09-15"


def make_project(assessment: dict) -> dict:
    return {
        "id": "p1",
        "name": "验收项目",
        "description": "",
        "createdAt": TODAY,
        "assessmentEnabled": True,
        "reviewEnabled": False,
        "tree": [{
            "id": "p1-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": "p1-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": [{
                    "id": "p1-i", "type": "item", "text": "解释机制", "completed": True,
                    "completedAt": f"{TODAY}T10:00:00", "optional": False,
                    "assessmentRequired": True, "assessmentHistory": 0,
                    "assessment": copy.deepcopy(assessment), "createdAt": TODAY, "children": [],
                }],
            }],
        }],
    }


def read_assessment() -> dict:
    project = storage.read_project("p1")[0]
    return project["tree"][0]["children"][0]["children"][0]["assessment"]


class AssessmentConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        storage.ensure_schema()

    def test_conversations_survive_assessment_without_that_key(self) -> None:
        conversations = [
            [{"role": "user", "content": "第一题回答"}, {"role": "assistant", "content": "第一题反馈"}],
            [{"role": "user", "content": "第二题回答"}],
        ]
        storage.write_project(make_project({"passed": True, "questionConversations": conversations}), None)
        stored = read_assessment()
        self.assertEqual(len(stored["questionConversations"]), 2)
        self.assertEqual(len(stored["questionConversations"][0]), 2)

        # 局部写入：客户端只发 passed（旧代码会把上面的对话全删掉）
        revision = storage.read_project("p1")[1]
        storage.write_project(make_project({"passed": True}), revision)
        stored = read_assessment()
        self.assertTrue(stored["passed"])
        self.assertIn("questionConversations", stored, "缺少该键的局部写入不能删除已有逐题对话")
        self.assertEqual(len(stored["questionConversations"]), 2)
        self.assertEqual(stored["questionConversations"][0][0]["content"], "第一题回答")
        self.assertEqual(stored["questionConversations"][1][0]["content"], "第二题回答")

    def test_explicit_empty_conversations_still_clear_them(self) -> None:
        conversations = [[{"role": "user", "content": "会被清掉的回答"}]]
        storage.write_project(make_project({"passed": True, "questionConversations": conversations}), None)
        self.assertEqual(len(read_assessment()["questionConversations"]), 1)

        # 显式传空数组 = 用户确实清空了对话，这时必须真的删掉
        revision = storage.read_project("p1")[1]
        storage.write_project(make_project({"passed": True, "questionConversations": []}), revision)
        stored = read_assessment()
        self.assertEqual(stored.get("questionConversations"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
