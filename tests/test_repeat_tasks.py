"""批次 4：周期任务规则与生成（10）、加上 repeat 字段的存取校验。

（自然语言解析与提醒是纯前端逻辑，由前端断言脚本覆盖。）

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-repeat-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "summary.sqlite3")

import storage  # noqa: E402

DB = Path(storage.DATABASE_FILE)
TODAY = date.today().isoformat()


def item(node_id: str, text: str, **fields) -> dict:
    base = {
        "id": node_id, "type": "item", "text": text, "completed": False, "completedAt": None,
        "optional": False, "assessmentRequired": False, "assessmentHistory": 0,
        "assessment": None, "createdAt": TODAY, "children": [],
    }
    base.update(fields)
    return base


def make_project(items: list[dict]) -> dict:
    return {
        "id": "p1", "name": "项目一", "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False,
        "tree": [{
            "id": "p1-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": "p1-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": items,
            }],
        }],
    }


class RepeatRuleMathTests(unittest.TestCase):
    def test_daily_and_interval(self) -> None:
        self.assertEqual(storage.next_repeat_due({"freq": "daily"}, "2026-09-15"), "2026-09-16")
        self.assertEqual(storage.next_repeat_due({"freq": "daily", "interval": 3}, "2026-09-15"), "2026-09-18")

    def test_weekday_skips_weekend(self) -> None:
        # 2026-09-18 是周五 → 下一个工作日是周一 2026-09-21
        self.assertEqual(storage.next_repeat_due({"freq": "weekday"}, "2026-09-18"), "2026-09-21")
        self.assertEqual(storage.next_repeat_due({"freq": "weekday"}, "2026-09-17"), "2026-09-18")

    def test_weekly_targets_weekday(self) -> None:
        # 从周二 2026-09-15 起，每周一（weekday=0）
        self.assertEqual(storage.next_repeat_due({"freq": "weekly", "weekday": 0}, "2026-09-15"), "2026-09-21")

    def test_monthly_handles_short_months(self) -> None:
        # 9 月没有 31 号 → 顺到 10-31
        self.assertEqual(storage.next_repeat_due({"freq": "monthly", "day": 31}, "2026-09-15"), "2026-10-31")
        self.assertEqual(storage.next_repeat_due({"freq": "monthly", "day": 15}, "2026-09-15"), "2026-10-15")

    def test_until_stops_recurrence(self) -> None:
        self.assertEqual(storage.next_repeat_due({"freq": "daily", "until": "2026-09-15"}, "2026-09-15"), "")
        self.assertEqual(storage.next_repeat_due({"freq": "daily", "until": "2026-09-20"}, "2026-09-15"), "2026-09-16")

    def test_invalid_rules(self) -> None:
        for rule in ({}, {"freq": "hourly"}, {"freq": "weekly"}, {"freq": "weekly", "weekday": 9},
                     {"freq": "monthly", "day": 0}, {"freq": "monthly", "day": 40}, "每天"):
            self.assertEqual(storage.next_repeat_due(rule, "2026-09-15"), "", f"{rule} 应视为非法")


class RepeatStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def test_repeat_round_trips(self) -> None:
        storage.replace_projects([make_project([
            item("i1", "每天背单词", dueDate=TODAY, repeat={"freq": "daily"}),
            item("i2", "每周一复盘", repeat={"freq": "weekly", "weekday": 0, "until": "2026-12-31"}),
        ])])
        project = storage.read_project("p1")[0]
        nodes = project["tree"][0]["children"][0]["children"]
        self.assertEqual(nodes[0]["repeat"], {"freq": "daily", "interval": 1})
        self.assertEqual(nodes[1]["repeat"], {"freq": "weekly", "weekday": 0, "until": "2026-12-31"})

    def test_invalid_repeat_is_dropped(self) -> None:
        storage.replace_projects([make_project([item("i1", "坏规则", repeat={"freq": "hourly"})])])
        node = storage.read_project("p1")[0]["tree"][0]["children"][0]["children"][0]
        self.assertNotIn("repeat", node)

    def test_batch_complete_spawns_next_occurrence(self) -> None:
        storage.replace_projects([make_project([
            item("i1", "每天背单词", dueDate=TODAY, repeat={"freq": "daily"}),
        ])])
        result = storage.batch_update_nodes([{"projectId": "p1", "nodeId": "i1"}], "complete")
        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["spawned"], 1)
        nodes = storage.read_project("p1")[0]["tree"][0]["children"][0]["children"]
        self.assertEqual(len(nodes), 2, "完成周期任务后应该多出下一次出现")
        spawned = next(node for node in nodes if not node["completed"])
        done = next(node for node in nodes if node["completed"])
        self.assertEqual(done["text"], "每天背单词")
        self.assertEqual(spawned["text"], "每天背单词")
        self.assertEqual(spawned["dueDate"], (date.today() + timedelta(days=1)).isoformat())
        self.assertFalse(spawned["completed"])
        self.assertEqual(spawned["repeat"], {"freq": "daily", "interval": 1})
        self.assertNotEqual(spawned["id"], done["id"])

    def test_non_recurring_complete_does_not_spawn(self) -> None:
        storage.replace_projects([make_project([item("i1", "一次性任务")])])
        result = storage.batch_update_nodes([{"projectId": "p1", "nodeId": "i1"}], "complete")
        self.assertEqual(result["spawned"], 0)
        self.assertEqual(len(storage.read_project("p1")[0]["tree"][0]["children"][0]["children"]), 1)

    def test_uncomplete_does_not_spawn(self) -> None:
        storage.replace_projects([make_project([item("i1", "每天", repeat={"freq": "daily"}, completed=True,
                                                     completedAt=f"{TODAY}T08:00:00")])])
        result = storage.batch_update_nodes([{"projectId": "p1", "nodeId": "i1"}], "uncomplete")
        self.assertEqual(result["spawned"], 0)
        self.assertEqual(len(storage.read_project("p1")[0]["tree"][0]["children"][0]["children"]), 1)

    def test_repeat_respects_until_when_spawning(self) -> None:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        storage.replace_projects([make_project([
            item("i1", "到期就停", dueDate=yesterday, repeat={"freq": "daily", "until": yesterday}),
        ])])
        result = storage.batch_update_nodes([{"projectId": "p1", "nodeId": "i1"}], "complete")
        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["spawned"], 0, "超过 until 就不再生成")


if __name__ == "__main__":
    unittest.main(verbosity=2)
