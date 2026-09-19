"""复习接口的 HTTP 层测试（真起 ThreadingHTTPServer，只走 socket）。"""
import contextlib
import io
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
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-http-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import local_server  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"
MIN_POINTS = 40
CONTENT_PATH = APP_DIR / "content" / "review" / "py-week1.json"
MUTABLE_DEFAULT = "py.mutability.default-arg"
# 5 张复习表按主键排序（行序不定会让"内容一致"变成随机假阴性）。
REVIEW_TABLE_ORDER = {
    "review_points": "code",
    "review_point_tasks": "code,task_id,project_id",
    "review_states": "code",
    "review_attempts": "id",
    "review_sessions": "id",
}
# 导出/导入响应里 review 快照的键（与 storage.REVIEW_EXPORT_TABLES 一致）。
REVIEW_EXPORT_KEYS = ("points", "pointTasks", "states", "attempts", "sessions")


class _QuietHandler(local_server.TodoHandler):
    def log_message(self, *args) -> None:
        pass


class ReviewHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        storage.ensure_schema()
        review_storage.ensure_content_imported()
        # /api/import 拒绝空的 projects 列表（"没有可导入的项目"）。先保证库里至少有一个
        # 项目（真实的收集箱），否则导出的快照 projects 为空，导入用例根本走不到 review 分支。
        storage.ensure_inbox_project()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(APP_DIR)))
        cls.port = int(cls.server.server_address[1])
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, path: str, method: str = "GET", body: dict | None = None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=15)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"X-Todo-Session": local_server.SESSION_TOKEN}
        if payload:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        connection.close()
        if not raw and response.status < 400:
            self.fail(f"{path} 返回 {response.status} 但 body 为空")
        return response.status, json.loads(raw or "{}")

    def test_summary_and_queue(self) -> None:
        status, summary = self.call(f"/api/review/summary?today={TODAY}")
        self.assertEqual(status, 200)
        self.assertIn("dueToday", summary)
        status, queue = self.call(f"/api/review/queue?today={TODAY}&limit=5")
        self.assertEqual(status, 200)
        self.assertLessEqual(len(queue["items"]), 5)

    def test_queue_does_not_run_full_summary(self) -> None:
        """队列接口只为读 limit/newPerDay：不能再跑一遍完整 summary（P7）。

        /api/review/queue 与前端并行请求的 /api/review/summary 以前把这套开销跑了两遍。
        """
        calls = []
        original = review_storage.summary

        def counted(today):
            calls.append(today)
            return original(today)

        review_storage.summary = counted
        try:
            status, queue = self.call(f"/api/review/queue?today={TODAY}&limit=5")
        finally:
            review_storage.summary = original
        self.assertEqual(status, 200)
        self.assertLessEqual(len(queue["items"]), 5)
        self.assertEqual(calls, [], "队列接口不该调用 summary()，只该读 _settings()")

        # 对照：summary 接口本身当然还是走完整统计
        status, payload = self.call(f"/api/review/summary?today={TODAY}")
        self.assertEqual(status, 200)
        self.assertIn("dueToday", payload)

    def test_queue_never_leaks_answers(self) -> None:
        status, queue = self.call(f"/api/review/queue?today={TODAY}&limit=5")
        self.assertEqual(status, 200)
        for item in queue["items"]:
            for key in (
                "answer",
                "expected",
                "explain",
                "rootCause",
                "fix",
                "acceptance",
                "reference",
            ):
                self.assertNotIn(key, item)

    def test_points_and_history(self) -> None:
        status, points = self.call("/api/review/points?limit=5")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(points["total"], 1)
        code = points["points"][0]["code"]
        status, history = self.call(f"/api/review/history?code={code}")
        self.assertEqual(status, 200)
        self.assertEqual(history["code"], code)

    def test_bad_params_are_400(self) -> None:
        self.assertEqual(self.call("/api/review/summary?today=not-a-date")[0], 400)
        self.assertEqual(self.call(f"/api/review/queue?today={TODAY}&limit=abc")[0], 400)
        self.assertEqual(self.call("/api/review/history")[0], 400)
        self.assertEqual(self.call("/api/review/history?code=py.nope.nope")[0], 404)

    def test_requires_session_token(self) -> None:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", f"/api/review/summary?today={TODAY}")
        self.assertEqual(connection.getresponse().status, 401)
        connection.close()
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", f"/api/review/queue?today={TODAY}&limit=5")
        self.assertEqual(connection.getresponse().status, 401)
        connection.close()


    def review_point_code(self) -> str:
        status, points = self.call("/api/review/points?limit=1")
        self.assertEqual(status, 200)
        return points["points"][0]["code"]

    def test_reveal_returns_answers_only_when_called(self) -> None:
        code = self.review_point_code()
        status, payload = self.call("/api/review/reveal", "POST", {"code": code, "type": "predict"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["expected"])
        self.assertTrue(payload["explain"])
        self.assertTrue(payload["pitfalls"])

    def test_answer_updates_schedule(self) -> None:
        code = self.review_point_code()
        status, payload = self.call("/api/review/answer", "POST", {
            "code": code, "type": "concept", "grade": 4, "answer": "我的回答",
            "durationMs": 1200, "sessionId": "", "today": TODAY})
        self.assertEqual(status, 200)
        self.assertEqual(payload["schedule"]["intervalDays"], 14)
        status, history = self.call(f"/api/review/history?code={code}")
        self.assertEqual(history["attempts"][0]["answer"], "我的回答")

    def test_answer_rejects_bad_grade(self) -> None:
        code = self.review_point_code()
        status, payload = self.call("/api/review/answer", "POST", {
            "code": code, "type": "concept", "grade": 9, "today": TODAY})
        self.assertEqual(status, 400)
        status, payload = self.call("/api/review/answer", "POST", {
            "code": code, "type": "concept", "grade": "abc", "today": TODAY})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "自评档位必须是 1~5")

    def test_session_lifecycle_over_http(self) -> None:
        status, started = self.call("/api/review/session", "POST", {"action": "start", "planned": 3})
        self.assertEqual(status, 200)
        session_id = started["sessionId"]
        status, payload = self.call("/api/review/session", "POST", {
            "action": "finish", "sessionId": session_id, "gradeCounts": ["3"]})
        self.assertEqual(status, 400)
        status, finished = self.call("/api/review/session", "POST", {
            "action": "finish", "sessionId": session_id, "answered": 2,
            "gradeCounts": {"3": 1, "4": 1}, "durationMs": 4000})
        self.assertEqual(status, 200)
        self.assertTrue(finished["ok"])

    def _content_point(self, code: str) -> dict:
        data = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
        return next(point for point in data["points"] if point["code"] == code)

    def test_reveal_predict_preserves_question_code(self) -> None:
        status, payload = self.call("/api/review/reveal", "POST",
                                   {"code": MUTABLE_DEFAULT, "type": "predict"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["pointCode"], MUTABLE_DEFAULT)
        self.assertEqual(payload["code"], self._content_point(MUTABLE_DEFAULT)["predict"]["code"])
        self.assertIn("def add(item, items=[])", payload["code"])

    def test_reveal_debug_preserves_question_code(self) -> None:
        status, payload = self.call("/api/review/reveal", "POST",
                                   {"code": MUTABLE_DEFAULT, "type": "debug"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["pointCode"], MUTABLE_DEFAULT)
        self.assertEqual(payload["code"], self._content_point(MUTABLE_DEFAULT)["debug"]["code"])
        self.assertIn("def cache(", payload["code"])

    def test_reveal_concept_has_no_question_code(self) -> None:
        status, payload = self.call("/api/review/reveal", "POST",
                                   {"code": MUTABLE_DEFAULT, "type": "concept"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["pointCode"], MUTABLE_DEFAULT)
        self.assertFalse(payload.get("code"))

    def test_finish_unknown_session_is_400(self) -> None:
        status, payload = self.call("/api/review/session", "POST", {
            "action": "finish", "sessionId": "nope", "answered": 1,
            "gradeCounts": {"3": 1}, "durationMs": 1000})
        self.assertEqual(status, 400)
        self.assertFalse(payload.get("ok"))

    def dump_review_tables(self) -> dict[str, list[tuple]]:
        with storage.open_state_database() as connection:
            return {
                table: [tuple(row) for row in
                        connection.execute(f"SELECT * FROM {table} ORDER BY {order}")]
                for table, order in REVIEW_TABLE_ORDER.items()
            }

    def test_import_consumes_review_snapshot(self) -> None:
        """规格 §10.7：导出（带 review）→ 清空复习表（新库）→ 同一份 payload 导入 → 内容一致。

        没有这一步时，用户拿"导出 JSON → 导入"做跨机迁移会静默丢复习进度与作答历史。
        """
        code = self.review_point_code()
        self.call("/api/review/answer", "POST", {
            "code": code, "type": "concept", "grade": 3, "answer": "迁移前的作答",
            "durationMs": 900, "sessionId": "", "today": TODAY})
        started = self.call("/api/review/session", "POST", {"action": "start", "planned": 2})[1]
        self.call("/api/review/session", "POST", {
            "action": "finish", "sessionId": started["sessionId"], "answered": 1,
            "gradeCounts": {"3": 1}, "durationMs": 1500})
        before = self.dump_review_tables()
        self.assertGreater(len(before["review_points"]), 0)
        self.assertGreater(len(before["review_attempts"]), 0)
        self.assertGreater(len(before["review_sessions"]), 0)

        snapshot = storage.export_projects_snapshot()
        self.assertIn("review", snapshot, "导出必须附带 5 张复习表快照")
        self.assertEqual(len(snapshot["review"]["points"]), len(before["review_points"]))
        self.assertEqual(len(snapshot["review"]["attempts"]), len(before["review_attempts"]))
        # 导出键是 camelCase、JSON 列已解析成对象（导入侧要写回 content_json / grade_counts_json）。
        self.assertIsInstance(snapshot["review"]["points"][0]["content"], dict)
        self.assertIsInstance(snapshot["review"]["sessions"][0]["gradeCounts"], dict)

        # 清空 5 张复习表：模拟"换台机器 / 新库"。
        with storage.open_state_database() as connection:
            for table in REVIEW_TABLE_ORDER:
                connection.execute(f"DELETE FROM {table}")
        self.assertTrue(all(not rows for rows in self.dump_review_tables().values()),
                        "清空后复习表应为空")

        status, result = self.call("/api/import", "POST", {
            "projects": snapshot["projects"], "mode": "merge", "review": snapshot["review"]})
        self.assertEqual(status, 200)
        self.assertEqual(result["review"]["points"], len(snapshot["review"]["points"]))
        self.assertEqual(result["review"]["attempts"], len(snapshot["review"]["attempts"]))
        self.assertEqual(self.dump_review_tables(), before,
                         "导入后 5 张复习表必须与导出前逐行一致")

    def test_import_without_review_key_is_backward_compatible(self) -> None:
        """旧快照没有 review 键：导入照常成功，且绝不能删掉本地已有的复习数据。"""
        before = self.dump_review_tables()
        snapshot = storage.export_projects_snapshot()
        status, result = self.call("/api/import", "POST", {
            "projects": snapshot["projects"], "mode": "merge"})
        self.assertEqual(status, 200)
        self.assertEqual(result["review"], {key: 0 for key in REVIEW_EXPORT_KEYS})
        self.assertEqual(self.dump_review_tables(), before,
                         "不含 review 的旧快照不能动现有复习表")

    def test_import_review_snapshot_only_adds_never_deletes(self) -> None:
        """规格 §10.7 的"只增不删"：导入不含本地行的 review 快照，本地行必须原样保留。

        合并导入的快照可能来自另一台机器（没有这台机器本地的知识点/作答）。若导入按
        "整表替换"实现，用户本地的复习进度与作答历史会被静默清空；同时快照里出现的行
        必须真的被写入/更新，而不是因为"只增"就整份忽略。
        """
        # 先留一份快照（此时还没有本地独有行）。
        snapshot = storage.export_projects_snapshot()
        self.assertTrue(snapshot["review"]["points"], "快照里应有知识点，否则用例失去意义")

        # 本地新增：一个快照里没有的知识点 + 一条作答。
        local_code = "py.local.extra"
        with storage.open_state_database() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO review_points "
                "(code,title,minutes,module,level,origin,content_json,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (local_code, "本地独有知识点", 5, "本地", "基础", "local", "{}", TODAY, TODAY))
            connection.execute(
                "INSERT INTO review_attempts "
                "(id,code,task_id,project_id,question_type,grade,answer,ai_verdict,"
                "reviewed_on,duration_ms,session_id,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                ("local-attempt-1", local_code, "", "", "concept", 5, "本地独有作答",
                 "", TODAY, 700, "", TODAY))

        # 快照里出现的行要被 upsert：改一行标题，导入后库里必须变成新标题。
        updated = snapshot["review"]["points"][0]
        updated_code = str(updated["code"])
        updated["title"] = "被快照更新过的标题"

        status, result = self.call("/api/import", "POST", {
            "projects": snapshot["projects"], "mode": "merge",
            "review": snapshot["review"]})
        self.assertEqual(status, 200)
        self.assertGreater(result["review"]["points"], 0)

        after = self.dump_review_tables()
        self.assertIn(local_code, {row[0] for row in after["review_points"]},
                      "导入不能删掉快照里没有的本地知识点")
        self.assertIn("local-attempt-1", {row[0] for row in after["review_attempts"]},
                      "导入不能删掉快照里没有的本地作答")
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT title FROM review_points WHERE code=?", (updated_code,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "被快照更新过的标题",
                         "快照里出现的行必须被写入/更新")


class ReviewBootstrapTests(unittest.TestCase):
    """启动导入课程库：空库幂等播种；内容文件缺失/损坏不阻断启动（同一个临时库）。

    这些用例原在 tests/test_review_bootstrap.py，复审要求并入清单内文件。
    setUp 会清空知识点表，tearDown 负责恢复，避免影响同模块的 HTTP 用例。
    """

    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_point_tasks")

    def tearDown(self) -> None:
        review_storage.ensure_content_imported()

    def test_bootstrap_seeds_empty_database_and_is_idempotent(self) -> None:
        self.assertEqual(review_storage.list_points()["total"], 0)
        first = review_storage.ensure_review_content_ready()
        self.assertGreater(first, 0)
        total = review_storage.list_points()["total"]
        self.assertGreaterEqual(total, MIN_POINTS)
        second = review_storage.ensure_review_content_ready()
        self.assertEqual(second, 0)
        self.assertEqual(review_storage.list_points()["total"], total)

    def test_missing_content_file_warns_and_returns_none(self) -> None:
        missing = Path(_TEMP.name) / "no-such-content.json"
        warning = io.StringIO()
        with mock.patch.object(review_storage, "WEEK1_PATH", missing), \
                contextlib.redirect_stderr(warning):
            self.assertIsNone(review_storage.ensure_review_content_ready())
        # 内容缺失 ≠ 已是最新：必须留下明确告警。
        self.assertIn("内容文件不存在", warning.getvalue())
        self.assertIn(str(missing), warning.getvalue())

    def test_broken_content_file_is_skipped_and_others_still_import(self) -> None:
        """文件名匹配 glob 的损坏周文件被跳过，其它周照常导入，返回导入条数（不抛异常、不是 None）。

        旧用例把损坏文件命名成 broken-content.json，不匹配 `py-week*.json`，实际走的是"一个
        周文件都没有"分支、断言 None——用例绿却没覆盖它声称的"坏文件被跳过"路径。
        """
        with tempfile.TemporaryDirectory(prefix="todo-review-broken-") as work:
            broken = Path(work) / "py-week99.json"
            broken.write_bytes(b"{ not json")
            sample = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))["points"][0]
            good = Path(work) / "py-week1.json"
            good.write_text(json.dumps(
                {"schemaVersion": 1, "week": 1, "level": "基础", "points": [sample]},
                ensure_ascii=False), encoding="utf-8")
            warning = io.StringIO()
            with mock.patch.object(review_storage, "WEEK1_PATH", broken), \
                    contextlib.redirect_stderr(warning):
                imported = review_storage.ensure_review_content_ready()
        self.assertEqual(imported, 1, "返回的是其它周真正导入的条数，而不是 None")
        self.assertIn("py-week99.json", warning.getvalue())
        self.assertIn("跳过", warning.getvalue())
        self.assertIn(sample["code"],
                      {entry["code"] for entry in review_storage.list_points()["points"]})

    def test_main_wires_startup_bootstrap(self) -> None:
        source = (APP_DIR / "local_server.py").read_text(encoding="utf-8")
        main_body = source.split("def main() -> None:", 1)[1]
        self.assertIn("ensure_review_content_ready()", main_body)


if __name__ == "__main__":
    unittest.main()
