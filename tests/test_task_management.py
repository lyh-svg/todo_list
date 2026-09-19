"""第五批（中等难度任务管理）后端回归测试：
拖拽排序 / 跨周跨单元移动 / 复制节点与项目 / 删除影响面 / 回收站恢复位置与保留天数 /
活动历史 / 应用设置。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-manage-test-")
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


def make_project(project_id: str = "p1") -> dict:
    """两周，每周两个单元，单元里各两个任务。"""
    return {
        "id": project_id, "name": f"项目{project_id}", "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": False,
        "tree": [
            {"id": f"{project_id}-w1", "type": "week", "text": "第1周", "completed": False,
             "expanded": False, "createdAt": TODAY, "children": [
                 {"id": f"{project_id}-d1", "type": "day", "text": "单元1", "completed": False,
                  "expanded": False, "createdAt": TODAY, "children": [
                      item(f"{project_id}-i1", "任务1", priority="high", estimateMinutes=30),
                      item(f"{project_id}-i2", "任务2", completed=True, completedAt=f"{TODAY}T08:00:00",
                           review={"due": TODAY, "learning": False, "log": [{"at": TODAY, "result": "good"}]},
                           assessment={"passed": True, "score": 90}, assessmentHistory=2),
                  ]},
                 {"id": f"{project_id}-d2", "type": "day", "text": "单元2", "completed": False,
                  "expanded": False, "createdAt": TODAY, "children": [
                      item(f"{project_id}-i3", "任务3"),
                  ]},
             ]},
            {"id": f"{project_id}-w2", "type": "week", "text": "第2周", "completed": False,
             "expanded": False, "createdAt": TODAY, "children": [
                 {"id": f"{project_id}-d3", "type": "day", "text": "单元3", "completed": False,
                  "expanded": False, "createdAt": TODAY, "children": [item(f"{project_id}-i4", "任务4")]},
             ]},
        ],
    }


def tree(project_id: str = "p1") -> list[dict]:
    return storage.read_project(project_id)[0]["tree"]


def texts(nodes) -> list[str]:
    return [str(node.get("text")) for node in nodes or []]


def find(nodes, node_id):
    for node in nodes or []:
        if str(node.get("id")) == str(node_id):
            return node
        found = find(node.get("children") or [], node_id)
        if found is not None:
            return found
    return None


class ResetMixin:
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        storage.replace_projects([make_project()])


class AppSettingsTests(ResetMixin, unittest.TestCase):
    def test_defaults(self) -> None:
        settings = storage.read_app_settings()
        self.assertEqual(settings["trashRetentionDays"], storage.TRASH_RETENTION_DAYS)
        self.assertFalse(settings["autoArchiveEnabled"])
        self.assertIsInstance(settings["autoArchiveDays"], int)

    def test_update_and_persist(self) -> None:
        updated = storage.update_app_settings({"trashRetentionDays": 30, "autoArchiveEnabled": True,
                                               "autoArchiveDays": 14})
        self.assertEqual(updated["trashRetentionDays"], 30)
        self.assertTrue(updated["autoArchiveEnabled"])
        self.assertEqual(storage.read_app_settings()["autoArchiveDays"], 14)

    def test_invalid_values_are_rejected(self) -> None:
        for patch, message in (
            ({"trashRetentionDays": 0}, "保留天数"),
            ({"trashRetentionDays": 999}, "保留天数"),
            ({"trashRetentionDays": "很多"}, "整数"),
            ({"autoArchiveDays": 0}, "归档天数"),
            ({"unknownOption": 1}, "不支持"),
        ):
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError) as ctx:
                    storage.update_app_settings(patch)
                self.assertIn(message, str(ctx.exception))

    def test_broken_settings_fall_back_to_defaults(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute(
                "INSERT INTO app_state(key,payload,updated_at,revision) VALUES('settings',?,?,0)",
                ("{不是 JSON", storage._now()))
        self.assertEqual(storage.read_app_settings()["trashRetentionDays"], storage.TRASH_RETENTION_DAYS)

    def test_retention_setting_controls_purge(self) -> None:
        """把保留天数改成 1 天后，两天前的回收站条目要被清掉。"""
        storage.store_trash_item("node", "p1", "旧任务", item("old", "旧任务"), parent_id="p1-d1")
        with storage.open_state_database() as connection:
            connection.execute("UPDATE trash_items SET deleted_at=?", (
                (__import__("datetime").datetime.now() - timedelta(days=3)).isoformat(timespec="seconds"),))
        self.assertEqual(len(storage.list_trash_items()), 1, "默认 7 天保留")
        storage.update_app_settings({"trashRetentionDays": 1})
        self.assertEqual(storage.list_trash_items(), [], "保留 1 天时三天前的条目应被清掉")


class ReorderTests(ResetMixin, unittest.TestCase):
    def test_move_item_to_another_unit(self) -> None:
        result = storage.reorder_node("p1", "p1-i1", "p1-d2", 0)
        self.assertEqual(result["parentId"], "p1-d2")
        self.assertEqual(result["previous"], {"parentId": "p1-d1", "position": 0})
        node = tree()
        self.assertEqual(texts(find(node, "p1-d2")["children"]), ["任务1", "任务3"])
        self.assertEqual(texts(find(node, "p1-d1")["children"]), ["任务2"])

    def test_move_item_to_another_week(self) -> None:
        storage.reorder_node("p1", "p1-i3", "p1-d3", 0)
        node = tree()
        self.assertEqual(texts(find(node, "p1-d3")["children"]), ["任务3", "任务4"])
        self.assertEqual(find(node, "p1-d2")["children"], [])

    def test_move_week_to_root_position(self) -> None:
        result = storage.reorder_node("p1", "p1-w1", None, 1)
        node = tree()
        self.assertEqual(texts(node), ["第2周", "第1周"])
        self.assertEqual(result["previous"], {"parentId": None, "position": 0})

    def test_position_is_clamped_and_appended(self) -> None:
        storage.reorder_node("p1", "p1-i1", "p1-d2", 99)
        self.assertEqual(texts(find(tree(), "p1-d2")["children"]), ["任务3", "任务1"])
        storage.reorder_node("p1", "p1-i1", "p1-d2", -5)
        self.assertEqual(texts(find(tree(), "p1-d2")["children"]), ["任务1", "任务3"])

    def test_rejects_cycles_and_bad_targets(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            storage.reorder_node("p1", "p1-w1", "p1-d1", 0)
        self.assertIn("子节点", str(ctx.exception))
        with self.assertRaises(ValueError):
            storage.reorder_node("p1", "p1-w1", "p1-w1", 0)
        with self.assertRaises(ValueError) as ctx:
            storage.reorder_node("p1", "p1-i1", "p1-i2", 0)
        self.assertIn("周或学习单元", str(ctx.exception))
        with self.assertRaises(ValueError):
            storage.reorder_node("p1", "p1-i1", "不存在", 0)
        with self.assertRaises(ValueError):
            storage.reorder_node("p1", "不存在", None, 0)
        with self.assertRaises(ValueError):
            storage.reorder_node("不存在项目", "p1-i1", None, 0)

    def test_revision_advances_once_and_activity_logged(self) -> None:
        before = storage.read_project("p1")[1]
        storage.reorder_node("p1", "p1-i1", "p1-d2", 0)
        self.assertEqual(storage.read_project("p1")[1], before + 1)
        entry = storage.list_activity(1)[0]
        self.assertEqual(entry["kind"], "reorder")
        self.assertTrue(entry["undoable"])
        self.assertEqual(entry["detail"]["previousParentId"], "p1-d1")

    def test_reorder_is_reversible_with_recorded_previous_position(self) -> None:
        """撤销要用返回的 previous 数据能原样放回去。"""
        result = storage.reorder_node("p1", "p1-i1", "p1-d2", 1)
        storage.reorder_node("p1", "p1-i1", result["previous"]["parentId"], result["previous"]["position"])
        node = tree()
        self.assertEqual(texts(find(node, "p1-d1")["children"]), ["任务1", "任务2"])
        self.assertEqual(texts(find(node, "p1-d2")["children"]), ["任务3"])


class DuplicateTests(ResetMixin, unittest.TestCase):
    def descendants(self, node: dict) -> list[dict]:
        out = []
        for child in node.get("children") or []:
            out.append(child)
            out.extend(self.descendants(child))
        return out

    def test_duplicate_day_with_children_regenerates_ids(self) -> None:
        result = storage.duplicate_node("p1", "p1-d1", include_children=True)
        clone = result["node"]
        self.assertEqual(clone["text"], "单元1（副本）")
        self.assertNotEqual(clone["id"], "p1-d1")
        original_ids = {"p1-d1", "p1-i1", "p1-i2"}
        for node in self.descendants(clone):
            self.assertNotIn(node["id"], original_ids, "子树里的 ID 必须全部重新生成")
        node = tree()
        self.assertEqual(texts(find(node, "p1-w1")["children"]), ["单元1", "单元1（副本）", "单元2"])
        self.assertEqual(len(self.descendants(clone)), 2)

    def test_duplicate_without_children(self) -> None:
        clone = storage.duplicate_node("p1", "p1-d1", include_children=False)["node"]
        self.assertEqual(clone["children"], [])

    def test_duplicate_resets_progress_by_default(self) -> None:
        clone = storage.duplicate_node("p1", "p1-i2")["node"]
        self.assertFalse(clone["completed"])
        self.assertIsNone(clone["completedAt"])
        self.assertIsNone(clone["assessment"])
        self.assertEqual(clone["assessmentHistory"], 0)
        self.assertNotIn("review", clone)
        self.assertEqual(clone["priority"] if "priority" in clone else "", "")

    def test_duplicate_can_keep_state(self) -> None:
        clone = storage.duplicate_node("p1", "p1-i2", keep_completion=True,
                                       keep_assessment=True, keep_review=True)["node"]
        self.assertTrue(clone["completed"])
        self.assertTrue(clone["assessment"]["passed"])
        self.assertEqual(clone["assessmentHistory"], 2)
        self.assertEqual(clone["review"]["log"][0]["result"], "good")

    def test_duplicate_keeps_metadata(self) -> None:
        clone = storage.duplicate_node("p1", "p1-i1")["node"]
        self.assertEqual(clone["priority"], "high")
        self.assertEqual(clone["estimateMinutes"], 30)

    def test_duplicate_item_is_leaf(self) -> None:
        clone = storage.duplicate_node("p1", "p1-i1")["node"]
        self.assertEqual(clone["children"], [])

    def test_duplicate_missing_node(self) -> None:
        with self.assertRaises(ValueError):
            storage.duplicate_node("p1", "nope")

    def test_duplicate_project(self) -> None:
        result = storage.duplicate_project("p1", name="项目一（第二遍）", keep_completion=False,
                                           keep_assessment=False, keep_review=False)
        clone = result["project"]
        self.assertNotEqual(clone["id"], "p1")
        self.assertEqual(clone["name"], "项目一（第二遍）")
        stored = storage.read_project(clone["id"])[0]
        self.assertEqual(len(stored["tree"]), 2)
        self.assertEqual(stored["tree"][0]["text"], "第1周")
        # 节点 ID 全部重生成，且完成/验收/复习按选项清掉
        original = tree()
        original_ids = {node["id"] for node in storage._walk_nodes(original)}
        for node in storage._walk_nodes(stored["tree"]):
            self.assertNotIn(node["id"], original_ids)
        copied_item = find(stored["tree"], stored["tree"][0]["children"][0]["children"][1]["id"])
        self.assertFalse(copied_item["completed"])
        self.assertIsNone(copied_item.get("assessment"))
        self.assertNotIn("review", copied_item)
        # 原项目没被改动
        self.assertEqual(storage.read_project("p1")[0]["tree"], original)

    def test_duplicate_project_keeps_state_by_default(self) -> None:
        clone = storage.duplicate_project("p1")["project"]
        stored = storage.read_project(clone["id"])[0]
        copied = stored["tree"][0]["children"][0]["children"][1]
        self.assertTrue(copied["completed"])
        self.assertTrue(copied["assessment"]["passed"])
        self.assertIn("review", copied)

    def test_duplicate_project_gets_new_position(self) -> None:
        before = [entry["id"] for entry in storage.read_project_summaries()]
        clone = storage.duplicate_project("p1")["project"]
        after = [entry["id"] for entry in storage.read_project_summaries()]
        self.assertEqual(after, before + [clone["id"]])


class DeleteImpactTests(ResetMixin, unittest.TestCase):
    def test_counts_descendants_items_and_estimates(self) -> None:
        impact = storage.describe_node_delete("p1", "p1-d1")
        self.assertEqual(impact["title"], "单元1")
        self.assertEqual(impact["descendantCount"], 2)
        self.assertEqual(impact["itemCount"], 2)
        self.assertEqual(impact["completedCount"], 1)
        self.assertEqual(impact["estimateMinutes"], 30)

    def test_week_impact(self) -> None:
        impact = storage.describe_node_delete("p1", "p1-w1")
        self.assertEqual(impact["itemCount"], 3)
        self.assertEqual(impact["descendantCount"], 5)

    def test_single_item_impact(self) -> None:
        impact = storage.describe_node_delete("p1", "p1-i1")
        self.assertEqual(impact["itemCount"], 1)
        self.assertEqual(impact["descendantCount"], 0)

    def test_missing_node(self) -> None:
        with self.assertRaises(ValueError):
            storage.describe_node_delete("p1", "nope")


class TrashRestoreTests(ResetMixin, unittest.TestCase):
    def _trash_node(self, node_id: str, parent_id: str, position: int = 0, title: str = "任务") -> str:
        project, revision = storage.read_project("p1")
        node = find(project["tree"], node_id)
        storage._detach_node(project["tree"], node_id)          # 真实流程：先从项目里摘掉
        storage.write_project(project, revision)
        entry = storage.store_trash_item("node", "p1", title, node, parent_id=parent_id, position=position)
        return entry["id"]

    def test_restore_to_original_position(self) -> None:
        trash_id = self._trash_node("p1-i1", "p1-d1", 0, "任务1")
        result = storage.restore_trash_item(trash_id)
        self.assertEqual(result["restoredTo"], "original")
        self.assertEqual(texts(find(tree(), "p1-d1")["children"]), ["任务1", "任务2"])

    def test_restore_project_avoids_position_collision(self) -> None:
        """B6：恢复项目的 position 已被占用时排到最后，不能和现存项目撞号。

        删掉最后一个项目后新建的项目会重新拿到 position=0，此时恢复旧项目就撞号；
        ORDER BY position,project_id 撞号后只能按 id 排，列表顺序看起来是随机的。
        """
        storage.replace_projects([make_project("p1"), make_project("p2")], pre_backup=False)
        for project_id in ("p1", "p2"):
            storage.delete_project(project_id, storage.read_project(project_id)[1])
        storage.write_project(make_project("p3"), None)          # 空表 → position 0
        trash_id = next(entry["id"] for entry in storage.list_trash_items()
                        if entry["title"] == "项目p1")
        result = storage.restore_trash_item(trash_id)
        self.assertEqual(result["restoredTo"], "end", "位置被占用时要在响应里说明")
        with storage.open_state_database() as connection:
            rows = connection.execute(
                "SELECT project_id,position FROM projects ORDER BY position,project_id").fetchall()
        order = [str(row["project_id"]) for row in rows]
        positions = [int(row["position"]) for row in rows]
        self.assertEqual(len(positions), len(set(positions)), f"项目 position 撞号了：{positions}")
        self.assertEqual(order, ["p3", "p1"], "恢复的项目应该排到最后")
        self.assertEqual([summary["id"] for summary in storage.read_project_summaries()], ["p3", "p1"])

    def test_restore_project_keeps_free_position(self) -> None:
        """守卫：位置没被占用时仍然沿用删除前的位置（不能一律扔到最后）。"""
        storage.replace_projects([make_project("p1"), make_project("p2")], pre_backup=False)
        storage.delete_project("p1", storage.read_project("p1")[1])
        trash_id = next(entry["id"] for entry in storage.list_trash_items()
                        if entry["title"] == "项目p1")
        result = storage.restore_trash_item(trash_id)
        self.assertEqual(result["restoredTo"], "original")
        with storage.open_state_database() as connection:
            rows = connection.execute(
                "SELECT project_id,position FROM projects ORDER BY position,project_id").fetchall()
        self.assertEqual([(str(row["project_id"]), int(row["position"])) for row in rows],
                         [("p1", 0), ("p2", 1)])

    def test_orphan_box_when_parent_is_gone(self) -> None:
        """父节点已不存在时恢复到"孤立任务箱"，而不是拒绝恢复。"""
        trash_id = self._trash_node("p1-i1", "p1-d1", 0, "任务1")
        # 模拟父节点消失：直接从项目里删掉 d1
        project = storage.read_project("p1")[0]
        storage._detach_node(project["tree"], "p1-d1")
        storage.write_project(project, storage.read_project("p1")[1])

        self.assertEqual(storage.list_trash_items()[0]["restoreTarget"], "orphan")
        result = storage.restore_trash_item(trash_id)
        self.assertEqual(result["restoredTo"], "orphan")
        node = tree()
        box = next(entry for entry in node if entry["text"] == storage.ORPHAN_BOX_TITLE)
        self.assertEqual(texts(box["children"]), ["任务1"])

    def test_orphan_box_is_reused(self) -> None:
        first = self._trash_node("p1-i1", "p1-d1", 0, "任务1")
        second = self._trash_node("p1-i3", "p1-d2", 0, "任务3")
        project = storage.read_project("p1")[0]
        storage._detach_node(project["tree"], "p1-d1")
        storage._detach_node(project["tree"], "p1-d2")
        storage.write_project(project, storage.read_project("p1")[1])
        storage.restore_trash_item(first)
        storage.restore_trash_item(second)
        boxes = [entry for entry in tree() if entry["text"] == storage.ORPHAN_BOX_TITLE]
        self.assertEqual(len(boxes), 1, "孤立任务箱只应有一个")
        self.assertEqual(texts(boxes[0]["children"]), ["任务1", "任务3"])

    def test_restore_unavailable_when_project_is_gone(self) -> None:
        trash_id = self._trash_node("p1-i1", "p1-d1", 0, "任务1")
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM projects WHERE project_id='p1'")
        self.assertEqual(storage.list_trash_items()[0]["restoreTarget"], "unavailable")
        with self.assertRaises(ValueError):
            storage.restore_trash_item(trash_id)

    def test_batch_restore_reports_each_result(self) -> None:
        first = self._trash_node("p1-i1", "p1-d1", 0, "任务1")
        second = self._trash_node("p1-i3", "p1-d3", 0, "任务3")
        result = storage.restore_trash_items([first, second, "不存在的条目"])
        self.assertEqual(sorted(result["restored"]), sorted([first, second]))
        self.assertEqual(len(result["failed"]), 1)

    def test_whole_project_restore(self) -> None:
        project = storage.read_project("p1")[0]
        trash_id = storage.store_trash_item("project", "p1", str(project["name"]), project,
                                            position=0, revision=1)["id"]
        storage.delete_project("p1", storage.read_project("p1")[1])
        self.assertIsNone(storage.read_project("p1"))
        self.assertEqual(storage.list_trash_items()[0]["restoreTarget"], "original")
        result = storage.restore_trash_item(trash_id)
        self.assertEqual(result["kind"], "project")
        self.assertIsNotNone(storage.read_project("p1"))
        self.assertEqual(len(storage.read_project("p1")[0]["tree"]), 2)


class ActivityDetailSizeTests(ResetMixin, unittest.TestCase):
    def test_batch_activity_node_ids_are_capped(self) -> None:
        """item 4：批量操作的 detail 不再整串塞 500 个 nodeId（一行活动约 20KB）。"""
        ids = [f"n{index:04d}" for index in range(500)]
        project = make_project("p1")
        children = project["tree"][0]["children"][0]["children"]
        for node_id in ids:
            children.append(item(node_id, f"任务{node_id}"))
        storage.replace_projects([project], pre_backup=False)
        result = storage.batch_update_nodes(
            [{"projectId": "p1", "nodeId": node_id} for node_id in ids], "complete")
        self.assertEqual(result["changed"], 500)
        entry = next(row for row in storage.list_activity(10) if row["kind"] == "batch")
        detail = entry["detail"]
        self.assertEqual(detail["nodeCount"], 500)
        self.assertTrue(detail["nodeIdsTruncated"])
        self.assertEqual(len(detail["nodeIds"]), storage.ACTIVITY_NODE_IDS_MAX)
        self.assertLessEqual(len(json.dumps(detail, ensure_ascii=False)),
                             storage.ACTIVITY_NODE_IDS_MAX * 40 + 200, "detail 必须是有限大小")

    def test_small_batch_keeps_full_ids_without_truncation_flag(self) -> None:
        result = storage.batch_update_nodes(
            [{"projectId": "p1", "nodeId": "p1-i1"}, {"projectId": "p1", "nodeId": "p1-i3"}],
            "complete")
        self.assertEqual(result["changed"], 2)
        detail = next(row for row in storage.list_activity(10) if row["kind"] == "batch")["detail"]
        self.assertEqual(sorted(detail["nodeIds"]), ["p1-i1", "p1-i3"])
        self.assertEqual(detail["nodeCount"], 2)
        self.assertFalse(detail["nodeIdsTruncated"])


class ActivityTests(ResetMixin, unittest.TestCase):
    def test_activity_lists_newest_first_and_truncates(self) -> None:
        for index in range(3):
            storage.log_activity("test", f"第{index}条", project_id="p1", project_name="项目p1")
        entries = storage.list_activity(10)
        self.assertEqual([entry["summary"] for entry in entries], ["第2条", "第1条", "第0条"])
        self.assertEqual(len(storage.list_activity(2)), 2)
        self.assertEqual(storage.list_activity(0)[0]["summary"], "第2条", "非法 limit 回落到默认")

    def test_operations_are_recorded(self) -> None:
        storage.reorder_node("p1", "p1-i1", "p1-d2", 0)
        storage.duplicate_node("p1", "p1-i3")
        storage.duplicate_project("p1")
        kinds = [entry["kind"] for entry in storage.list_activity(10)]
        self.assertIn("reorder", kinds)
        self.assertIn("duplicate", kinds)
        self.assertIn("duplicate-project", kinds)

    def test_clear_activity(self) -> None:
        storage.log_activity("test", "一条")
        self.assertGreaterEqual(storage.clear_activity(), 1)
        self.assertEqual(storage.list_activity(10), [])


class BatchUpdateActivityTests(ResetMixin, unittest.TestCase):
    def test_batch_changes_are_logged(self) -> None:
        storage.batch_update_nodes([{"projectId": "p1", "nodeId": "p1-i1"}], "set-priority", "low")
        entries = [entry for entry in storage.list_activity(10) if entry["kind"] == "batch"]
        self.assertTrue(entries, "批量修改也应进活动历史")


if __name__ == "__main__":
    unittest.main(verbosity=2)
