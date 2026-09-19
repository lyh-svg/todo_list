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
        # weekday 用 JS getDay()：0=周日，1=周一，…，6=周六（与前端一致）。
        # 从周二 2026-09-15 起：下一个周日是 09-20，下一个周一是 09-21。
        self.assertEqual(storage.next_repeat_due({"freq": "weekly", "weekday": 0}, "2026-09-15"), "2026-09-20")
        self.assertEqual(storage.next_repeat_due({"freq": "weekly", "weekday": 1}, "2026-09-15"), "2026-09-21")
        # 周二自己：下一次是下周二
        self.assertEqual(storage.next_repeat_due({"freq": "weekly", "weekday": 2}, "2026-09-15"), "2026-09-22")
        self.assertEqual(storage.next_repeat_due({"freq": "weekly", "weekday": 6}, "2026-09-15"), "2026-09-19")

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

    def test_spawn_skips_node_missing_from_tree(self) -> None:
        """B5：mark 里的节点已经不在树里（过期/并发删除）时必须跳过，不能挂到项目根。

        locate_parent 以前只返回 parent_id，None 同时意味着"顶层节点"和"没找到"；
        没找到时 find_parent(tree, None) 命中项目根列表 → 幽灵任务的副本凭空出现在根层。
        """
        storage.replace_projects([make_project([item("i1", "还在的任务", dueDate=TODAY)])])
        project = storage.read_project("p1")[0]
        ghost = item("gone", "幽灵周期任务", dueDate=TODAY, repeat={"freq": "daily"})
        spawned = storage._spawn_next_occurrences(project, [ghost])
        self.assertEqual(spawned, 0, "目标不在树里就不能生成下一次")
        self.assertEqual(len(project["tree"]), 1, "副本不能挂到项目根")
        self.assertEqual([node["id"] for node in project["tree"]], ["p1-w"])

    def test_spawn_still_puts_top_level_next_occurrence_at_root(self) -> None:
        """守卫：顶层周期任务的"下一次"本来就该挂在项目根，别把合法路径一起掐掉。"""
        storage.replace_projects([make_project([])])
        project = storage.read_project("p1")[0]
        top = item("top", "顶层周期任务", dueDate=TODAY, repeat={"freq": "daily"})
        project["tree"].append(top)
        spawned = storage._spawn_next_occurrences(project, [top])
        self.assertEqual(spawned, 1)
        self.assertEqual([node["text"] for node in project["tree"]],
                         ["第1周", "顶层周期任务", "顶层周期任务"])
        self.assertEqual(project["tree"][-1]["completed"], False)
        self.assertNotEqual(project["tree"][-1]["id"], "top")

    def test_single_completion_via_patch_spawns_on_server(self) -> None:
        """Q13：单条完成（节点 patch）由服务端生成下一次，并回传副本给前端拼接。"""
        storage.replace_projects([make_project([
            item("i1", "每天背单词", dueDate=TODAY, repeat={"freq": "daily"}),
        ])])
        result = storage.patch_project_nodes("p1", 1, [
            {"op": "update", "nodeId": "i1",
             "fields": {"completed": True, "completedAt": f"{TODAY}T09:00:00"}},
        ])
        self.assertEqual(len(result["spawned"]), 1, "patch 完成周期任务必须生成下一次")
        entry = result["spawned"][0]
        self.assertEqual(entry["parentId"], "p1-d", "副本要挂在同一个父节点下")
        self.assertEqual(entry["node"]["dueDate"], (date.today() + timedelta(days=1)).isoformat())
        self.assertFalse(entry["node"]["completed"])
        self.assertEqual(entry["node"]["repeat"], {"freq": "daily", "interval": 1})
        nodes = storage.read_project("p1")[0]["tree"][0]["children"][0]["children"]
        self.assertEqual(len(nodes), 2, "库里也要真的多出这一条")
        self.assertEqual([node["text"] for node in nodes], ["每天背单词", "每天背单词"])

    def test_patch_that_does_not_complete_does_not_spawn(self) -> None:
        """守卫：改标签/取消完成都不该生成下一次。"""
        storage.replace_projects([make_project([
            item("i1", "每天背单词", dueDate=TODAY, repeat={"freq": "daily"}),
        ])])
        tagged = storage.patch_project_nodes("p1", 1, [
            {"op": "update", "nodeId": "i1", "fields": {"tags": ["英语"]}},
        ])
        self.assertEqual(tagged["spawned"], [])
        completed = storage.patch_project_nodes("p1", 2, [
            {"op": "update", "nodeId": "i1",
             "fields": {"completed": True, "completedAt": f"{TODAY}T09:00:00"}},
        ])
        self.assertEqual(len(completed["spawned"]), 1)
        undone = storage.patch_project_nodes("p1", 3, [
            {"op": "update", "nodeId": "i1", "fields": {"completed": False, "completedAt": None}},
        ])
        self.assertEqual(undone["spawned"], [], "取消完成不能生成")
        self.assertEqual(len(storage.read_project("p1")[0]["tree"][0]["children"][0]["children"]), 2)

    def test_full_save_spawns_on_completion_flip(self) -> None:
        """Q13：整树保存（非 patch 路径）也由服务端按"翻转"生成，且 revision 只前进一次。"""
        storage.replace_projects([make_project([
            item("i1", "每天背单词", dueDate=TODAY, repeat={"freq": "daily"}),
        ])])
        project, revision = storage.read_project("p1")
        node = project["tree"][0]["children"][0]["children"][0]
        node["completed"] = True
        node["completedAt"] = f"{TODAY}T09:00:00"
        saved_revision, summary, spawned = storage.write_project_with_occurrences(project, revision)
        self.assertEqual(saved_revision, revision + 1)
        self.assertEqual(len(spawned), 1)
        self.assertEqual(spawned[0]["parentId"], "p1-d")
        project_after = storage.read_project("p1")[0]
        self.assertEqual(len(project_after["tree"][0]["children"][0]["children"]), 2)
        self.assertEqual(summary["_revision"], revision + 1)

    def test_full_save_is_idempotent_and_ignores_new_completed_nodes(self) -> None:
        """再存一次（已完成没再翻转）不生成；新建一个"生来就完成"的节点也不生成。"""
        storage.replace_projects([make_project([
            item("i1", "每天背单词", dueDate=TODAY, repeat={"freq": "daily"}),
        ])])
        project, revision = storage.read_project("p1")
        node = project["tree"][0]["children"][0]["children"][0]
        node["completed"] = True
        _rev, _summary, first = storage.write_project_with_occurrences(project, revision)
        self.assertEqual(len(first), 1)

        same, revision_after = storage.read_project("p1")
        _rev2, _summary2, second = storage.write_project_with_occurrences(same, revision_after)
        self.assertEqual(second, [], "没有新的完成翻转就不能再生成")

        fresh, revision_now = storage.read_project("p1")
        fresh["tree"][0]["children"][0]["children"].append(
            item("i-new", "生来就完成的周期任务", dueDate=TODAY, repeat={"freq": "daily"},
                 completed=True, completedAt=f"{TODAY}T09:00:00"))
        _rev3, _summary3, third = storage.write_project_with_occurrences(fresh, revision_now)
        self.assertEqual(third, [], "库里没有过的新节点不算'完成了一次'")

    def test_batch_complete_ignores_stale_node_ids(self) -> None:
        """走公开 API：批量请求里混入"早就删掉"的节点 id，也不能在项目根留下垃圾。"""
        storage.replace_projects([make_project([
            item("i1", "每天背单词", dueDate=TODAY, repeat={"freq": "daily"}),
        ])])
        result = storage.batch_update_nodes([
            {"projectId": "p1", "nodeId": "i1"},
            {"projectId": "p1", "nodeId": "早就删了"},
        ], "complete")
        self.assertEqual(result["spawned"], 1, "只有真实存在的那一条该生成下一次")
        project = storage.read_project("p1")[0]
        self.assertEqual(len(project["tree"]), 1, "项目根层不能多出东西")
        self.assertEqual(len(project["tree"][0]["children"][0]["children"]), 2)

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

    def test_spawn_drops_children_to_avoid_duplicate_ids(self) -> None:
        """周期任务带子节点时，克隆出来的下一次不能连子节点一起复制（否则节点 ID 重复、整批 500）。"""
        parent = item("i1", "每周例会", dueDate=TODAY, repeat={"freq": "daily"})
        parent["children"] = [item("i1-c1", "会前准备")]
        storage.replace_projects([make_project([parent])])
        result = storage.batch_update_nodes([{"projectId": "p1", "nodeId": "i1"}], "complete")
        self.assertEqual(result["spawned"], 1)
        nodes = storage.read_project("p1")[0]["tree"][0]["children"][0]["children"]
        spawned = next(node for node in nodes if not node["completed"])
        self.assertEqual(spawned["children"], [], "克隆出来的下一次不应带子节点")
        # 读回项目本身也要能通过（说明没有重复 ID）
        self.assertEqual(len(nodes), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
