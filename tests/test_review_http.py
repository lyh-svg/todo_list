"""复习接口的 HTTP 层测试（真起 ThreadingHTTPServer，只走 socket）。"""
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
_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-http-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import local_server  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"
CONTENT_PATH = APP_DIR / "content" / "review" / "py-week1.json"
MUTABLE_DEFAULT = "py.mutability.default-arg"


class _QuietHandler(local_server.TodoHandler):
    def log_message(self, *args) -> None:
        pass


class ReviewHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        storage.ensure_schema()
        review_storage.ensure_content_imported()
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


if __name__ == "__main__":
    unittest.main()
