"""第五批（中等难度任务管理）导入/导出/模板/自动归档的回归测试。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-import-export-test-")
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


def make_project(project_id: str = "p1", name: str = "项目一") -> dict:
    return {
        "id": project_id, "name": name, "description": "说明文字", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": False,
        "tree": [{
            "id": f"{project_id}-w1", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": f"{project_id}-d1", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": [
                    item(f"{project_id}-i1", "带,逗号与\"引号\"的任务", priority="high",
                         dueDate="2026-09-20", estimateMinutes=45, tags=["Python", "复习"],
                         note="第一行\n第二行", links=[{"label": "文档", "url": "https://example.com"}],
                         repeat={"freq": "weekly", "weekday": 3}),
                    item(f"{project_id}-i2", "已完成任务", completed=True,
                         completedAt=f"{TODAY}T09:00:00",
                         assessment={"passed": True, "score": 88},
                         assessmentHistory=1,
                         review={"due": TODAY, "learning": False, "log": [{"at": TODAY, "result": "good"}]}),
                ],
            }],
        }],
    }


class ResetMixin:
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()
        storage.replace_projects([make_project()])


class ExportMarkdownTests(ResetMixin, unittest.TestCase):
    def test_structure(self) -> None:
        text = storage.export_markdown()
        self.assertIn("# 学习计划导出", text)
        self.assertIn("## 项目一", text)
        self.assertIn("> 说明文字", text)
        self.assertIn("### 第1周", text)
        self.assertIn("#### 单元1", text)
        self.assertIn("- [ ] 带", text, "未完成任务是空复选框")
        self.assertIn("- [x] 已完成任务", text)

    def test_metadata_notes_links_and_repeat(self) -> None:
        text = storage.export_markdown()
        self.assertIn("优先级 高", text)
        self.assertIn("截止 2026-09-20", text)
        self.assertIn("预计 45 分钟", text)
        self.assertIn("周期 每周三", text)
        self.assertIn("#Python", text)
        self.assertIn("> 第一行", text)
        self.assertIn("> 第二行", text)
        self.assertIn("[文档](https://example.com)", text)

    def test_empty_project_has_no_items_note(self) -> None:
        project = make_project("p2", "空项目")
        project["tree"] = [{"id": "p2-w", "type": "week", "text": "第1周", "completed": False,
                            "expanded": False, "createdAt": TODAY,
                            "children": [{"id": "p2-d", "type": "day", "text": "单元1",
                                          "completed": False, "expanded": False,
                                          "createdAt": TODAY, "children": []}]}]
        storage.replace_projects([project])
        self.assertIn("（没有任务）", storage.export_markdown())


class ExportCsvTests(ResetMixin, unittest.TestCase):
    def rows(self) -> list[list[str]]:
        text = storage.export_csv()
        self.assertTrue(text.startswith("\ufeff"), "CSV 带 UTF-8 BOM，Excel 打开中文才不乱码")
        return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))

    def test_header_and_row_types(self) -> None:
        rows = self.rows()
        self.assertEqual(rows[0], storage.CSV_COLUMNS)
        types = [row[4] for row in rows[1:]]
        self.assertEqual(types, ["week", "day", "item", "item"])

    def test_values_and_escaping(self) -> None:
        rows = self.rows()
        first_item = rows[3]
        self.assertEqual(first_item[0], "项目一")
        self.assertEqual(first_item[1], "第1周")
        self.assertEqual(first_item[2], "单元1")
        self.assertEqual(first_item[3], '带,逗号与"引号"的任务', "含逗号/引号的字段要能原样解析回来")
        self.assertEqual(first_item[5], "否")
        self.assertEqual(first_item[8], "high")
        self.assertEqual(first_item[9], "2026-09-20")
        self.assertEqual(first_item[10], "45")
        self.assertEqual(first_item[11], "Python、复习")
        self.assertIn("第一行", first_item[12])
        self.assertIn("第二行", first_item[12])
        self.assertEqual(first_item[13], "https://example.com")
        self.assertEqual(first_item[14], "每周三")
        done = rows[4]
        self.assertEqual(done[5], "是")
        self.assertTrue(done[16].startswith(TODAY))

    def test_row_count_matches_tree(self) -> None:
        self.assertEqual(len(self.rows()) - 1, 4, "1 周 + 1 单元 + 2 任务")


class TemplateTests(ResetMixin, unittest.TestCase):
    def test_builtin_templates_exist(self) -> None:
        templates = storage.list_templates()
        ids = {entry["id"] for entry in templates}
        self.assertIn("builtin-8-week-review", ids)
        self.assertIn("builtin-debug-drill", ids)
        eight = next(entry for entry in templates if entry["id"] == "builtin-8-week-review")
        self.assertEqual(len(eight["tree"]), 8)
        self.assertEqual(len(eight["tree"][0]["children"]), 3)

    def test_create_from_template_generates_ids(self) -> None:
        result = storage.create_project_from_template("builtin-debug-drill", name="我的排错训练")
        project = result["project"]
        self.assertEqual(project["name"], "我的排错训练")
        stored = storage.read_project(project["id"])[0]
        self.assertEqual(len(stored["tree"][0]["children"][0]["children"]), 4)
        for node in storage._walk_nodes(stored["tree"]):
            self.assertTrue(node["id"], "模板节点必须有新 ID")
            self.assertFalse(node.get("completed"))

    def test_create_from_unknown_template(self) -> None:
        with self.assertRaises(ValueError):
            storage.create_project_from_template("不存在")

class ImportPreviewTests(ResetMixin, unittest.TestCase):
    def incoming(self, project_id: str = "p1", *, extra_node: bool = True) -> dict:
        project = make_project(project_id)
        if extra_node:
            project["tree"][0]["children"][0]["children"].append(item(f"{project_id}-i3", "新任务"))
        project["tree"][0]["children"][0]["children"][0]["text"] = "改过标题的任务"
        return project

    def test_duplicates_are_reported(self) -> None:
        duplicated = make_project("dup", "重复项目")
        problems = storage.find_import_duplicate_ids([duplicated, duplicated])
        self.assertTrue(any("重复的项目 ID" in problem for problem in problems))
        bad_nodes = make_project("n1", "重复节点")
        bad_nodes["tree"][0]["children"][0]["children"].append(item("n1-i1", "又一个同 ID 任务"))
        problems = storage.find_import_duplicate_ids([bad_nodes])
        self.assertTrue(any("重复的节点 ID" in problem for problem in problems))

    def test_preview_replace_reports_removed_projects_and_deleted_nodes(self) -> None:
        storage.replace_projects([make_project("p1"), make_project("p2", "会被删掉")])
        preview = storage.preview_import([self.incoming("p1")], "replace")
        self.assertEqual([entry["id"] for entry in preview["removedProjects"]], ["p2"])
        self.assertGreater(preview["totals"]["deletedNodes"], 0)
        self.assertEqual(preview["mode"], "replace")

    def test_preview_merge_counts_added_and_updated_and_keeps_local_only(self) -> None:
        preview = storage.preview_import([self.incoming("p1")], "merge")
        self.assertEqual(preview["removedProjects"], [])
        self.assertEqual(len(preview["updatedProjects"]), 1)
        entry = preview["updatedProjects"][0]
        self.assertEqual(entry["addedNodes"], 1, "新增一个任务")
        self.assertGreaterEqual(entry["updatedNodes"], 3, "已有节点算更新")
        self.assertEqual(preview["totals"]["keptLocalOnlyNodes"], 0)
        self.assertEqual(preview["totals"]["deletedNodes"], 0, "合并模式不删任何东西")

    def test_preview_new_project_mode(self) -> None:
        preview = storage.preview_import([self.incoming("brand-new", extra_node=False)], "new")
        self.assertEqual(len(preview["newProjects"]), 1)
        self.assertEqual(preview["updatedProjects"], [])
        self.assertEqual(preview["newProjects"][0]["itemCount"], 2)

    def test_preview_reports_ai_history(self) -> None:
        preview = storage.preview_import([self.incoming()], "merge")
        self.assertEqual(preview["aiHistory"]["nodesWithAssessment"], 1)
        self.assertEqual(preview["aiHistory"]["nodesWithReview"], 1)
        self.assertEqual(preview["aiHistory"]["policy"], "保留")
        preview = storage.preview_import([self.incoming()], "merge", keep_ai_history=False)
        self.assertIn("清空", preview["aiHistory"]["policy"])

    def test_invalid_mode(self) -> None:
        with self.assertRaises(ValueError):
            storage.preview_import([self.incoming()], "随便")


class ImportModeTests(ResetMixin, unittest.TestCase):
    def incoming(self, project_id: str = "p1") -> dict:
        project = make_project(project_id)
        project["tree"][0]["children"][0]["children"].append(item(f"{project_id}-i3", "新任务"))
        project["tree"][0]["children"][0]["children"][0]["text"] = "改过标题的任务"
        return project

    def test_merge_updates_adds_and_keeps_local_only(self) -> None:
        # 本地先加一个"只有本地才有"的任务
        project, revision = storage.read_project("p1")
        project["tree"][0]["children"][0]["children"].append(item("p1-local", "本地独有"))
        storage.write_project(project, revision)

        result = storage.import_projects([self.incoming("p1")], "merge")
        self.assertEqual(result["mode"], "merge")
        stored = storage.read_project("p1")[0]
        items = stored["tree"][0]["children"][0]["children"]
        titles = [entry["text"] for entry in items]
        self.assertIn("改过标题的任务", titles, "同 ID 节点被新内容覆盖")
        self.assertIn("新任务", titles, "新节点被追加")
        self.assertIn("本地独有", titles, "本地独有的节点不能被删")

    def test_merge_is_transactional_and_bumps_revision(self) -> None:
        before = storage.read_project("p1")[1]
        storage.import_projects([self.incoming("p1")], "merge")
        self.assertEqual(storage.read_project("p1")[1], before + 1)

    def test_merge_adds_unknown_project(self) -> None:
        storage.import_projects([make_project("p9", "新项目")], "merge")
        self.assertIsNotNone(storage.read_project("p9"))

    def test_new_mode_regenerates_project_ids(self) -> None:
        storage.import_projects([self.incoming("p1")], "new")
        summaries = storage.read_project_summaries()
        self.assertEqual(len(summaries), 2, "原项目保留，新导入的是另一个项目")
        names = sorted(entry["name"] for entry in summaries)
        self.assertEqual(names, ["项目一", "项目一"])
        ids = {entry["id"] for entry in summaries}
        self.assertIn("p1", ids)

    def test_replace_mode_still_replaces_everything(self) -> None:
        storage.import_projects([make_project("only", "只剩这个")], "replace")
        summaries = storage.read_project_summaries()
        self.assertEqual([entry["id"] for entry in summaries], ["only"])

    def test_keep_ai_history_false_strips_assessment_and_review(self) -> None:
        storage.import_projects([self.incoming("p1")], "merge", keep_ai_history=False)
        stored = storage.read_project("p1")[0]
        second = stored["tree"][0]["children"][0]["children"][1]
        self.assertIsNone(second.get("assessment"))
        self.assertEqual(second.get("assessmentHistory", 0), 0)
        self.assertNotIn("review", second)

    def test_duplicates_are_rejected_before_writing_anything(self) -> None:
        duplicated = make_project("dup", "重复")
        before = storage.read_project_summaries()
        with self.assertRaises(ValueError) as ctx:
            storage.import_projects([duplicated, duplicated], "merge")
        self.assertIn("重复", str(ctx.exception))
        self.assertEqual(storage.read_project_summaries(), before, "拒绝导入时不能改动数据")

    def test_import_is_logged(self) -> None:
        storage.import_projects([self.incoming("p1")], "merge")
        self.assertTrue(any(entry["kind"] == "import" for entry in storage.list_activity(5)))


