"""批次 3：保存筛选视图（11）、批量修改（12）、基础归档（15）的回归测试。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-batch3-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "summary.sqlite3")

import storage  # noqa: E402

DB = Path(storage.DATABASE_FILE)
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def item(node_id: str, text: str, **fields) -> dict:
    base = {
        "id": node_id, "type": "item", "text": text, "completed": False, "completedAt": None,
        "optional": False, "assessmentRequired": False, "assessmentHistory": 0,
        "assessment": None, "createdAt": TODAY, "children": [],
    }
    base.update(fields)
    return base


def make_project(project_id: str, items: list[dict], *, archived: bool = False) -> dict:
    return {
        "id": project_id, "name": f"项目{project_id}", "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": archived,
        "tree": [{
            "id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": items,
            }],
        }],
    }


def read_items(project_id: str = "p1") -> list[dict]:
    project = storage.read_project(project_id)[0]
    return project["tree"][0]["children"][0]["children"]


class SavedViewTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def test_create_list_and_delete(self) -> None:
        created = storage.save_saved_view("高优先级未完成", {"projectFilters": {"status": "active"},
                                                        "nodeFilters": {"priority": "high"}})
        self.assertEqual(created["name"], "高优先级未完成")
        self.assertEqual(created["payload"]["nodeFilters"]["priority"], "high")
        views = storage.list_saved_views()
        self.assertEqual([view["name"] for view in views], ["高优先级未完成"])
        self.assertTrue(storage.delete_saved_view(created["id"]))
        self.assertEqual(storage.list_saved_views(), [])
        self.assertFalse(storage.delete_saved_view(created["id"]))

    def test_same_name_overwrites(self) -> None:
        first = storage.save_saved_view("本周 Python", {"nodeFilters": {"tag": "Python"}})
        second = storage.save_saved_view("本周 Python", {"nodeFilters": {"tag": "Python", "due": "week"}})
        self.assertEqual(first["id"], second["id"], "同名视图应该覆盖而不是新增")
        self.assertEqual(len(storage.list_saved_views()), 1)
        self.assertEqual(second["payload"]["nodeFilters"]["due"], "week")

    def test_name_and_payload_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            storage.save_saved_view("   ", {})
        with self.assertRaises(ValueError):
            storage.save_saved_view("视图", ["不是对象"])
        with self.assertRaises(ValueError):
            storage.save_saved_view("视图", {"big": "x" * (65 * 1024)})

    def test_views_survive_reload(self) -> None:
        storage.save_saved_view("阻塞任务", {"nodeFilters": {"status": "active"}})
        # 新连接读一次，确认落库而不是只存在内存
        with storage.open_state_database() as connection:
            count = connection.execute("SELECT COUNT(*) FROM saved_views").fetchone()[0]
        self.assertEqual(count, 1)


class BatchUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        storage.replace_projects([
            make_project("p1", [
                item("p1-a", "任务A"),
                item("p1-b", "任务B", priority="low"),
                item("p1-c", "需要验收", assessmentRequired=True),
            ]),
            make_project("p2", [item("p2-a", "另一个项目的任务")]),
        ])

    def targets(self, *pairs):
        return [{"projectId": project_id, "nodeId": node_id} for project_id, node_id in pairs]

    def test_set_priority_across_projects(self) -> None:
        result = storage.batch_update_nodes(self.targets(("p1", "p1-a"), ("p2", "p2-a")), "set-priority", "high")
        self.assertEqual(result["changed"], 2)
        self.assertEqual(read_items("p1")[0]["priority"], "high")
        self.assertEqual(read_items("p2")[0]["priority"], "high")
        self.assertEqual(sorted(entry["id"] for entry in result["projects"]), ["p1", "p2"])

    def test_add_and_remove_tags(self) -> None:
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "add-tags", ["Python", "复习"])
        self.assertEqual(read_items("p1")[0]["tags"], ["Python", "复习"])
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "add-tags", ["Python"])
        self.assertEqual(read_items("p1")[0]["tags"], ["Python", "复习"], "重复标签不应叠加")
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "remove-tags", ["Python"])
        self.assertEqual(read_items("p1")[0]["tags"], ["复习"])

    def test_set_and_shift_due_date(self) -> None:
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "set-due", TOMORROW)
        self.assertEqual(read_items("p1")[0]["dueDate"], TOMORROW)
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "shift-due", 3)
        expected = (date.today() + timedelta(days=4)).isoformat()
        self.assertEqual(read_items("p1")[0]["dueDate"], expected, "在原有到期日上顺延")
        storage.batch_update_nodes(self.targets(("p1", "p1-b")), "shift-due", 1)
        self.assertEqual(read_items("p1")[1]["dueDate"], TOMORROW, "没有到期日的任务从今天起算")
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "set-due", "")
        self.assertEqual(read_items("p1")[0].get("dueDate", ""), "")

    def test_set_estimate_and_validation(self) -> None:
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "set-estimate", 45)
        self.assertEqual(read_items("p1")[0]["estimateMinutes"], 45)
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "set-estimate", -5)
        self.assertEqual(read_items("p1")[0].get("estimateMinutes", 0), 0)

    def test_complete_and_uncomplete(self) -> None:
        result = storage.batch_update_nodes(self.targets(("p1", "p1-a")), "complete")
        self.assertEqual(result["changed"], 1)
        node = read_items("p1")[0]
        self.assertTrue(node["completed"])
        self.assertTrue(node["completedAt"])
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "uncomplete")
        node = read_items("p1")[0]
        self.assertFalse(node["completed"])
        self.assertIsNone(node.get("completedAt"), "读回时不带 completedAt（与既有行为一致）")

    def test_complete_rejects_assessment_task_and_reports_reason(self) -> None:
        result = storage.batch_update_nodes(self.targets(("p1", "p1-c"), ("p1", "p1-a")), "complete")
        self.assertEqual(result["changed"], 1, "只完成不需要验收的那个")
        self.assertEqual(len(result["failed"]), 1)
        self.assertIn("验收", result["failed"][0]["error"])
        self.assertFalse(read_items("p1")[2]["completed"])

    def test_invalid_action_and_empty_targets(self) -> None:
        with self.assertRaises(ValueError):
            storage.batch_update_nodes(self.targets(("p1", "p1-a")), "explode")
        with self.assertRaises(ValueError):
            storage.batch_update_nodes([], "set-priority", "high")
        result = storage.batch_update_nodes(self.targets(("不存在", "x")), "set-priority", "high")
        self.assertEqual(result["changed"], 0)
        self.assertEqual(len(result["failed"]), 1)

    def test_invalid_set_due_is_rejected_instead_of_clearing(self) -> None:
        """格式不对的日期不能当成"清除"：旧行为会把选中任务的截止日期静默抹掉。"""
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "set-due", TOMORROW)
        self.assertEqual(read_items("p1")[0]["dueDate"], TOMORROW)
        result = storage.batch_update_nodes(self.targets(("p1", "p1-a")), "set-due", "2026-9-5")
        self.assertEqual(result["changed"], 0)
        self.assertEqual(len(result["failed"]), 1)
        self.assertIn("格式", result["failed"][0]["error"])
        self.assertEqual(read_items("p1")[0]["dueDate"], TOMORROW, "非法输入不能改动截止日期")
        # 真正的空串仍然表示清除
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "set-due", "")
        self.assertEqual(read_items("p1")[0].get("dueDate", ""), "")

    def test_batch_complete_schedules_review_like_single_complete(self) -> None:
        """批量完成要和逐条完成一致：开启复习的项目要排进复习队列。"""
        storage.replace_projects([
            make_project("p1", [item("p1-a", "任务A"), item("p1-b", "任务B")]),
        ])
        with storage.open_state_database() as connection:
            connection.execute("UPDATE projects SET review_enabled=1 WHERE project_id='p1'")
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "complete")
        node = read_items("p1")[0]
        self.assertTrue(node["completed"])
        self.assertEqual(node.get("review", {}).get("due"), TOMORROW)
        # 取消完成要把复习计划一起撤掉
        storage.batch_update_nodes(self.targets(("p1", "p1-a")), "uncomplete")
        self.assertNotIn("review", read_items("p1")[0])

    def test_batch_touches_only_latest_revision_once_per_project(self) -> None:
        before = storage.read_project("p1")[1]
        storage.batch_update_nodes(self.targets(("p1", "p1-a"), ("p1", "p1-b")), "set-priority", "mid")
        after = storage.read_project("p1")[1]
        self.assertEqual(after, before + 1, "同一项目的多个任务只前进一个版本")


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def test_archive_flag_round_trip_and_revision(self) -> None:
        storage.replace_projects([make_project("p1", [item("p1-a", "任务A")])])
        project, revision = storage.read_project("p1")
        project["archived"] = True
        storage.write_project(project, revision)
        self.assertTrue(storage.read_project_summaries()[0]["archived"])
        self.assertTrue(storage.read_project("p1")[0]["archived"])

    def test_summary_reports_live_columns_even_if_json_is_stale(self) -> None:
        """summary_json 是旧版本程序写的（缺 archived 等字段）时，摘要必须以列为准。"""
        storage.replace_projects([make_project("p1", [item("p1-a", "任务A")])])
        with storage.open_state_database() as connection:
            connection.execute(
                "UPDATE projects SET summary_json=?, archived=1, review_enabled=1 WHERE project_id='p1'",
                (json.dumps({"id": "p1", "name": "旧摘要", "description": "",
                             "createdAt": TODAY, "assessmentEnabled": False,
                             "stats": {"total": 1, "remaining": 1,
                                       "optionalTotal": 0, "optionalCompleted": 0}},
                            ensure_ascii=False),),
            )
        summary = storage.read_project_summaries()[0]
        self.assertTrue(summary["archived"], "摘要必须反映 live 的 archived 列")
        self.assertTrue(summary["reviewEnabled"], "摘要必须反映 live 的 review_enabled 列")
        self.assertIn("lastOpenedAt", summary)

    def test_archived_project_is_excluded_from_workbench(self) -> None:
        storage.replace_projects([
            make_project("p1", [item("p1-a", "活跃任务", dueDate=TODAY)]),
            make_project("p2", [item("p2-a", "归档任务", dueDate=TODAY)], archived=True),
        ])
        board = storage.workbench(TODAY)
        texts = [entry["text"] for group in board["groups"].values() for entry in group]
        self.assertIn("活跃任务", texts)
        self.assertNotIn("归档任务", texts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
