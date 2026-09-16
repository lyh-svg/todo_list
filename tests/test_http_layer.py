"""HTTP 层回归测试：真实起一个 ThreadingHTTPServer，只走 socket 发请求。

覆盖本轮审计发现的"空回复 / 状态码 / 请求体"问题：
- 坏数据行必须变成 JSON 500，而不是把异常抛到 HTTP 层（客户端看到连接直接断开）；
- 来源校验（GET/POST/DELETE）与 401/403 必须分开；
- 不存在的备份是 404 而不是 400；
- 声明了 Content-Length 却提前断开的请求体不能被当成完整数据；
- 备忘录的 HTTP 上限不能低于备忘录本身允许的大小。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.parse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-http-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))
os.environ.setdefault("TODO_SUMMARY_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "summary.sqlite3"))

import local_server  # noqa: E402
import memo_storage  # noqa: E402
import storage  # noqa: E402
import summary_storage  # noqa: E402

TODAY = "2026-09-15"


def make_project(project_id: str = "p1") -> dict:
    return {
        "id": project_id,
        "name": "HTTP 测试项目",
        "description": "",
        "createdAt": TODAY,
        "assessmentEnabled": False,
        "reviewEnabled": False,
        "tree": [{
            "id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": [{
                    "id": f"{project_id}-i", "type": "item", "text": "任务1", "completed": False,
                    "completedAt": None, "optional": False, "assessmentRequired": False,
                    "assessmentHistory": 0, "assessment": None, "createdAt": TODAY, "children": [],
                }],
            }],
        }],
    }


class _QuietHandler(local_server.TodoHandler):
    def log_message(self, *args) -> None:  # 测试输出保持干净
        pass


class HttpLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        storage.ensure_schema()
        memo_storage.initialize()
        summary_storage.initialize()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(_QuietHandler, directory=str(APP_DIR))
        )
        cls.port = int(cls.server.server_address[1])
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        storage.replace_projects([make_project()], pre_backup=False)

    # ---------- 工具 ----------

    def call(self, method: str, path: str, body: bytes | None = None,
             headers: dict | None = None, token: bool = True):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        sent = dict(headers or {})
        if token:
            sent["X-Todo-Session"] = local_server.SESSION_TOKEN
        try:
            connection.request(method, path, body=body, headers=sent)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def json_call(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        status, data = self.call(method, path, body, headers)
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.fail(f"{method} {path} 返回的不是 JSON（HTTP {status}）：{data[:200]!r}")
        return status, payload

    def post_json(self, path: str, payload: dict):
        return self.json_call("POST", path, json.dumps(payload).encode("utf-8"),
                              {"Content-Type": "application/json"})

    def with_review_item(self) -> None:
        """造一个"已完成 + 排了复习"的任务，用于复习队列接口测试。"""
        project = make_project()
        item = project["tree"][0]["children"][0]["children"][0]
        item["completed"] = True
        item["completedAt"] = TODAY
        item["review"] = {"due": "2026-09-10", "learning": True, "log": [{"at": TODAY, "result": "hard"}]}
        storage.replace_projects([project], pre_backup=False)

    def test_reviews_endpoint_splits_due_and_future(self) -> None:
        """跨项目复习队列由服务端算：前端不必再把所有项目的整棵树拉下来（第六批 item 3）。"""
        self.with_review_item()
        status, payload = self.json_call("GET", f"/api/reviews?today={TODAY}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["today"], TODAY)
        self.assertEqual([entry["nodeId"] for entry in payload["due"]], ["p1-i"])
        self.assertEqual(payload["due"][0]["path"], "第1周 / 单元1")
        self.assertEqual(payload["due"][0]["ancestorIds"], ["p1-w", "p1-d"])
        self.assertTrue(payload["due"][0]["learning"])
        self.assertEqual(payload["future"], [])
        # 未来到期 → 落到 future；更早的 today 参数 → 落到 due
        status, payload = self.json_call("GET", "/api/reviews?today=2026-09-01")
        self.assertEqual([entry["nodeId"] for entry in payload["future"]], ["p1-i"])
        self.assertEqual(payload["due"], [])

    def test_reviews_endpoint_limit_and_bad_params(self) -> None:
        self.with_review_item()
        status, payload = self.json_call("GET", f"/api/reviews?today={TODAY}&limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(payload["limit"], 1)
        status, payload = self.json_call("GET", f"/api/reviews?today={TODAY}&limit=abc")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_search_endpoint_matches_text_path_and_project(self) -> None:
        """服务端搜索：任务文本、分组路径（搜"第1周"能列出其中的任务）、项目名。"""
        status, payload = self.json_call("GET", "/api/search?q=" + urllib.parse.quote("任务1"))
        self.assertEqual(status, 200)
        nodes = [entry for entry in payload["results"] if entry["kind"] == "node"]
        self.assertEqual([entry["nodeId"] for entry in nodes], ["p1-i"])
        self.assertEqual(nodes[0]["detail"], "第1周 / 单元1")
        status, payload = self.json_call("GET", "/api/search?q=" + urllib.parse.quote("第1周"))
        ids = [entry["nodeId"] for entry in payload["results"] if entry["kind"] == "node"]
        self.assertEqual(ids, ["p1-d", "p1-i", "p1-w"],
                         "命中的分组自己算一条，同时连带它的后代（顺序固定：位置 + node_id）")
        status, payload = self.json_call("GET", "/api/search?q=" + urllib.parse.quote("HTTP 测试"))
        self.assertEqual([entry["kind"] for entry in payload["results"]], ["project"])
        status, payload = self.json_call("GET", "/api/search?q=")
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["total"], 0)

    def test_search_endpoint_rejects_overlong_query(self) -> None:
        status, payload = self.json_call("GET", "/api/search?q=" + "x" * 201)
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        status, payload = self.json_call("GET", "/api/search?q=abc&limit=abc")
        self.assertEqual(status, 400)

    def corrupt_project_row(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute("UPDATE projects SET id_json='{bad' WHERE project_id='p1'")

    # ---------- 坏数据不能变成空回复 ----------

    def test_storage_diagnostics_uses_sql_and_tolerates_corrupt_json(self) -> None:
        """诊断接口现在只做 SQL 汇总（不重建/解析项目），坏数据行不再让它 500。

        坏数据仍然会被真正读数据的接口抓到（下一个用例断言 /api/export 会 500、/api/project 会 400）。
        """
        self.corrupt_project_row()
        status, payload = self.json_call("GET", "/api/storage")
        self.assertEqual(status, 200)
        self.assertIn("nodeCount", payload)
        status, _ = self.json_call("GET", "/api/project?id=p1")
        self.assertEqual(status, 400, "真正读项目的接口仍然要报错")

    def test_export_reports_corrupt_row_as_json_500(self) -> None:
        self.corrupt_project_row()
        status, payload = self.json_call("GET", "/api/export")
        self.assertEqual(status, 500)
        self.assertIn("error", payload)

    def test_memo_database_download_reports_failure_as_json_500(self) -> None:
        original = None
        with sqlite3.connect(memo_storage.MEMO_DATABASE_FILE) as connection:
            original = int(connection.execute("PRAGMA user_version").fetchone()[0])
            connection.execute("PRAGMA user_version=99")
        try:
            status, payload = self.json_call("GET", "/api/memos/database-download")
            self.assertEqual(status, 500, "未来 schema 版本的备忘录库必须给出 JSON 500，而不是空回复")
            self.assertIn("error", payload)
        finally:
            with sqlite3.connect(memo_storage.MEMO_DATABASE_FILE) as connection:
                connection.execute(f"PRAGMA user_version={original}")

    # ---------- 来源校验 / 状态码 ----------

    def test_get_rejects_foreign_origin(self) -> None:
        status, payload = self.json_call("GET", "/api/projects", headers={"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        self.assertIn("来源", payload["error"])

    def test_delete_separates_401_from_403(self) -> None:
        status, _ = self.call("DELETE", "/api/project?id=p1&revision=1",
                              headers={"Origin": "http://evil.example"}, token=False)
        self.assertEqual(status, 401, "会话失效应该是 401")
        status, payload = self.json_call("DELETE", "/api/project?id=p1&revision=1",
                                         headers={"Origin": "http://evil.example"})
        self.assertEqual(status, 403, "来源不允许应该是 403，而不是 401")
        self.assertIn("来源", payload["error"])

    def test_missing_backup_is_404(self) -> None:
        status, payload = self.json_call("GET", "/api/backup/inspect?name=nope.zip")
        self.assertEqual(status, 404)
        self.assertIn("不存在", payload["error"])

    def test_illegal_backup_name_is_400(self) -> None:
        status, _ = self.json_call("GET", "/api/backup/inspect?name=..%2Fetc%2Fpasswd.zip")
        self.assertEqual(status, 400)

    # ---------- 请求体 ----------

    def test_truncated_background_upload_is_rejected(self) -> None:
        """声明 1 MB 只发 10 字节就半关闭：不能把半截数据当完整图片存起来。"""
        request = (
            b"POST /api/background?name=x.png&type=image/png HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            + f"X-Todo-Session: {local_server.SESSION_TOKEN}\r\n".encode("utf-8")
            + b"Content-Length: 1048576\r\n\r\n" + b"0123456789"
        )
        with socket.create_connection(("127.0.0.1", self.port), timeout=15) as sock:
            sock.sendall(request)
            sock.shutdown(socket.SHUT_WR)
            sock.settimeout(15)
            chunks = []
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
            except (socket.timeout, ConnectionResetError):
                pass
        raw = b"".join(chunks)
        self.assertIn(b"400", raw.split(b"\r\n", 1)[0] if raw else b"", "必须明确回 400")
        self.assertIsNone(storage.read_asset("background"), "半截请求体不能入库")

    def test_large_memo_is_accepted(self) -> None:
        """6 MB 的备忘录必须能存进去（旧上限 5 MB 会 413/断连）。"""
        content = "备" * (6 * 1024 * 1024)
        status, payload = self.post_json("/api/memo", {"title": "大备忘录", "content": content})
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["memo"]["title"], "大备忘录")

    def test_memo_list_supports_paging_and_total(self) -> None:
        for index in range(5):
            self.post_json("/api/memo", {"title": f"分页备忘 {index}", "content": "正文" * 10})
        status, payload = self.json_call("GET", "/api/memos?limit=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["memos"]), 2)
        self.assertGreaterEqual(payload["total"], 5)
        status, payload2 = self.json_call("GET", "/api/memos?limit=2&offset=2")
        self.assertNotEqual([m["id"] for m in payload["memos"]], [m["id"] for m in payload2["memos"]])
        status, bad = self.json_call("GET", "/api/memos?limit=abc")
        self.assertEqual(status, 400)
        self.assertIn("error", bad)

    def test_summary_list_paging_preview_and_detail(self) -> None:
        long_text = "很长的摘要" * 1000
        summary_storage = __import__("summary_storage")
        summary_storage.clear_summaries()   # 同一进程里别的用例可能留下摘要
        with summary_storage.open_summary_database() as connection:
            connection.execute(
                "INSERT INTO summaries(summary_id,question_key,question,content,created_at,updated_at,revision) "
                "VALUES(?,?,?,?,?,?,0)",
                ("s1", "k1", "题目一", long_text, "2026-09-16T00:00:00", "2026-09-16T00:00:00"))
            connection.execute(
                "INSERT INTO summaries(summary_id,question_key,question,content,created_at,updated_at,revision) "
                "VALUES(?,?,?,?,?,?,0)",
                ("s2", "k2", "题目二", "短摘要", "2026-09-16T00:00:00", "2026-09-16T00:00:00"))
        status, payload = self.json_call("GET", "/api/summaries?limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["summaries"]), 1)
        self.assertEqual(payload["total"], 2)
        item = payload["summaries"][0]
        self.assertLessEqual(len(item["content"]), 2000, "列表里的正文要截断")
        self.assertEqual(item["contentLength"], len(long_text))
        # 详情接口给完整正文
        status, detail = self.json_call("GET", f"/api/summary?id={item['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(len(detail["summary"]["content"]), len(long_text))
        status, missing = self.json_call("GET", "/api/summary?id=nope")
        self.assertEqual(status, 404)
        self.assertIn("error", missing)

    def test_oversized_post_gets_json_413(self) -> None:
        """声明超过上限的请求也必须拿到 JSON 413（而不是连接重置）。"""
        status, payload = self.call("POST", "/api/evaluate", b"{}", {
            "Content-Type": "application/json",
            "Content-Length": str(200 * 1024 * 1024),
        })
        self.assertEqual(status, 413)
        self.assertIn("请求内容", json.loads(payload.decode("utf-8"))["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
