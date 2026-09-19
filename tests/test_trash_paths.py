"""P8 回归：回收站的存在性校验不该先全量列一遍。

旧实现里 restore / delete 各调 list_trash_items() **两次**（校验一次、响应一次），
而 list_trash_items() 自己就要：读设置 + 清理过期 + 读 trash 表 + 扫全 nodes 建 known_nodes。
50,220 节点 / 20 条回收站记录实测：单次 list 36.2 ms，restore 分支 77.8 ms、delete 分支 73.6 ms。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-trash-paths-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import local_server  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-19"

Base = storage._ManagedConnection


class CountingConnection(Base):
    statements: list[str] = []

    def execute(self, sql, *args, **kwargs):
        CountingConnection.statements.append(" ".join(str(sql).split()).upper())
        return super().execute(sql, *args, **kwargs)


class TrashItemIdsTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        storage.ensure_schema()
        storage.write_project({
            "id": "p1", "name": "项目", "description": "", "createdAt": TODAY,
            "assessmentEnabled": False, "tree": [{
                "id": "p1-w", "type": "week", "text": "第1周", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": [{
                    "id": "p1-d", "type": "day", "text": "单元1", "completed": False,
                    "expanded": False, "createdAt": TODAY, "children": [], }],
            }],
        }, None)
        self.kept = storage.store_trash_item("node", "p1", "保留的条目", {"id": "gone", "type": "item"})
        self.other = storage.store_trash_item("node", "p1", "另一条", {"id": "gone2", "type": "item"})
        storage.purge_trash_items(3650)   # 别让保留策略把测试数据清掉

    def test_ids_match_the_full_listing(self) -> None:
        listed = {entry["id"] for entry in storage.list_trash_items()}
        found = storage.trash_item_ids([self.kept["id"], self.other["id"], "不存在", ""])
        self.assertEqual(found, listed, "trash_item_ids 的口径必须与 list_trash_items 一致")
        self.assertNotIn("不存在", found)
        self.assertNotIn("", found)

    def test_single_lookup_uses_one_indexed_query(self) -> None:
        original = storage._ManagedConnection
        storage._ManagedConnection = CountingConnection
        CountingConnection.statements = []
        try:
            found = storage.trash_item_ids([self.kept["id"]])
        finally:
            storage._ManagedConnection = original
        self.assertEqual(found, {self.kept["id"]})
        selects = [sql for sql in CountingConnection.statements if sql.startswith("SELECT")]
        self.assertEqual(len(selects), 1, f"应该只查一次，实际 {selects}")
        self.assertIn("TRASH_ITEMS", selects[0])
        self.assertIn("WHERE TRASH_ID IN", selects[0])

    def test_empty_input_does_not_touch_the_database(self) -> None:
        original = storage._ManagedConnection
        storage._ManagedConnection = CountingConnection
        CountingConnection.statements = []
        try:
            self.assertEqual(storage.trash_item_ids([]), set())
            self.assertEqual(storage.trash_item_ids(None), set())
        finally:
            storage._ManagedConnection = original
        self.assertEqual(CountingConnection.statements, [], "空输入不该产生任何 SQL")


class _QuietHandler(local_server.TodoHandler):
    def log_message(self, *args) -> None:
        pass


class TrashRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        storage.ensure_schema()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(_QuietHandler, directory=str(APP_DIR)))
        cls.port = int(cls.server.server_address[1])
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        storage.replace_projects([], pre_backup=False)
        storage.clear_trash_items()
        # 恢复要有"原项目"才走得通（项目不存在时服务端会以 400 拒绝）
        storage.write_project({
            "id": "p1", "name": "项目", "description": "", "createdAt": TODAY,
            "assessmentEnabled": False, "tree": [{
                "id": "p1-w", "type": "week", "text": "第1周", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": [{
                    "id": "p1-d", "type": "day", "text": "单元1", "completed": False,
                    "expanded": False, "createdAt": TODAY, "children": [], }],
            }],
        }, None)
        self.item = storage.store_trash_item("node", "p1", "待恢复", {"id": "gone", "type": "item"})

    def call(self, body: dict):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=15)
        payload = json.dumps(body).encode("utf-8")
        connection.request("POST", "/api/trash", body=payload,
                           headers={"X-Todo-Session": local_server.SESSION_TOKEN,
                                    "Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        connection.close()
        return response.status, json.loads(raw or "{}")

    def count_listings(self):
        """把 local_server 里的 list_trash_items 换成计数器（handler 用的是顶部的别名）。"""
        original = local_server.list_trash_items
        calls = []

        def counted():
            calls.append(1)
            return original()

        local_server.list_trash_items = counted
        self.addCleanup(lambda: setattr(local_server, "list_trash_items", original))
        return calls

    def test_restore_lists_items_only_for_the_response(self) -> None:
        calls = self.count_listings()
        status, payload = self.call({"action": "restore", "id": self.item["id"]})
        self.assertEqual(status, 200)
        self.assertEqual(len(calls), 1, f"restore 应该只列一次（响应），实际 {len(calls)} 次")
        self.assertEqual(payload["items"], [], "恢复后回收站应为空")
        self.assertEqual(payload["item"]["id"], self.item["id"])

    def test_delete_lists_items_only_for_the_response(self) -> None:
        calls = self.count_listings()
        status, payload = self.call({"action": "delete", "id": self.item["id"]})
        self.assertEqual(status, 200)
        self.assertEqual(len(calls), 1, f"delete 应该只列一次（响应），实际 {len(calls)} 次")
        self.assertEqual(payload["items"], [])

    def test_unknown_id_is_404_without_listing(self) -> None:
        calls = self.count_listings()
        status, payload = self.call({"action": "restore", "id": "没有这个 id"})
        self.assertEqual(status, 404)
        self.assertIn("不存在", payload["error"])
        self.assertEqual(calls, [], "存在性校验不该靠全量列一遍")
        status, payload = self.call({"action": "delete", "id": "没有这个 id"})
        self.assertEqual(status, 404)
        self.assertEqual(calls, [])

    def test_batch_validation_does_not_list(self) -> None:
        calls = self.count_listings()
        status, payload = self.call({"action": "restore-many", "ids": [self.item["id"], "不存在"]})
        self.assertEqual(status, 404)
        self.assertIn("已不在回收站", payload["error"])
        self.assertEqual(calls, [], "批量校验不该全量列一遍")

        calls.clear()
        status, payload = self.call({"action": "delete-many", "ids": [self.item["id"]]})
        self.assertEqual(status, 200)
        self.assertEqual(len(calls), 1, "批量删除的响应列一次就够")
        self.assertEqual(payload["items"], [])

    def test_store_still_returns_the_list_once(self) -> None:
        calls = self.count_listings()
        status, payload = self.call({"action": "store", "item": {
            "kind": "node", "projectId": "p1", "title": "新条目", "payload": {"id": "x", "type": "item"}}})
        self.assertEqual(status, 200)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(payload["items"]), 2, "setUp 里那条 + 刚存的这条")


if __name__ == "__main__":
    unittest.main(verbosity=2)
