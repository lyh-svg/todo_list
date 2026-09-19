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

import local_server  # noqa: E402
import memo_storage  # noqa: E402
import storage  # noqa: E402

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

    def test_review_counts_endpoint_is_lightweight(self) -> None:
        """勾选/复习之后只刷计数：轻量接口只回 byProject + totals，不夹带项目摘要（P6）。"""
        self.with_review_item()
        status, payload = self.json_call("GET", f"/api/review/counts?today={TODAY}")
        self.assertEqual(status, 200)
        # with_review_item() 排的复习日是 2026-09-10，比 TODAY(2026-09-15) 早 → 逾期
        self.assertEqual(payload["byProject"], {"p1": {"today": 0, "overdue": 1}})
        self.assertEqual(payload["totals"], {"today": 0, "overdue": 1})
        self.assertNotIn("projects", payload, "轻量接口不该带全部项目摘要")
        self.assertEqual(payload["usedToday"], TODAY)
        self.assertTrue(payload["serverToday"])

        # 把 today 挪到复习日当天 → 同一条复习算"今天"
        status, on_due = self.json_call("GET", "/api/review/counts?today=2026-09-10")
        self.assertEqual(on_due["byProject"], {"p1": {"today": 1, "overdue": 0}})
        self.assertEqual(on_due["totals"], {"today": 1, "overdue": 0})

        # 非法日期回落服务端日期，仍然必须是结构完整的 JSON（不能空回复）
        status, fallback = self.json_call("GET", "/api/review/counts?today=not-a-date")
        self.assertEqual(status, 200)
        self.assertIn("byProject", fallback)
        self.assertIn("totals", fallback)

    def test_workbench_since_short_circuits_unchanged_data(self) -> None:
        """提醒轮询靠 since 跳过"数据没变"的整次重算（P3）。"""
        status, board = self.json_call("GET", f"/api/workbench?today={TODAY}")
        self.assertEqual(status, 200)
        self.assertTrue(board["version"])
        self.assertNotIn("unchanged", board)

        status, same = self.json_call("GET", f"/api/workbench?today={TODAY}&since={board['version']}")
        self.assertEqual(status, 200)
        self.assertTrue(same.get("unchanged"))
        self.assertEqual(same["version"], board["version"])
        self.assertEqual(same["totals"], {key: 0 for key in board["totals"]})
        self.assertEqual(same["groups"], {key: [] for key in board["groups"]})

        # 数据真的变了：加一个今天到期的任务 → 必须回到完整结果，并给出新的 version
        project = make_project()
        project["tree"][0]["children"][0]["children"][0]["dueDate"] = TODAY
        storage.replace_projects([project], pre_backup=False)
        status, changed = self.json_call("GET", f"/api/workbench?today={TODAY}&since={board['version']}")
        self.assertEqual(status, 200)
        self.assertNotIn("unchanged", changed)
        self.assertNotEqual(changed["version"], board["version"])
        self.assertEqual([item["text"] for item in changed["groups"]["today"]], ["任务1"])

        # 乱传/超长 since 一律当没传：绝不能因此返回一个空工作台
        status, bogus = self.json_call("GET", f"/api/workbench?today={TODAY}&since={'x' * 500}")
        self.assertEqual(status, 200)
        self.assertNotIn("unchanged", bogus)
        self.assertEqual(len(bogus["groups"]["today"]), 1)

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

    def test_workbench_tolerates_corrupt_node_json(self) -> None:
        """B4：任务行的 tags/links/repeat 坏掉不能让整个工作台 500（一个坏任务拖垮所有项目）。"""
        with storage.open_state_database() as connection:
            connection.execute(
                "UPDATE nodes SET tags='{坏', links='[[[', repeat='daily', due_date=? WHERE node_id='p1-i'",
                (TODAY,))
        status, payload = self.json_call("GET", f"/api/workbench?today={TODAY}")
        self.assertEqual(status, 200)
        entries = [entry for entry in payload["groups"]["today"] if entry["nodeId"] == "p1-i"]
        self.assertEqual(len(entries), 1, "坏数据行不能从分组里消失")
        self.assertEqual(entries[0]["tags"], [])
        self.assertEqual(entries[0]["links"], [])
        self.assertIsNone(entries[0]["repeat"])

    def test_downloads_only_accept_header_token(self) -> None:
        """item 3：/api/export 与 /api/backup/download 只认请求头，token 不再进 URL。

        以前允许 ?token=（浏览器直接点链接带不了自定义头），代价是 token 留在浏览器历史
        和服务端日志里；前端已改成 fetch + Blob，所以查询串这条路要彻底关掉。
        """
        status, _ = self.call("GET", f"/api/export?token={local_server.SESSION_TOKEN}", token=False)
        self.assertEqual(status, 401, "查询串 token 不能再被接受")

        created = self.json_call("POST", "/api/backup",
                                 json.dumps({"action": "snapshot", "reason": "http-test"}).encode("utf-8"),
                                 {"Content-Type": "application/json"})
        self.assertEqual(created[0], 200)
        name = created[1]["name"]
        status, _ = self.call("GET",
                              f"/api/backup/download?name={name}&token={local_server.SESSION_TOKEN}",
                              token=False)
        self.assertEqual(status, 401, "查询串 token 不能再被接受")

        status, body = self.call("GET", "/api/export?format=json")
        self.assertEqual(status, 200)
        self.assertIn(b"schemaVersion", body)

        status, body = self.call("GET", f"/api/backup/download?name={name}")
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"PK"), "带请求头必须能正常下载 zip")

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

    def test_illegal_or_missing_backup_name_is_400(self) -> None:
        """备份名校验现在只走恢复动作：路径穿越与"不存在"都必须给 JSON 400，不能是空回复。"""
        for name in ("..%2Fetc%2Fpasswd.zip", "nope.zip"):
            with self.subTest(name=name):
                status, payload = self.post_json("/api/backup", {"action": "restore", "name": name})
                self.assertEqual(status, 400)
                self.assertIn("error", payload)

    # ---------- 请求体 ----------

    def test_truncated_body_is_rejected(self) -> None:
        """声明 1 MB 只发 10 字节就半关闭：半截请求体不能被当成完整 JSON 处理。"""
        request = (
            b"POST /api/project HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            + f"X-Todo-Session: {local_server.SESSION_TOKEN}\r\n".encode("utf-8")
            + b"Content-Length: 1048576\r\n\r\n" + b'{"project":'
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
        self.assertIsNotNone(storage.read_project("p1"), "半截请求体不能改动数据")

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

    def test_trash_list_supports_paging_and_total(self) -> None:
        for index in range(3):
            storage.store_trash_item("node", "p1", f"删除的条目 {index}",
                                     {"id": f"gone{index}", "type": "item"})
        status, payload = self.json_call("GET", "/api/trash?limit=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["total"], 3)
        status, second = self.json_call("GET", "/api/trash?limit=2&offset=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(second["items"]), 1)
        self.assertEqual(second["total"], 3)
        first_ids = {item["id"] for item in payload["items"]}
        second_ids = {item["id"] for item in second["items"]}
        self.assertEqual(first_ids & second_ids, set(), "两页不能重复")
        self.assertEqual(len(first_ids | second_ids), 3, "两页必须覆盖全部条目")
        status, bad = self.json_call("GET", "/api/trash?limit=abc")
        self.assertEqual(status, 400, "非法 limit 要 400，不能变成空回复")
        self.assertIn("error", bad)

    def test_oversized_post_gets_json_413(self) -> None:
        """声明超过上限的请求也必须拿到 JSON 413（而不是连接重置）。"""
        status, payload = self.call("POST", "/api/evaluate", b"{}", {
            "Content-Type": "application/json",
            "Content-Length": str(200 * 1024 * 1024),
        })
        self.assertEqual(status, 413)
        self.assertIn("请求内容", json.loads(payload.decode("utf-8"))["error"])

    def test_import_preview_accepts_payload_over_ai_limit(self) -> None:
        """预览必须和 /api/import 同档大限额（真 bug：预览曾落 5MiB 的 AI 限额分支）。

        大快照（projects + 导出的 review 附件）在预览上会 413，前端拿不到预览就禁用确认
        按钮，整条 UI 导入路径不可用。这里真发一个略大于 5MiB 的合法预览载荷。
        """
        project = make_project()
        project["tree"][0]["children"][0]["children"][0]["note"] = "a" * (6 * 1024 * 1024)
        raw = json.dumps({"projects": [project], "mode": "merge"}).encode("utf-8")
        self.assertGreater(len(raw), local_server.MAX_AI_REQUEST_BYTES)
        self.assertLess(len(raw), local_server.MAX_STATE_REQUEST_BYTES)
        status, payload = self.json_call("POST", "/api/import/preview", raw,
                                         {"Content-Type": "application/json"})
        self.assertNotEqual(status, 413, "预览不能再按 5MiB 的 AI 限额拒绝大快照")
        self.assertEqual(status, 200, payload)
        self.assertIn("preview", payload)

    def test_import_preview_still_rejects_over_state_limit(self) -> None:
        """放宽到 110MiB 不等于不设防：超过 STATE 限额仍必须 JSON 413。

        只声明 Content-Length、不真发 110MiB，避免测试链变慢。
        """
        status, payload = self.call("POST", "/api/import/preview", b"{}", {
            "Content-Type": "application/json",
            "Content-Length": str(local_server.MAX_STATE_REQUEST_BYTES + 1),
        })
        self.assertEqual(status, 413)
        self.assertIn("请求内容", json.loads(payload.decode("utf-8"))["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
