"""导出快照与导入往返的回归测试。

只用标准库（unittest），不引入任何第三方依赖，也不触碰 data/ 下的真实数据库：
所有存储路径通过环境变量指向临时目录，且必须在 import storage 之前设置。

运行：
    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-export-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")

import storage  # noqa: E402  （必须在上面的环境变量之后导入）

# 前端的 DATA_SCHEMA_VERSION（js/app.js）。导入时 extractProjects 会拒绝更大的值。
FRONTEND_DATA_SCHEMA_VERSION = 2


def make_project(project_id: str, name: str, *, completed_item: bool = False) -> dict:
    """构造一个"周 → 学习单元 → 任务"的最小项目。"""
    return {
        "id": project_id,
        "name": name,
        "description": "测试用项目",
        "createdAt": "2026-09-15",
        "assessmentEnabled": True,
        "reviewEnabled": False,
        "tree": [
            {
                "id": f"{project_id}-w1",
                "type": "week",
                "text": "第1周：基础",
                "completed": False,
                "expanded": False,
                "createdAt": "2026-09-15",
                "children": [
                    {
                        "id": f"{project_id}-d1",
                        "type": "day",
                        "text": "单元1：概念",
                        "completed": False,
                        "expanded": False,
                        "createdAt": "2026-09-15",
                        "children": [
                            {
                                "id": f"{project_id}-i1",
                                "type": "item",
                                "text": "任务1：解释机制",
                                "completed": completed_item,
                                "completedAt": "2026-09-15T10:00:00" if completed_item else None,
                                "optional": False,
                                "assessmentRequired": True,
                                "assessmentHistory": 2,
                                "assessment": {
                                    "passed": True,
                                    "score": 91,
                                    "summary": "讲清了机制",
                                    "stage": "implementation",
                                    "questionIndex": 2,
                                    "questionPassed": True,
                                    "questionSet": ["闭包捕获什么？", "什么时候会泄漏？", "如何验证？"],
                                    "questionAnswers": ["变量引用", "循环引用", "打个日志"],
                                    "questionConversations": [
                                        [{"role": "user", "content": "变量引用"},
                                         {"role": "assistant", "content": "对，是变量本身"}],
                                        [{"role": "user", "content": "循环引用"}],
                                    ],
                                    "questionResults": [
                                        {"passed": True, "score": 90, "summary": "第一题通过"},
                                        {"passed": True, "score": 88, "summary": "第二题通过"},
                                    ],
                                    "uploadedFiles": [{"name": "demo.py", "content": "x = 1\n"}],
                                    "model": "flash",
                                    "implementationDraft": "实现草稿",
                                    "answer": "最终回答",
                                },
                                "createdAt": "2026-09-15",
                                "review": {
                                    "due": "2026-09-16",
                                    "learning": False,
                                    "log": [{"at": "2026-09-15", "result": "good"},
                                            {"at": "2026-09-17", "result": "hard"}],
                                },
                                # 元数据（第六列）也必须在往返里保住
                                "priority": "high",
                                "dueDate": "2026-09-16",
                                "estimateMinutes": 45,
                                "tags": ["Python", "复习"],
                                "note": "先讲结论再讲原因",
                                "links": [{"label": "文档", "url": "https://example.com/doc"}],
                                "repeat": {"freq": "weekly", "weekday": 3, "until": "2026-12-31"},
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def count_items(project: dict) -> int:
    total = 0

    def walk(nodes):
        nonlocal total
        for node in nodes or []:
            if node.get("type") == "item":
                total += 1
            walk(node.get("children"))

    walk(project.get("tree"))
    return total


class ExportSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        # 每个测试都从空库开始，避免相互影响。
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)

    def test_snapshot_has_frontend_import_contract(self) -> None:
        """快照必须是前端 extractProjects 能接受的形状。"""
        snapshot = storage.export_projects_snapshot()
        self.assertIsInstance(snapshot, dict)
        self.assertIn("projects", snapshot)
        self.assertIsInstance(snapshot["projects"], list)
        self.assertEqual(snapshot["schemaVersion"], FRONTEND_DATA_SCHEMA_VERSION)
        self.assertLessEqual(snapshot["schemaVersion"], FRONTEND_DATA_SCHEMA_VERSION)
        self.assertTrue(snapshot.get("exportedAt"))

    def test_snapshot_contains_full_trees_not_summaries(self) -> None:
        """导出必须带完整 tree；否则导入后项目会变成空壳（本次修复的核心回归）。"""
        storage.write_project(make_project("p1", "项目一"), None)
        storage.write_project(make_project("p2", "项目二", completed_item=True), None)

        snapshot = storage.export_projects_snapshot()
        self.assertEqual(len(snapshot["projects"]), 2)

        by_name = {project["name"]: project for project in snapshot["projects"]}
        self.assertEqual(set(by_name), {"项目一", "项目二"})
        for project in snapshot["projects"]:
            self.assertNotIn("stats", project)
            self.assertNotIn("_revision", project)
            self.assertEqual(count_items(project), 1, f"{project['name']} 的 tree 被导出成空壳")
            week = project["tree"][0]
            self.assertEqual(week["type"], "week")
            self.assertEqual(week["children"][0]["type"], "day")
            self.assertEqual(week["children"][0]["children"][0]["type"], "item")

        # 序列化后仍可被前端 JSON.parse + extractProjects 读取
        round_tripped = json.loads(json.dumps(snapshot, ensure_ascii=False))
        self.assertEqual(round_tripped["schemaVersion"], FRONTEND_DATA_SCHEMA_VERSION)
        self.assertEqual(len(round_tripped["projects"]), 2)

    def test_snapshot_import_roundtrip_preserves_projects(self) -> None:
        """导出 → 导入 必须无损：项目、节点、完成态、复习、验收记录全部一致。"""
        storage.write_project(make_project("p1", "项目一"), None)
        storage.write_project(make_project("p2", "项目二", completed_item=True), None)
        expected = {pid: storage.read_project(pid)[0] for pid in ("p1", "p2")}

        snapshot = storage.export_projects_snapshot()
        storage.replace_projects(snapshot["projects"])
        actual = {pid: storage.read_project(pid)[0] for pid in ("p1", "p2")}

        self.assertEqual(actual, expected)

    def test_snapshot_import_replaces_everything(self) -> None:
        """导入是整体替换：库里多出来的项目会被清掉。"""
        storage.write_project(make_project("p1", "项目一"), None)
        storage.write_project(make_project("p2", "项目二"), None)
        storage.write_project(make_project("p3", "将被删除的项目"), None)
        snapshot = storage.export_projects_snapshot()
        snapshot["projects"] = [p for p in snapshot["projects"] if p["id"] != "p3"]

        storage.replace_projects(snapshot["projects"])
        names = [summary["name"] for summary in storage.read_project_summaries()]
        self.assertEqual(sorted(names), ["项目一", "项目二"])
        self.assertIsNone(storage.read_project("p3"))

    def test_roundtrip_keeps_review_assessment_history_and_metadata(self) -> None:
        """逐字段钉住：复习、验收（含逐题对话/结果/附件）、历史次数与六类元数据都不能丢。"""
        storage.write_project(make_project("p1", "项目一", completed_item=True), None)
        before = storage.read_project("p1")[0]

        snapshot = storage.export_projects_snapshot()
        text = json.dumps(snapshot, ensure_ascii=False)
        for needle in ('"review"', '"assessment"', '"questionConversations"', '"questionResults"',
                       '"uploadedFiles"', '"assessmentHistory"', '"repeat"', '"priority"',
                       '"dueDate"', '"estimateMinutes"', '"tags"', '"note"', '"links"'):
            self.assertIn(needle, text, f"导出内容里缺少 {needle}（字段被摘要化丢掉了）")

        storage.replace_projects(snapshot["projects"])
        after = storage.read_project("p1")[0]
        self.assertEqual(after, before, "导出 → 导入必须逐字节一致")

        node = after["tree"][0]["children"][0]["children"][0]
        self.assertEqual(node["assessment"]["questionConversations"][1][0]["content"], "循环引用")
        self.assertEqual(node["assessment"]["questionResults"][1]["score"], 88)
        self.assertEqual(node["assessment"]["uploadedFiles"][0]["name"], "demo.py")
        self.assertEqual(node["assessment"]["implementationDraft"], "实现草稿")
        self.assertTrue(node["assessment"]["passed"])
        self.assertEqual(node["assessmentHistory"], 2)
        self.assertEqual(node["assessmentRequired"], True)
        self.assertEqual(node["review"]["log"][1], {"at": "2026-09-17", "result": "hard"})
        self.assertEqual(node["repeat"], {"freq": "weekly", "weekday": 3, "until": "2026-12-31"})
        self.assertEqual(node["priority"], "high")
        self.assertEqual(node["dueDate"], "2026-09-16")
        self.assertEqual(node["estimateMinutes"], 45)
        self.assertEqual(node["tags"], ["Python", "复习"])
        self.assertEqual(node["note"], "先讲结论再讲原因")
        self.assertEqual(node["links"], [{"label": "文档", "url": "https://example.com/doc"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
