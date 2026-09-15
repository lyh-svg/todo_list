"""任务元数据（优先级 / 截止日期 / 标签 / 预计耗时 / 备注 / 链接）与 schema 6 迁移的回归测试。

对应第四阶段批次 1（第 1~4、6 项日常功能；第 5 项五态状态按使用者决定不做）。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-meta-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "summary.sqlite3")

import storage  # noqa: E402

DB = Path(storage.DATABASE_FILE)


def make_project(project_id: str = "p1", name: str = "项目一", **item_fields) -> dict:
    item = {
        "id": f"{project_id}-i", "type": "item", "text": "任务1", "completed": False,
        "completedAt": None, "optional": False, "assessmentRequired": False,
        "assessmentHistory": 0, "assessment": None, "createdAt": "2026-09-15", "children": [],
    }
    item.update(item_fields)
    return {
        "id": project_id, "name": name, "description": "", "createdAt": "2026-09-15",
        "assessmentEnabled": False, "reviewEnabled": False,
        "tree": [{
            "id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": "2026-09-15", "children": [{
                "id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": "2026-09-15", "children": [item],
            }],
        }],
    }


def read_item(project_id: str = "p1") -> dict:
    project = storage.read_project(project_id)[0]
    return project["tree"][0]["children"][0]["children"][0]


class SchemaMigrationTests(unittest.TestCase):
    def test_schema_version_is_six(self) -> None:
        self.assertEqual(storage.SCHEMA_VERSION, 6)

    def test_v5_database_gains_metadata_columns_without_losing_data(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        # 造一个 v5 结构的库：没有元数据列，但有一条已完成的任务 + 复习安排
        with storage.open_state_database() as connection:
            connection.execute("PRAGMA user_version=5")
        storage.replace_projects([make_project()])
        with sqlite3.connect(DB) as connection:
            connection.execute("UPDATE nodes SET completed=1, completed_at='2026-09-10T08:00:00'")
            connection.execute("UPDATE nodes SET review_due='2026-09-20'")
            connection.execute("PRAGMA user_version=5")

        storage.ensure_schema()

        self.assertEqual(storage.database_user_version(), 6)
        with sqlite3.connect(DB) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(nodes)")}
        for column in ("priority", "due_date", "estimate_minutes", "tags", "note", "links"):
            self.assertIn(column, columns, f"v5 → v6 迁移必须补上 {column}")
        project_columns = None
        with sqlite3.connect(DB) as connection:
            project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
        self.assertIn("archived", project_columns)
        self.assertIn("last_opened_at", project_columns)
        item = read_item()
        self.assertTrue(item["completed"], "迁移不能丢已有完成状态")
        self.assertEqual(item["completedAt"], "2026-09-10T08:00:00")
        self.assertEqual(item["review"]["due"], "2026-09-20")
        # 新字段有安全默认值
        self.assertEqual(item.get("priority", ""), "")
        self.assertEqual(item.get("dueDate", ""), "")
        self.assertEqual(item.get("estimateMinutes", 0), 0)
        self.assertEqual(item.get("tags", []), [])
        self.assertEqual(item.get("note", ""), "")
        self.assertEqual(item.get("links", []), [])

    def test_indexes_created(self) -> None:
        with sqlite3.connect(DB) as connection:
            names = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'")}
        for index in ("idx_nodes_due", "idx_nodes_priority", "idx_projects_archived"):
            self.assertIn(index, names)


class MetadataRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def test_all_metadata_fields_round_trip(self) -> None:
        storage.replace_projects([make_project(
            priority="high",
            dueDate="2026-09-20",
            estimateMinutes=45,
            tags=["Python", "复习"],
            note="先看装饰器再写测试",
            links=[{"label": "官方文档", "url": "https://docs.python.org/3/"}],
        )])
        item = read_item()
        self.assertEqual(item["priority"], "high")
        self.assertEqual(item["dueDate"], "2026-09-20")
        self.assertEqual(item["estimateMinutes"], 45)
        self.assertEqual(item["tags"], ["Python", "复习"])
        self.assertEqual(item["note"], "先看装饰器再写测试")
        self.assertEqual(item["links"], [{"label": "官方文档", "url": "https://docs.python.org/3/"}])

    def test_metadata_survives_project_update(self) -> None:
        storage.replace_projects([make_project(priority="mid", dueDate="2026-09-21", tags=["A"])])
        project, revision = storage.read_project("p1")
        project["name"] = "改名了"
        storage.write_project(project, revision)
        item = read_item()
        self.assertEqual(item["priority"], "mid")
        self.assertEqual(item["dueDate"], "2026-09-21")
        self.assertEqual(item["tags"], ["A"])

    def test_export_import_snapshot_keeps_metadata(self) -> None:
        storage.replace_projects([make_project(priority="low", dueDate="2026-09-25", estimateMinutes=15,
                                               tags=["标签"], note="备注", links=[{"url": "https://a.example"}])])
        snapshot = storage.export_projects_snapshot()
        storage.replace_projects([], pre_backup=False)
        self.assertEqual(storage.read_project_summaries(), [])
        storage.replace_projects(snapshot["projects"], pre_backup=False)
        item = read_item()
        self.assertEqual(item["priority"], "low")
        self.assertEqual(item["dueDate"], "2026-09-25")
        self.assertEqual(item["estimateMinutes"], 15)
        self.assertEqual(item["tags"], ["标签"])
        self.assertEqual(item["note"], "备注")
        self.assertEqual(item["links"][0]["url"], "https://a.example")

    def test_non_item_nodes_do_not_get_metadata(self) -> None:
        storage.replace_projects([make_project(priority="high", dueDate="2026-09-20", tags=["x"])])
        project = storage.read_project("p1")[0]
        week = project["tree"][0]
        self.assertNotIn("priority", week)
        self.assertNotIn("dueDate", week)
        self.assertNotIn("tags", week)


class MetadataValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{DB}{suffix}").unlink(missing_ok=True)
        with storage.open_state_database() as connection:
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
        storage.ensure_schema()

    def test_priority_only_accepts_known_values(self) -> None:
        storage.replace_projects([make_project(priority="URGENT")])
        self.assertEqual(read_item().get("priority", ""), "", "未知优先级应被丢弃")
        for value in ("high", "mid", "low"):
            storage.replace_projects([make_project(priority=value)])
            self.assertEqual(read_item()["priority"], value)

    def test_due_date_rejects_invalid_values(self) -> None:
        for bad in ("2026-13-01", "2026-02-30", "tomorrow", "2026/09/20"):
            storage.replace_projects([make_project(dueDate=bad)])
            self.assertEqual(read_item().get("dueDate", ""), "", f"{bad} 应被丢弃")
        storage.replace_projects([make_project(dueDate="2026-09-20")])
        self.assertEqual(read_item()["dueDate"], "2026-09-20")

    def test_estimate_is_clamped(self) -> None:
        storage.replace_projects([make_project(estimateMinutes=-10)])
        self.assertEqual(read_item().get("estimateMinutes", 0), 0)
        storage.replace_projects([make_project(estimateMinutes=999999999)])
        self.assertEqual(read_item()["estimateMinutes"], storage.MAX_ESTIMATE_MINUTES)
        storage.replace_projects([make_project(estimateMinutes="30")])
        self.assertEqual(read_item()["estimateMinutes"], 30)

    def test_tags_are_deduped_truncated_and_capped(self) -> None:
        storage.replace_projects([make_project(tags=["A", "A", "  B  ", ""] + [f"t{i}" for i in range(30)])])
        tags = read_item()["tags"]
        self.assertEqual(len(tags), storage.MAX_TAGS)
        self.assertEqual(tags[:2], ["A", "B"])
        self.assertNotIn("", tags)
        storage.replace_projects([make_project(tags="not-a-list")])
        self.assertEqual(read_item().get("tags", []), [])

    def test_note_is_truncated(self) -> None:
        storage.replace_projects([make_project(note="x" * (storage.MAX_NOTE_CHARS + 100))])
        self.assertEqual(len(read_item()["note"]), storage.MAX_NOTE_CHARS)

    def test_links_require_http_scheme(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            storage.replace_projects([make_project(links=[{"label": "坏链接", "url": "javascript:alert(1)"}])])
        self.assertIn("http", str(ctx.exception))
        storage.replace_projects([make_project(links=[{"url": "https://ok.example"}])])
        links = read_item()["links"]
        self.assertEqual(links[0]["url"], "https://ok.example")
        self.assertEqual(links[0]["label"], "https://ok.example", "没给 label 时用 URL 兜底")

    def test_archived_project_flag_round_trips(self) -> None:
        project = make_project()
        project["archived"] = True
        storage.replace_projects([project])
        summaries = storage.read_project_summaries()
        self.assertTrue(summaries[0]["archived"])
        project, revision = storage.read_project("p1")
        self.assertTrue(project["archived"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
