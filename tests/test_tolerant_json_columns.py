"""B4 回归：坏掉的 JSON 列不能把整个工作台打成 500。

`/api/workbench`（工作台）对 `nodes.tags / links / repeat` 三列直接 `json.loads`，
其中任意一行坏掉都会让整个聚合接口抛 JSONDecodeError → 500：**一个坏任务让所有项目的
今天/逾期/收集箱全部打不开**。读项目那条路径（`_read_project_from_connection`）一直
是容错解析（解析失败回退空值），工作台漏了这一层。

这里断言：
1. 三列是坏 JSON 或"合法 JSON 但类型不对"时，工作台不抛异常，回退成 []/[]/None；
2. 坏掉的那一行仍然出现在分组里（解析失败不能连任务一起丢）；
3. 正常数据逐字段不被改写（容错解析不能顺手改口径）；
4. 读项目路径对同一份坏数据同样是容错回退（守卫既有行为）。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-tolerant-json-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import storage  # noqa: E402

TODAY = "2026-09-15"
NODE_ID = "i1"


def make_project() -> dict:
    item = {
        "id": NODE_ID, "type": "item", "text": "坏数据任务", "completed": False,
        "completedAt": None, "optional": False, "assessmentRequired": False,
        "assessmentHistory": 0, "createdAt": TODAY, "children": [],
        "dueDate": TODAY,
        "tags": ["标签甲", "标签乙"],
        "links": [{"label": "链接甲", "url": "https://example.com/a"}],
        "repeat": {"freq": "daily"},
    }
    return {
        "id": "p1", "name": "容错项目", "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": False, "archived": False,
        "tree": [{
            "id": "w1", "type": "week", "text": "第1周", "completed": False,
            "expanded": True, "createdAt": TODAY, "children": [{
                "id": "d1", "type": "day", "text": "单元1", "completed": False,
                "expanded": True, "createdAt": TODAY, "children": [item],
            }],
        }],
    }


def reset() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
    storage.ensure_schema()


class TolerantJsonColumnTests(unittest.TestCase):
    def setUp(self) -> None:
        reset()
        storage.write_project(make_project(), None)

    def tearDown(self) -> None:
        # tests/__init__.py 把库钉在共享临时目录上，本模块造的项目不能留给后面的用例。
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)

    # ---------- 工具 ----------

    def corrupt(self, column: str, value: str) -> None:
        """把一行的某一列改成指定文本；列名走白名单，避免拼出别的 SQL。"""
        self.assertIn(column, {"tags", "links", "repeat"})
        with storage.open_state_database() as connection:
            connection.execute(f"UPDATE nodes SET {column}=? WHERE node_id=?", (value, NODE_ID))

    def board_item(self) -> dict:
        board = storage.workbench(TODAY)
        entries = [entry for entry in board["groups"]["today"] if entry["nodeId"] == NODE_ID]
        self.assertEqual(len(entries), 1, "坏数据行不能从分组里消失")
        return entries[0]

    # ---------- 坏 JSON ----------

    def test_corrupt_json_columns_fall_back_to_empty(self) -> None:
        """三列同时坏掉：工作台照常返回，三个字段回退空值，任务仍在今天分组里。"""
        self.corrupt("tags", "{不是 JSON")
        self.corrupt("links", "[[[")
        self.corrupt("repeat", "daily")
        item = self.board_item()
        self.assertEqual(item["tags"], [])
        self.assertEqual(item["links"], [])
        self.assertIsNone(item["repeat"])
        self.assertEqual(item["text"], "坏数据任务")
        self.assertEqual(item["dueDate"], TODAY)

    def test_one_corrupt_row_does_not_break_other_projects(self) -> None:
        """一个坏任务不能让别的任务一起打不开（旧实现是整接口 500）。"""
        other = make_project()
        other["id"] = "p2"
        other["tree"][0]["children"][0]["children"][0]["id"] = "j1"
        other["tree"][0]["children"][0]["children"][0]["text"] = "好数据任务"
        storage.write_project(other, None)
        self.corrupt("tags", "{不是 JSON")
        board = storage.workbench(TODAY)
        texts = sorted(entry["text"] for entry in board["groups"]["today"])
        self.assertEqual(texts, ["坏数据任务", "好数据任务"])   # 按码点排序，坏(U+574F) < 好(U+597D)
        self.assertEqual(board["totals"]["today"], 2)

    def test_wrong_json_type_falls_back_to_empty(self) -> None:
        """合法 JSON 但类型不对（字符串/对象/数组）同样回退，不能把非列表塞给前端。"""
        self.corrupt("tags", '"看起来像标签"')
        self.corrupt("links", '{"label": "不是列表"}')
        self.corrupt("repeat", "[]")
        item = self.board_item()
        self.assertEqual(item["tags"], [])
        self.assertEqual(item["links"], [])
        self.assertIsNone(item["repeat"])

    # ---------- 正常数据不能被改口径 ----------

    def test_valid_columns_pass_through_unchanged(self) -> None:
        item = self.board_item()
        self.assertEqual(item["tags"], ["标签甲", "标签乙"])
        self.assertEqual(item["links"], [{"label": "链接甲", "url": "https://example.com/a"}])
        self.assertEqual(item["repeat"], {"freq": "daily", "interval": 1})

    # ---------- 读项目路径（守卫既有容错） ----------

    def test_read_project_tolerates_same_corruption(self) -> None:
        self.corrupt("tags", "{不是 JSON")
        self.corrupt("links", "[[[")
        self.corrupt("repeat", "daily")
        result = storage.read_project("p1")
        self.assertIsNotNone(result, "读项目不能因为坏列返回 None")
        project, _revision = result
        item = project["tree"][0]["children"][0]["children"][0]
        self.assertEqual(item["text"], "坏数据任务")
        # 读项目侧的口径是"空值就不写这个键"，坏数据要落到这个口径里。
        self.assertNotIn("tags", item)
        self.assertNotIn("links", item)
        self.assertNotIn("repeat", item)

    def test_read_project_keeps_valid_columns(self) -> None:
        project, _revision = storage.read_project("p1")
        item = project["tree"][0]["children"][0]["children"][0]
        self.assertEqual(item["tags"], ["标签甲", "标签乙"])
        self.assertEqual(item["links"], [{"label": "链接甲", "url": "https://example.com/a"}])
        self.assertEqual(item["repeat"], {"freq": "daily", "interval": 1})


if __name__ == "__main__":
    unittest.main()


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
