"""节点级 patch 的回归测试（第六批性能优化 item 2）。

覆盖：update / append / delete 一个事务完成、revision 只前进一次、摘要只算受影响的统计、
不影响未涉及的节点、参数校验与冲突码。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-patch-test-")
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
    return {
        "id": project_id, "name": "补丁项目", "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": False,
        "tree": [{"id": f"{project_id}-w1", "type": "week", "text": "第1周", "completed": False,
                  "expanded": False, "createdAt": TODAY, "children": [
                      {"id": f"{project_id}-d1", "type": "day", "text": "单元1", "completed": False,
                       "expanded": False, "createdAt": TODAY, "children": [
                           item(f"{project_id}-i1", "任务1"),
                           item(f"{project_id}-i2", "任务2", optional=True),
                       ]}]}],
    }


def find(nodes, node_id):
    for node in nodes or []:
        if str(node.get("id")) == str(node_id):
            return node
        found = find(node.get("children") or [], node_id)
        if found is not None:
            return found
    return None


class NodePatchTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        storage.replace_projects([make_project()])
        self.revision = storage.read_project("p1")[1]

    def patch(self, ops, revision=None):
        # 默认用"当前"revision：patch 之后版本会前进，同一个用例里可以连续 patch
        expected = storage.read_project("p1")[1] if revision is None else revision
        return storage.patch_project_nodes("p1", expected, ops)

    def test_update_fields_and_summary(self) -> None:
        result = self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
            "completed": True, "completedAt": f"{TODAY}T10:00:00", "priority": "high",
            "dueDate": "2026-09-20", "estimateMinutes": 45, "tags": ["补丁"],
            "note": "备注", "links": [{"label": "文档", "url": "https://example.com"}],
            "repeat": {"freq": "daily"},
        }}])
        self.assertEqual(result["revision"], self.revision + 1)
        self.assertEqual(result["updated"], ["p1-i1"])
        self.assertEqual(result["summary"]["stats"]["remaining"], 0, "主线任务只剩这一个，完成即 0")
        node = find(storage.read_project("p1")[0]["tree"], "p1-i1")
        self.assertTrue(node["completed"])
        self.assertEqual(node["priority"], "high")
        self.assertEqual(node["dueDate"], "2026-09-20")
        self.assertEqual(node["estimateMinutes"], 45)
        self.assertEqual(node["tags"], ["补丁"])
        self.assertEqual(node["note"], "备注")
        self.assertEqual(node["links"][0]["url"], "https://example.com")
        self.assertEqual(node["repeat"], {"freq": "daily", "interval": 1})

    def test_update_review_field_writes_three_columns(self) -> None:
        """前端勾选任务时会带上 review（复习计划）：patch 必须认这个字段。

        真实浏览器测试暴露过 400「不支持的节点字段：review」——
        全量保存认它、patch 不认，于是"性能路径"在真机上一直回退成整棵树上传。
        """
        result = self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
            "completed": True, "completedAt": f"{TODAY}T09:00:00",
            "review": {"due": "2026-09-20", "learning": True,
                       "log": [{"at": TODAY, "result": "easy"}]},
        }}])
        self.assertEqual(result["updated"], ["p1-i1"])
        node = find(storage.read_project("p1")[0]["tree"], "p1-i1")
        self.assertEqual(node["review"]["due"], "2026-09-20")
        self.assertTrue(node["review"]["learning"])
        self.assertEqual(node["review"]["log"], [{"at": TODAY, "result": "easy"}])

    def test_update_review_null_clears_schedule(self) -> None:
        self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
            "completed": True, "review": {"due": "2026-09-20", "learning": False, "log": []}}}])
        self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {"review": None}}])
        node = find(storage.read_project("p1")[0]["tree"], "p1-i1")
        self.assertNotIn("review", node, "清空复习安排后不该再带 review")

    def test_unknown_field_still_rejected(self) -> None:
        with self.assertRaises(ValueError) as caught:
            self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {"nonsense": 1}}])
        self.assertIn("不支持的节点字段", str(caught.exception))

    def test_update_does_not_touch_other_nodes(self) -> None:
        before = find(storage.read_project("p1")[0]["tree"], "p1-i2")
        self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {"text": "改过的任务1"}}])
        after = find(storage.read_project("p1")[0]["tree"], "p1-i2")
        self.assertEqual(before, after, "没被 patch 的节点必须逐字段不变")

    def test_summary_counts_optional_separately(self) -> None:
        self.patch([{"op": "update", "nodeId": "p1-i2", "fields": {"completed": True}}])
        summary = storage.read_project_summaries()[0]
        self.assertEqual(summary["stats"]["optionalTotal"], 1)
        self.assertEqual(summary["stats"]["optionalCompleted"], 1)
        self.assertEqual(summary["stats"]["remaining"], 1, "主线任务仍未完成")

    def test_revision_only_advances_once_for_many_ops(self) -> None:
        result = self.patch([
            {"op": "update", "nodeId": "p1-i1", "fields": {"completed": True}},
            {"op": "update", "nodeId": "p1-i1", "fields": {"text": "再来一次"}},
            {"op": "append", "parentId": "p1-d1", "node": item("p1-new", "新任务")},
        ])
        self.assertEqual(result["revision"], self.revision + 1)
        self.assertEqual(storage.read_project("p1")[1], self.revision + 1)

    def test_append_puts_node_at_the_end_with_metadata(self) -> None:
        result = self.patch([{"op": "append", "parentId": "p1-d1", "node": item(
            "p1-new", "新任务", priority="mid", tags=["a"], dueDate="2026-09-25")}])
        self.assertEqual(result["appended"], [{"id": "p1-new", "parentId": "p1-d1"}])
        children = find(storage.read_project("p1")[0]["tree"], "p1-d1")["children"]
        self.assertEqual([node["text"] for node in children], ["任务1", "任务2", "新任务"])
        self.assertEqual(children[-1]["priority"], "mid")
        self.assertEqual(children[-1]["tags"], ["a"])

    def test_append_generates_id_when_missing(self) -> None:
        node = item("", "没有 id 的任务")
        node.pop("id")
        result = self.patch([{"op": "append", "parentId": "p1-d1", "node": node}])
        self.assertTrue(result["appended"][0]["id"])

    def test_append_rejects_bad_parent_and_duplicate_id(self) -> None:
        with self.assertRaises(ValueError):
            self.patch([{"op": "append", "parentId": "不存在", "node": item("x", "x")}])
        with self.assertRaises(ValueError) as ctx:
            self.patch([{"op": "append", "parentId": "p1-i1", "node": item("y", "y")}])
        self.assertIn("周或学习单元", str(ctx.exception))
        with self.assertRaises(ValueError):
            self.patch([{"op": "append", "parentId": "p1-d1", "node": item("p1-i1", "重复 id")}])

    def test_delete_removes_subtree_and_updates_summary(self) -> None:
        result = self.patch([{"op": "delete", "nodeId": "p1-d1"}])
        self.assertEqual(result["deleted"], ["p1-d1"])
        project = storage.read_project("p1")[0]
        self.assertEqual(find(project["tree"], "p1-d1"), None)
        self.assertEqual(find(project["tree"], "p1-i1"), None, "子节点一起删掉")
        self.assertEqual(result["summary"]["stats"]["total"], 0)
        self.assertEqual(storage.read_project_summaries()[0]["stats"]["remaining"], 0)

    def test_delete_removes_assessment_rows(self) -> None:
        self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
            "assessment": {"passed": True, "questionConversations": [[{"role": "user", "content": "答"}]]}}}])
        with storage.open_state_database() as connection:
            before = connection.execute(
                "SELECT COUNT(*) FROM assessments WHERE project_id='p1'").fetchone()[0]
        self.assertEqual(before, 1)
        self.patch([{"op": "delete", "nodeId": "p1-d1"}])
        with storage.open_state_database() as connection:
            after = connection.execute(
                "SELECT COUNT(*) FROM assessments WHERE project_id='p1'").fetchone()[0]
        self.assertEqual(after, 0, "删节点要级联删掉验收记录")

    def test_assessment_update_keeps_conversations_when_key_present(self) -> None:
        self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
            "assessment": {"passed": True, "questionConversations": [[{"role": "user", "content": "第一次"}]]}}}])
        self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
            "assessment": {"passed": False, "score": 40,
                           "questionConversations": [[{"role": "user", "content": "第二次"}]]}}}])
        node = find(storage.read_project("p1")[0]["tree"], "p1-i1")
        self.assertEqual(node["assessment"]["questionConversations"][0][0]["content"], "第二次")
        self.assertFalse(node["assessment"]["passed"])

    def test_validation_errors(self) -> None:
        with self.assertRaises(ValueError):
            self.patch([])
        with self.assertRaises(ValueError):
            self.patch([{"op": "explode", "nodeId": "p1-i1"}])
        with self.assertRaises(ValueError) as ctx:
            self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {"nope": 1}}])
        self.assertIn("不支持的节点字段", str(ctx.exception))
        with self.assertRaises(ValueError):
            self.patch([{"op": "update", "nodeId": "不存在", "fields": {"text": "x"}}])
        with self.assertRaises(ValueError):
            self.patch([{"op": "delete", "nodeId": "不存在"}])
        with self.assertRaises(ValueError):
            storage.patch_project_nodes("不存在项目", None, [{"op": "update", "nodeId": "x", "fields": {}}])
        with self.assertRaises(ValueError) as ctx:
            self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {"text": "x"}}] * (storage.MAX_PATCH_OPS + 1))
        self.assertIn("最多", str(ctx.exception))

    def test_unknown_project_and_revision_conflict(self) -> None:
        with self.assertRaises(storage.StateConflictError):
            self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {"text": "x"}}],
                       revision=self.revision + 5)
        # revision 为 None 表示不做乐观锁校验（内部调用用）
        storage.patch_project_nodes("p1", None, [{"op": "update", "nodeId": "p1-i1", "fields": {"text": "x"}}])
        self.assertEqual(find(storage.read_project("p1")[0]["tree"], "p1-i1")["text"], "x")

    def test_cleaning_matches_full_save(self) -> None:
        """patch 的字段清洗必须与整项目写入（clean_*）一致。"""
        self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
            "priority": "urgent", "dueDate": "2026-02-30", "estimateMinutes": -5,
            "tags": ["重复", "重复", "x"],
        }}])
        node = find(storage.read_project("p1")[0]["tree"], "p1-i1")
        self.assertEqual(node.get("priority", ""), "", "非法优先级被清空")
        self.assertEqual(node.get("dueDate", ""), "", "非法日期被清空")
        self.assertEqual(node.get("estimateMinutes", 0), 0, "负数被夹到 0")
        self.assertEqual(node.get("tags", []), ["重复", "x"], "标签去重")
        # 非 http(s) 链接与整项目保存一致：直接拒绝（前端本来就会先过滤）
        with self.assertRaises(ValueError):
            self.patch([{"op": "update", "nodeId": "p1-i1", "fields": {
                "links": [{"url": "javascript:alert(1)"}]}}])
        # 失败的 patch 不能改动任何东西
        still = find(storage.read_project("p1")[0]["tree"], "p1-i1")
        self.assertNotIn("links", still)

    def test_patch_logs_delete_activity(self) -> None:
        self.patch([{"op": "delete", "nodeId": "p1-i1"}])
        self.assertTrue(any(entry["kind"] == "delete" for entry in storage.list_activity(5)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
