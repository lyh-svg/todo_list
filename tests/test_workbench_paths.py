"""P3 回归：路径只为结果集构建，且三个接口的输出逐字段不变 + 工作台变更指纹能短路。

背景（实测 10k 节点）：`_node_locations()` 每次把全库节点的 text 读进内存、为每个节点向上拼路径，
一次 26.7 ms；而 workbench/复习队列/搜索真正需要的行往往只有几十到几千。
workbench 还会给**全库每个任务**造一遍 item 字典（含 json.loads），实际只有少数进分组。

这里断言两件事：
1. 新实现（只为给定行建路径）与旧的整表实现在**同样的节点上逐字段一致**；
2. 工作台的"没变就短路"（`since`）不会漏掉任何会改变分组的变更。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-workbench-paths-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import storage  # noqa: E402

TODAY = "2026-09-15"          # 参考日期；horizon = +7 天 = 2026-09-22
HORIZON = "2026-09-22"


def reference_locations(connection) -> dict[tuple[str, str], dict]:
    """旧实现的逐行拷贝：整表读进来，为每个节点向上拼路径。

    用它当"标准答案"，保证新实现没有偷偷改掉 path/ancestorIds 的口径。
    """
    rows = connection.execute("SELECT project_id,node_id,parent_id,text FROM nodes").fetchall()
    parent: dict[tuple[str, str], tuple[str | None, str]] = {}
    for row in rows:
        parent[(str(row["project_id"]), str(row["node_id"]))] = (row["parent_id"], str(row["text"] or ""))
    locations: dict[tuple[str, str], dict] = {}
    for key in parent:
        labels: list[str] = []
        ancestors: list[str] = []
        entry = parent.get(key)
        cursor: str | None = str(entry[0]) if entry and entry[0] is not None else None
        seen: set[str] = set()
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            ancestors.append(cursor)
            parent_entry = parent.get((key[0], cursor))
            if not parent_entry:
                break
            if parent_entry[1]:
                labels.append(parent_entry[1])
            cursor = str(parent_entry[0]) if parent_entry[0] is not None else None
        locations[key] = {"path": " / ".join(reversed(labels)), "ancestorIds": list(reversed(ancestors))}
    return locations


class CountingConnection(storage._ManagedConnection):
    """记录执行过的 SQL，用来断言"只查了周/单元、只查一次"。"""

    statements: list[str] = []

    def execute(self, sql, *args, **kwargs):
        CountingConnection.statements.append(" ".join(str(sql).split()))
        return super().execute(sql, *args, **kwargs)


def item_node(node_id: str, text: str, *, completed: bool = False, due: str = "",
              review_due: str = "", optional: bool = False) -> dict:
    node = {
        "id": node_id, "type": "item", "text": text, "completed": completed,
        "completedAt": f"{TODAY}T09:00:00" if completed else None, "optional": optional,
        "assessmentRequired": False, "assessmentHistory": 0, "createdAt": TODAY, "children": [],
    }
    if due:
        node["dueDate"] = due
    if review_due:
        node["review"] = {"due": review_due, "learning": False, "log": []}
    return node


def container(node_id: str, node_type: str, text: str, children: list) -> dict:
    return {"id": node_id, "type": node_type, "text": text, "completed": False,
            "expanded": True, "createdAt": TODAY, "children": children}


def project(project_id: str, items: list, *, name: str = "", archived: bool = False,
            nested: bool = False) -> dict:
    holder = container(f"{project_id}-d1", "day", "单元1", items)
    if nested:
        holder = container(f"{project_id}-d0", "day", "外层单元", [holder])
    return {
        "id": project_id, "name": name or f"项目 {project_id}", "description": "",
        "createdAt": TODAY, "assessmentEnabled": False, "reviewEnabled": True,
        "archived": archived,
        "tree": [container(f"{project_id}-w1", "week", "第1周", [holder])],
    }


def reset() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
    storage.ensure_schema()


def group_texts(board: dict, name: str) -> list[str]:
    return sorted(item["text"] for item in board["groups"][name])


class NodeLocationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset()
        storage.write_project(project("p1", [
            item_node("i1", "普通任务"),
            item_node("i2", "逾期任务", due="2026-09-14"),
        ]), None)
        storage.write_project(project("p2", [
            item_node("j1", "深层任务", completed=True, review_due=TODAY),
        ], nested=True), None)

    def node_rows(self, *keys: tuple[str, str]):
        with storage.open_state_database() as connection:
            rows = connection.execute(
                "SELECT project_id,node_id,parent_id,text,type FROM nodes").fetchall()
        wanted = {(str(row["project_id"]), str(row["node_id"])) for row in rows}
        if keys:
            wanted &= set(keys)
        return [row for row in rows if (str(row["project_id"]), str(row["node_id"])) in wanted], wanted

    def test_matches_reference_implementation(self) -> None:
        rows, wanted = self.node_rows()
        with storage.open_state_database() as connection:
            expected = reference_locations(connection)
            actual = storage._node_locations(connection, rows)
        self.assertEqual(set(actual), wanted, "返回的键必须正好是传入的行")
        for key in wanted:
            self.assertEqual(actual[key], expected[key], f"{key} 的路径与旧实现不一致")

    def test_container_and_dangling_parent_edge_cases(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute(
                "INSERT INTO nodes(project_id,node_id,id_json,parent_id,position,type,text,completed,"
                "optional,assessment_required,assessment_history,expanded,created_at,completed_at) "
                "VALUES('p1','orphan','\"orphan\"','ghost',9,'item','孤儿任务',0,0,0,0,0,?, '')", (TODAY,))
        rows, _ = self.node_rows(("p1", "i1"), ("p1", "orphan"), ("p1", "p1-d1"), ("p1", "p1-w1"))
        with storage.open_state_database() as connection:
            expected = reference_locations(connection)
            actual = storage._node_locations(connection, rows)
        for key in (("p1", "i1"), ("p1", "orphan"), ("p1", "p1-d1"), ("p1", "p1-w1")):
            self.assertIn(key, actual)
            self.assertEqual(actual[key], expected[key], f"{key} 的路径与旧实现不一致")

    def test_only_reads_containers_instead_of_every_node(self) -> None:
        # 造 300 个任务，只为其中 1 个要路径：查询数必须是 1，且只查 week/day
        items = [item_node(f"big{i}", f"任务 {i}") for i in range(300)]
        storage.write_project(project("big", items), None)
        rows, _ = self.node_rows(("big", "big7"))
        original = storage._ManagedConnection
        storage._ManagedConnection = CountingConnection
        CountingConnection.statements = []
        try:
            with storage.open_state_database() as connection:
                CountingConnection.statements = []
                locations = storage._node_locations(connection, rows)
        finally:
            storage._ManagedConnection = original
        self.assertEqual(locations[("big", "big7")]["path"], "第1周 / 单元1")
        selects = [sql for sql in CountingConnection.statements if sql.upper().startswith("SELECT")]
        self.assertEqual(len(selects), 1, f"应该只查一次，实际 {len(selects)} 次：{selects}")
        self.assertIn("type IN ('week','day')", selects[0], "只应该读周/单元，不能把任务也读出来")


class WorkbenchGroupTests(unittest.TestCase):
    def setUp(self) -> None:
        reset()
        storage.write_project(project("p1", [
            item_node("overdue", "逾期任务", due="2026-09-14"),
            item_node("today", "今天到期", due=TODAY),
            item_node("edge", "刚好第7天", due=HORIZON),
            item_node("beyond", "第8天以后", due="2026-09-23"),
            item_node("nodue", "没有日期"),
            item_node("done", "完成了要复习", completed=True, review_due=TODAY),
            item_node("donefuture", "完成了但复习在未来", completed=True, review_due="2026-09-20"),
            item_node("donepastdue", "完成了带过期截止", completed=True, due="2026-09-01"),
            item_node("optional", "选做但也到期", due=TODAY, optional=True),
        ]), None)
        storage.write_project(project("inbox", [
            item_node("inbox1", "收集箱无日期"),
            item_node("inbox2", "收集箱今天到期", due=TODAY),
            item_node("inbox3", "收集箱很远", due="2026-09-30"),
        ], name="收集箱"), None)
        storage.write_project(project("arch", [
            item_node("arch1", "归档项目里的到期任务", due=TODAY),
        ], archived=True), None)

    def test_group_membership_is_exact(self) -> None:
        board = storage.workbench(TODAY)
        self.assertEqual(group_texts(board, "overdue"), ["逾期任务"])
        # 收集箱里"有今天截止"的任务归"今天"，收集箱分组只收没被日期分组收走的
        self.assertEqual(group_texts(board, "today"), ["今天到期", "收集箱今天到期", "选做但也到期"])
        self.assertEqual(group_texts(board, "next7"), ["刚好第7天"])
        self.assertEqual(group_texts(board, "reviewToday"), ["完成了要复习"])
        self.assertEqual(group_texts(board, "inbox"), ["收集箱很远", "收集箱无日期"])
        self.assertEqual(board["totals"], {"overdue": 1, "today": 3, "next7": 1,
                                          "reviewToday": 1, "inbox": 2})

    def test_path_and_ancestors_are_filled(self) -> None:
        board = storage.workbench(TODAY)
        item = board["groups"]["today"][0]
        self.assertEqual(item["path"], "第1周 / 单元1")
        self.assertEqual(item["ancestorIds"], ["p1-w1", "p1-d1"])

    def test_excluded_items_are_not_anywhere(self) -> None:
        board = storage.workbench(TODAY)
        shown = {item["text"] for items in board["groups"].values() for item in items}
        for text in ("第8天以后", "没有日期", "完成了但复习在未来", "完成了带过期截止",
                     "归档项目里的到期任务"):
            self.assertNotIn(text, shown)


class WorkbenchVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset()
        storage.write_project(project("p1", [item_node("i1", "今天到期", due=TODAY)]), None)

    def version(self, since: str | None = None) -> dict:
        return storage.workbench(TODAY, since=since)

    def test_full_response_carries_a_version(self) -> None:
        board = self.version()
        self.assertTrue(board["version"])
        self.assertNotIn("unchanged", board)
        self.assertEqual(group_texts(board, "today"), ["今天到期"])

    def test_unchanged_since_short_circuits(self) -> None:
        version = self.version()["version"]
        board = self.version(since=version)
        self.assertTrue(board.get("unchanged"))
        self.assertEqual(board["version"], version)
        self.assertEqual(board["totals"], {"overdue": 0, "today": 0, "next7": 0,
                                           "reviewToday": 0, "inbox": 0})
        self.assertEqual({key: board["groups"][key] for key in board["groups"]},
                         {key: [] for key in board["groups"]})

    def test_node_change_invalidates(self) -> None:
        version = self.version()["version"]
        live, revision = storage.read_project("p1")
        live["tree"][0]["children"][0]["children"].append(
            item_node("i2", "新加的任务", due=TODAY))
        storage.write_project(live, revision)
        board = self.version(since=version)
        self.assertNotIn("unchanged", board)
        self.assertNotEqual(board["version"], version)
        self.assertEqual(group_texts(board, "today"), ["今天到期", "新加的任务"])

    def test_completing_a_task_invalidates(self) -> None:
        version = self.version()["version"]
        live, revision = storage.read_project("p1")
        live["tree"][0]["children"][0]["children"][0]["completed"] = True
        live["tree"][0]["children"][0]["children"][0]["completedAt"] = f"{TODAY}T10:00:00"
        storage.write_project(live, revision)
        board = self.version(since=version)
        self.assertNotIn("unchanged", board)
        self.assertEqual(board["totals"]["today"], 0)

    def test_archive_and_delete_invalidate(self) -> None:
        version = self.version()["version"]
        live, revision = storage.read_project("p1")
        live["archived"] = True          # 归档走整树保存（和前端"归档"按钮同一条路）
        storage.write_project(live, revision)
        archived_board = self.version(since=version)
        self.assertNotIn("unchanged", archived_board)
        self.assertEqual(archived_board["totals"]["today"], 0)

        version = archived_board["version"]
        storage.write_project(project("p2", [item_node("k1", "另一个今天到期", due=TODAY)]), None)
        added = self.version(since=version)
        self.assertNotIn("unchanged", added)
        self.assertEqual(group_texts(added, "today"), ["另一个今天到期"])

        version = added["version"]
        storage.delete_project("p2", storage.read_project("p2")[1])
        deleted = self.version(since=version)
        self.assertNotIn("unchanged", deleted)
        self.assertEqual(deleted["totals"]["today"], 0)

    def test_bogus_since_returns_full_result(self) -> None:
        board = self.version(since="0:0:0:0:0:0")
        self.assertNotIn("unchanged", board)
        self.assertEqual(board["totals"]["today"], 1)


class ReviewQueueAndSearchPathTests(unittest.TestCase):
    def setUp(self) -> None:
        reset()
        storage.write_project(project("p1", [
            item_node("due", "要复习的任务", completed=True, review_due="2026-09-10"),
        ]), None)

    def test_review_queue_path_matches_reference(self) -> None:
        with storage.open_state_database() as connection:
            expected = reference_locations(connection)[("p1", "due")]
        queue = storage.list_review_queue(TODAY)
        self.assertEqual(len(queue["due"]), 1)
        self.assertEqual(queue["due"][0]["path"], expected["path"])
        self.assertEqual(queue["due"][0]["ancestorIds"], expected["ancestorIds"])

    def test_search_result_path_matches_reference(self) -> None:
        with storage.open_state_database() as connection:
            expected = reference_locations(connection)[("p1", "due")]
        found = storage.search_everything("要复习")
        self.assertEqual(len(found["results"]), 1)
        self.assertEqual(found["results"][0]["detail"], expected["path"])
        self.assertEqual(found["results"][0]["ancestorIds"], expected["ancestorIds"])

    def test_search_on_container_lists_descendants_with_paths(self) -> None:
        found = storage.search_everything("第1周")
        # 命中周本身，也连带它的后代
        self.assertEqual({row["label"] for row in found["results"]}, {"第1周", "单元1", "要复习的任务"})
        item = next(row for row in found["results"] if row["label"] == "要复习的任务")
        self.assertEqual(item["detail"], "第1周 / 单元1")
        self.assertEqual(item["ancestorIds"], ["p1-w1", "p1-d1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
