"""批次 2：收集箱 / 今日工作台 / 最近入口 的回归测试。

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

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-workbench-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")

import storage  # noqa: E402

DB = Path(storage.DATABASE_FILE)
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
IN_3_DAYS = (date.today() + timedelta(days=3)).isoformat()
IN_10_DAYS = (date.today() + timedelta(days=10)).isoformat()


def make_project(project_id: str, name: str, items: list[dict], *, archived: bool = False) -> dict:
    return {
        "id": project_id, "name": name, "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": archived,
        "tree": [{
            "id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": items,
            }],
        }],
    }


def item(node_id: str, text: str, **fields) -> dict:
    base = {
        "id": node_id, "type": "item", "text": text, "completed": False, "completedAt": None,
        "optional": False, "assessmentRequired": False, "assessmentHistory": 0,
        "assessment": None, "createdAt": TODAY, "children": [],
    }
    base.update(fields)
    return base


class InboxTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def test_inbox_is_created_on_demand_and_is_idempotent(self) -> None:
        project, revision = storage.ensure_inbox_project()
        self.assertEqual(project["id"], "inbox")
        self.assertEqual(project["name"], storage.INBOX_PROJECT_NAME)
        self.assertEqual(project["tree"], [])
        self.assertEqual(revision, 1)
        again, second_revision = storage.ensure_inbox_project()
        self.assertEqual(second_revision, revision, "重复调用不应该再写一次")
        self.assertEqual(len(storage.read_project_summaries()), 1)

    def test_add_item_keeps_metadata_and_returns_stored_node(self) -> None:
        created = storage.add_inbox_item({
            "text": "给装饰器写测试", "priority": "high", "dueDate": IN_3_DAYS,
            "estimateMinutes": 30, "tags": ["Python"], "note": "备注内容",
            "links": [{"label": "文档", "url": "https://docs.python.org"}],
        })
        node = created["node"]
        self.assertEqual(node["text"], "给装饰器写测试")
        self.assertEqual(node["priority"], "high")
        self.assertEqual(node["dueDate"], IN_3_DAYS)
        self.assertEqual(node["estimateMinutes"], 30)
        self.assertEqual(node["tags"], ["Python"])
        self.assertEqual(node["note"], "备注内容")
        self.assertEqual(node["links"][0]["label"], "文档")
        project = storage.read_project("inbox")[0]
        self.assertEqual(len(project["tree"]), 1)

    def test_add_item_rejects_bad_link(self) -> None:
        with self.assertRaises(ValueError):
            storage.add_inbox_item({"text": "坏链接", "links": [{"url": "javascript:alert(1)"}]})

    def test_add_item_without_text_gets_placeholder(self) -> None:
        created = storage.add_inbox_item({"text": "   "})
        self.assertEqual(created["node"]["text"], "未命名任务")

    def test_move_item_between_projects(self) -> None:
        storage.replace_projects([make_project("p1", "目标项目", [])])
        created = storage.add_inbox_item({"text": "要归类", "priority": "mid"})
        inbox_revision_before = storage.read_project("inbox")[1]
        target_revision_before = storage.read_project("p1")[1]

        result = storage.move_node(created["node"]["id"], "inbox", "p1", parent_id="p1-d", position=0)

        self.assertEqual(result["to"], "p1")
        inbox, inbox_revision = storage.read_project("inbox")
        self.assertEqual(inbox["tree"], [], "收集箱里应该已经被移走")
        target = storage.read_project("p1")[0]
        placed = target["tree"][0]["children"][0]["children"]
        self.assertEqual([node["text"] for node in placed], ["要归类"])
        self.assertEqual(placed[0]["priority"], "mid")
        self.assertEqual(inbox_revision, inbox_revision_before + 1, "两个项目的 revision 都要前进")
        self.assertEqual(storage.read_project("p1")[1], target_revision_before + 1)

    def test_move_rejects_missing_node_or_project(self) -> None:
        storage.replace_projects([make_project("p1", "目标项目", [])])
        with self.assertRaises(ValueError):
            storage.move_node("不存在", "inbox", "p1")
        created = storage.add_inbox_item({"text": "x"})
        with self.assertRaises(ValueError):
            storage.move_node(created["node"]["id"], "inbox", "不存在项目")

    def test_add_item_with_parent_appends_to_the_end(self) -> None:
        """指定 parentId 时要追加到父节点末尾，而不是按顶层节点数插到中间。"""
        storage.replace_projects([make_project("p1", "项目一", [
            item("i1", "已有1"), item("i2", "已有2"), item("i3", "已有3"), item("i4", "已有4"),
        ])])
        created = storage.add_project_item("p1", {"text": "新加的"}, parent_id="p1-d")
        self.assertEqual(created["node"]["text"], "新加的")
        items = storage.read_project("p1")[0]["tree"][0]["children"][0]["children"]
        self.assertEqual([node["text"] for node in items],
                         ["已有1", "已有2", "已有3", "已有4", "新加的"])
        with self.assertRaises(ValueError):
            storage.add_project_item("p1", {"text": "孤儿"}, parent_id="不存在的父节点")

    def test_move_rejects_archived_target_project(self) -> None:
        """前端的目标下拉已经过滤掉归档项目，接口也要拒绝，否则任务会被归类进看不见的项目。"""
        storage.replace_projects([make_project("p1", "归档项目", [], archived=True)])
        created = storage.add_inbox_item({"text": "要归类"})
        with self.assertRaises(ValueError) as ctx:
            storage.move_node(created["node"]["id"], "inbox", "p1", parent_id="p1-d", position=0)
        self.assertIn("归档", str(ctx.exception))
        # 任务必须还在收集箱里（事务回滚，没被搬走）
        inbox = storage.read_project("inbox")[0]
        self.assertEqual([node["text"] for node in inbox["tree"]], ["要归类"])

    def test_add_item_rejects_archived_project(self) -> None:
        """往已归档项目里加任务也一样：前端选择器过滤了，接口也要拦。"""
        storage.replace_projects([make_project("p1", "归档项目", [], archived=True)])
        with self.assertRaises(ValueError) as ctx:
            storage.add_project_item("p1", {"text": "加进归档项目"})
        self.assertIn("归档", str(ctx.exception))
        self.assertEqual(storage.read_project("p1")[0]["tree"][0]["children"][0]["children"], [])
        # 收集箱例外：它是快速添加的落点，永远可写
        created = storage.add_inbox_item({"text": "收集箱任务"})
        self.assertEqual(created["node"]["text"], "收集箱任务")


class WorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        storage.replace_projects([
            make_project("p1", "项目一", [
                item("i-over", "逾期的", dueDate=YESTERDAY, priority="low"),
                item("i-today", "今天的", dueDate=TODAY, priority="high"),
                item("i-next", "三天后的", dueDate=IN_3_DAYS, priority="mid"),
                item("i-far", "十天后的（不该进未来 7 天）", dueDate=IN_10_DAYS),
                item("i-review", "已完成待复习", completed=True,
                     completedAt=f"{TODAY}T09:00:00", review={"due": TODAY, "learning": False, "log": []}),
                item("i-done", "已完成且无需复习", completed=True, completedAt=f"{TODAY}T10:00:00"),
            ]),
            make_project("p-arch", "已归档项目", [item("i-arch", "归档里的任务", dueDate=TODAY)], archived=True),
        ])
        storage.add_inbox_item({"text": "收集箱里的", "priority": "high"})

    def test_workbench_groups(self) -> None:
        board = storage.workbench(TODAY)
        totals = board["totals"]
        self.assertEqual(totals["overdue"], 1)
        self.assertEqual(totals["today"], 1, "只统计未完成且今天到期的")
        self.assertEqual(totals["next7"], 1, "十天后的不算未来 7 天")
        self.assertEqual(totals["reviewToday"], 1)
        self.assertEqual(totals["inbox"], 1)
        self.assertEqual(board["today"], TODAY)
        self.assertTrue(board["serverToday"])

    def test_workbench_excludes_archived_projects(self) -> None:
        board = storage.workbench(TODAY)
        texts = [entry["text"] for group in board["groups"].values() for entry in group]
        self.assertNotIn("归档里的任务", texts)

    def test_archived_inbox_is_still_listed(self) -> None:
        """收集箱即使被归档也必须显示：快速添加永远写进它，看不见就等于任务丢了。"""
        with storage.open_state_database() as connection:
            connection.execute("UPDATE projects SET archived=1 WHERE project_id='inbox'")
        board = storage.workbench(TODAY)
        self.assertEqual([entry["text"] for entry in board["groups"]["inbox"]], ["收集箱里的"])

    def test_inbox_items_are_not_counted_twice(self) -> None:
        """收集箱里排了日期的任务只出现在日期分组，两个分组/计数不能重复。"""
        near = storage.add_inbox_item({"text": "收集箱里今天到期", "dueDate": TODAY})
        far = storage.add_inbox_item({"text": "收集箱里很久以后", "dueDate": IN_10_DAYS})
        board = storage.workbench(TODAY)
        inbox_ids = [entry["nodeId"] for entry in board["groups"]["inbox"]]
        today_ids = [entry["nodeId"] for entry in board["groups"]["today"]]
        next7_ids = [entry["nodeId"] for entry in board["groups"]["next7"]]
        self.assertIn(near["node"]["id"], today_ids, "排了今天到期的收集箱任务要进'今天到期'")
        self.assertNotIn(near["node"]["id"], inbox_ids, "不能同时出现在收集箱分组里")
        # 超出 7 天视野的收集箱任务没有别的去处，仍然显示在收集箱
        self.assertIn(far["node"]["id"], inbox_ids)
        self.assertNotIn(far["node"]["id"], next7_ids)
        all_ids = [entry["nodeId"] for group in board["groups"].values() for entry in group]
        self.assertEqual(len(all_ids), len(set(all_ids)), "同一条任务不能被两个分组同时统计")
        self.assertEqual(board["totals"]["inbox"], len(inbox_ids))

    def test_workbench_items_carry_context(self) -> None:
        board = storage.workbench(TODAY)
        today_item = board["groups"]["today"][0]
        self.assertEqual(today_item["projectName"], "项目一")
        self.assertEqual(today_item["nodeId"], "i-today")
        self.assertEqual(today_item["priority"], "high")
        self.assertIn("第1周", today_item["path"], "要能看出任务在哪一周/单元")
        self.assertIn("单元1", today_item["path"])

    def test_workbench_items_carry_meta_badges(self) -> None:
        """工作台的行要能渲染备注/链接/周期徽标，所以这三个字段必须返回。"""
        storage.write_project(make_project("p3", "项目三", [
            item("i-meta", "带元数据的任务", dueDate=TODAY, note="记得先看文档",
                 links=[{"label": "文档", "url": "https://example.com/doc"}],
                 repeat={"freq": "daily"}),
        ]), None)
        board = storage.workbench(TODAY)
        entry = next(entry for group in board["groups"].values() for entry in group
                     if entry["nodeId"] == "i-meta")
        self.assertEqual(entry["note"], "记得先看文档")
        self.assertEqual(entry["links"][0]["url"], "https://example.com/doc")
        self.assertEqual(entry["repeat"], {"freq": "daily", "interval": 1})

    def test_workbench_sorts_high_priority_first(self) -> None:
        board = storage.workbench(TODAY)
        self.assertEqual(board["groups"]["today"][0]["priority"], "high")
        overdue = board["groups"]["overdue"][0]
        self.assertEqual(overdue["daysOverdue"], 1)

    def test_workbench_honours_passed_date(self) -> None:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        board = storage.workbench(tomorrow)
        self.assertEqual(board["today"], tomorrow)
        self.assertEqual(board["totals"]["overdue"], 2, "昨天和今天到期的都算逾期")

    def test_workbench_ignores_bad_date(self) -> None:
        board = storage.workbench("2026-02-30")
        self.assertEqual(board["today"], TODAY, "非法日期回落到服务端当天")


class RecentTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        storage.replace_projects([
            make_project("p1", "项目一", [item("i1", "任务一", completed=True, completedAt=f"{TODAY}T08:00:00")]),
            make_project("p2", "项目二", []),
        ])

    def test_touch_records_open_without_bumping_revision(self) -> None:
        before = storage.read_project("p1")[1]
        storage.touch_project_opened("p1")
        after = storage.read_project("p1")[1]
        self.assertEqual(before, after, "记录最近打开不应产生新的版本号")
        recent = storage.recent_overview()
        self.assertEqual([entry["id"] for entry in recent["opened"]], ["p1"])
        self.assertTrue(recent["opened"][0]["at"])

    def test_recent_lists_modified_and_completed(self) -> None:
        storage.touch_project_opened("p2")
        recent = storage.recent_overview()
        # 时间戳是秒精度，同一秒内写入的两个项目按 id 兜底排序；这里只断言两个都在、且"最近打开"用的是 p2
        self.assertEqual(sorted(entry["id"] for entry in recent["modified"]), ["p1", "p2"])
        self.assertEqual(recent["opened"][0]["id"], "p2")
        self.assertEqual(len(recent["completed"]), 1)
        self.assertEqual(recent["completed"][0]["text"], "任务一")
        self.assertEqual(recent["completed"][0]["projectName"], "项目一")
        self.assertEqual(recent["completed"][0]["nodeId"], "i1")

    def test_saving_project_keeps_last_opened_at(self) -> None:
        """前端的保存 payload 里没有 lastOpenedAt，保存不能把"最近打开"清空。"""
        storage.touch_project_opened("p1")
        self.assertEqual([entry["id"] for entry in storage.recent_overview()["opened"]], ["p1"])

        project, revision = storage.read_project("p1")
        project["name"] = "项目一（改名）"
        storage.write_project(project, revision)

        opened = [entry["id"] for entry in storage.recent_overview()["opened"]]
        self.assertEqual(opened, ["p1"], "普通保存不能清掉最近打开时间")
        self.assertEqual(storage.read_project_summaries()[0]["name"], "项目一（改名）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
