"""生成回流测试：完成任务按 taskRefs 生成复习项 + AI 补充 + 可选 AI 判分。

全部离线：AI 只走 TODO_AI_MOCK=1 的固定内容，或把 `_post_json` 换成假实现，
真实网络路径一次都不会被触发（DEEPSEEK_API_KEY 在用例里显式清空）。

运行：python3 -m unittest tests.test_review_generate -v
"""
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
_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-gen-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import ai_service  # noqa: E402
import local_server  # noqa: E402
import prompts  # noqa: E402
import review_content  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402

# 真实课程库里的那个点：Task 15 补 40 点之前也必须能被 taskRefs 找到。
REAL_POINT_CODE = "py.mutability.default-arg"
REAL_TASK_ID = "1103"
META_TASK_IDS = ("1104", "1504")


def point(code, task_id="", relation="introduces", *, project_id="", title="示例点",
          minutes=10, module="容器"):
    """一份自包含、能过 review_content.validate_points 的知识点。"""
    return {
        "code": code, "title": title, "minutes": minutes, "module": module, "level": "基础",
        "taskRefs": ([{"taskId": task_id, "projectId": project_id, "relation": relation}]
                     if task_id else []),
        "concept": {"prompt": "概念题", "answer": ["要点"]},
        "predict": {"prompt": "预测题", "code": "print(1)", "expected": ["1"], "explain": "因为"},
        "debug": {"prompt": "排查题", "code": "x =", "rootCause": "语法错误", "fix": "改成 x = 1"},
        "code_task": {"prompt": "编程题", "acceptance": ["能跑"], "reference": "def f(): return 1"},
        "pitfalls": ["易错点"],
    }


# 测试用知识点库：9202 同时有 introduces + exercises（验证排序），
# 1101 只有 exercises（验证"测试型任务也能回流"），另一个点同时挂 1104/1504（元任务）。
# 种子任务 id 用 9xxx 假号段：真实课程库（Task 15 的 40 点）会把知识点挂到
# 1202/1101/1103 等真实任务上，种子点若复用真实 id，points_for_task 会把内置点
# 一起返回，断言就变成依赖课程库内容而不是生成逻辑本身。
SEED_TASK_ID = "9202"
SEED_PROJECT_ID = "p-9202"
META_POINT = point("py.gen.meta", title="元任务点")
META_POINT["taskRefs"] = [
    {"taskId": "1104", "projectId": "", "relation": "introduces"},
    {"taskId": "1504", "projectId": "", "relation": "exercises"},
]
SEED_POINTS = [
    point("py.gen.intro", SEED_TASK_ID, "introduces", project_id=SEED_PROJECT_ID,
          title="9202 引入点"),
    point("py.gen.exercise", SEED_TASK_ID, "exercises", project_id=SEED_PROJECT_ID,
          title="9202 练习点"),
    point("py.gen.only-exercise", "1101", "exercises", title="1101 练习点"),
    META_POINT,
]


def reset_review_data() -> None:
    """清空复习数据后重新导入：真实课程库 + 本文件的测试知识点。"""
    storage.ensure_schema()
    with storage.open_state_database() as connection:
        for table in ("review_points", "review_point_tasks", "review_states"):
            connection.execute(f"DELETE FROM {table}")
    review_storage.ensure_content_imported()
    review_storage.import_content(SEED_POINTS)


class PointsForTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_review_data()

    def test_introduced_points_come_first(self) -> None:
        points = review_storage.points_for_task(SEED_TASK_ID)
        relations = [entry["relation"] for entry in points]
        self.assertEqual(sorted(set(relations)), ["exercises", "introduces"])
        first_exercise = relations.index("exercises")
        self.assertTrue(all(value == "introduces" for value in relations[:first_exercise]))
        self.assertTrue(all(value == "exercises" for value in relations[first_exercise:]))
        self.assertEqual([entry["code"] for entry in points], ["py.gen.intro", "py.gen.exercise"])

    def test_points_carry_display_fields(self) -> None:
        entry = {item["code"]: item for item in review_storage.points_for_task(SEED_TASK_ID)}["py.gen.intro"]
        self.assertEqual(entry["title"], "9202 引入点")
        self.assertEqual(entry["minutes"], 10)
        self.assertEqual(entry["module"], "容器")
        self.assertEqual(entry["level"], "基础")
        self.assertEqual(entry["relation"], "introduces")
        self.assertEqual(entry["projectId"], SEED_PROJECT_ID)

    def test_exercises_only_task_still_yields_points(self) -> None:
        points = review_storage.points_for_task("1101")
        self.assertTrue(points, "测试型任务必须能生成复习项（relation=exercises）")
        self.assertTrue(all(entry["relation"] == "exercises" for entry in points))

    def test_meta_tasks_yield_nothing(self) -> None:
        for task_id in META_TASK_IDS:
            self.assertEqual(review_storage.points_for_task(task_id), [],
                             f"元任务 {task_id} 不应产生复习项")

    def test_unknown_task_yields_nothing(self) -> None:
        self.assertEqual(review_storage.points_for_task("99999"), [])

    def test_blank_task_yields_nothing(self) -> None:
        self.assertEqual(review_storage.points_for_task("   "), [])

    def test_real_content_file_links_task_1103(self) -> None:
        codes = [entry["code"] for entry in review_storage.points_for_task(REAL_TASK_ID)]
        self.assertIn(REAL_POINT_CODE, codes)

    def test_enabling_task_without_refs_yields_nothing(self) -> None:
        review_storage.import_content([point("py.gen.ref-less")])
        self.assertEqual(review_storage.points_for_task("1313"), [])


class MarkWeakTests(unittest.TestCase):
    """验收失败标弱：只动已存在的 review_states 行，未知 code 忽略。"""

    def setUp(self) -> None:
        reset_review_data()

    def test_mark_weak_flags_existing_codes_and_ignores_unknown(self) -> None:
        self.assertFalse(review_storage.read_state("py.gen.intro")["weak"])
        affected = review_storage.mark_weak(["py.gen.intro", "py.gen.exercise", "py.gen.nope"])
        self.assertEqual(affected, 2)
        self.assertTrue(review_storage.read_state("py.gen.intro")["weak"])
        self.assertTrue(review_storage.read_state("py.gen.exercise")["weak"])
        self.assertIsNone(review_storage.read_state("py.gen.nope"))

    def test_mark_weak_without_codes_is_noop(self) -> None:
        self.assertEqual(review_storage.mark_weak([]), 0)
        self.assertEqual(review_storage.mark_weak(["   ", ""]), 0)

    def test_mark_weak_survives_one_grade3_and_clears_after_two_grade4(self) -> None:
        """验收失败标弱必须稳得住：一次 grade 3 抹不掉，连续两次 ≥4 才按既有规则清零。"""
        code = "py.gen.intro"
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_attempts WHERE code=?", (code,))
        review_storage.mark_weak([code])
        state = review_storage.read_state(code)
        self.assertTrue(state["weak"])
        self.assertGreaterEqual(state["lapses"], 2, "标弱同时要把 lapses 抬到薄弱阈值")

        review_storage.apply_grade(code, "concept", 3, today="2026-09-16")
        self.assertTrue(review_storage.read_state(code)["weak"],
                        "一次 grade 3 不能抹掉验收失败留下的薄弱标记")

        review_storage.apply_grade(code, "predict", 4, today="2026-09-17")
        self.assertTrue(review_storage.read_state(code)["weak"], "单次 grade 4 还不够")

        review_storage.apply_grade(code, "debug", 4, today="2026-09-18")
        state = review_storage.read_state(code)
        self.assertFalse(state["weak"], "连续两次 ≥4 才按既有规则清零")
        self.assertEqual(state["lapses"], 0)


class AiCodeNamespaceTests(unittest.TestCase):
    """AI 生成的 code 只能落在 py.ai. 命名空间，绝不能覆盖内置知识点。"""

    def test_normalize_points_drops_non_ai_codes(self) -> None:
        normalized = review_content.normalize_points([
            ai_draft(REAL_POINT_CODE), ai_draft("py.ai.1202.1")])
        self.assertEqual([point["code"] for point in normalized], ["py.ai.1202.1"])

    def test_generate_never_returns_builtin_code(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json",
                                   return_value={"points": [ai_draft(REAL_POINT_CODE)]}):
                generated = ai_service.generate_review_points(
                    task_id=REAL_TASK_ID, project_id="p-1", task_text="默认参数", count=3)
        self.assertEqual(generated, [], "模型返回内置 code 时必须被过滤，不能覆盖内置内容")

    def test_generate_drops_codes_that_belong_to_another_task(self) -> None:
        """模型返回 py.ai.<别的taskId>.<n> 时必须丢弃，否则会覆盖别的任务已有的 AI 点。"""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json",
                                   return_value={"points": [ai_draft(), ai_draft("py.ai.9999.1")]}):
                generated = ai_service.generate_review_points(
                    task_id="1301", project_id="p-2", task_text="闭包", count=3)
        self.assertEqual([entry["code"] for entry in generated], ["py.ai.1301.1"],
                         "别的任务的 code 必须被丢弃，只有当前任务的点能留下来")


def ai_draft(code=None):
    """AI 返回的原始草稿：缺 code/module/level/taskRefs，由生成侧补齐。"""
    draft = {
        "title": "AI 补充点", "minutes": 15,
        "concept": {"prompt": "解释机制", "answer": ["要点"]},
        "predict": {"prompt": "写出输出", "code": "print(1)", "expected": ["1"], "explain": "因为"},
        "debug": {"prompt": "找错", "code": "x =", "rootCause": "语法错误", "fix": "改成 x = 1"},
        "code_task": {"prompt": "写函数", "acceptance": ["能跑"], "reference": "def f(): return 1"},
        "pitfalls": ["边界输入"],
    }
    if code:
        draft["code"] = code
    return draft


class ReviewGenerateAiTests(unittest.TestCase):
    """AI 侧：无 key 判假；mock 模式返回可测固定内容；真实分支只被假 `_post_json` 驱动。"""

    def test_is_configured_false_without_key_or_mock(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": ""}, clear=False):
            self.assertFalse(ai_service.is_configured())

    def test_is_configured_true_in_mock_mode(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            self.assertTrue(ai_service.is_configured())

    def test_mock_generated_points_pass_content_gate_and_link_task(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            generated = ai_service.generate_review_points(
                task_id="1202", project_id="p-1202", task_text="可变默认参数", count=3)
        self.assertEqual(len(generated), 3)
        self.assertEqual(review_content.validate_points(generated), [])
        self.assertTrue(all(entry["code"].startswith("py.ai.1202.") for entry in generated))
        self.assertTrue(all(any(ref["taskId"] == "1202" and ref["relation"] == "exercises"
                                for ref in entry["taskRefs"]) for entry in generated))

    def test_mock_generate_count_is_clamped_to_1_3(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            self.assertEqual(len(ai_service.generate_review_points(
                task_id="1202", project_id="", task_text="x", count=9)), 3)
            self.assertEqual(len(ai_service.generate_review_points(
                task_id="1202", project_id="", task_text="x", count=0)), 1)
            self.assertEqual(len(ai_service.generate_review_points(
                task_id="1202", project_id="", task_text="x", count="bad")), 3)

    def test_real_branch_normalizes_and_links_task(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json",
                                   return_value={"points": [ai_draft()]}) as fake:
                generated = ai_service.generate_review_points(
                    task_id="1301", project_id="p-2", task_text="闭包", count=3)
        fake.assert_called_once()
        self.assertEqual([entry["code"] for entry in generated], ["py.ai.1301.1"])
        self.assertEqual(generated[0]["module"], "AI 补充")
        self.assertEqual(generated[0]["level"], "基础")
        self.assertEqual(review_content.validate_points(generated), [])
        self.assertIn({"taskId": "1301", "projectId": "p-2", "relation": "exercises"},
                      generated[0]["taskRefs"])

    def test_real_branch_failure_returns_empty_without_network(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json",
                                   side_effect=RuntimeError("DeepSeek API 返回 429")):
                self.assertEqual(ai_service.generate_review_points(
                    task_id="1301", project_id="", task_text="闭包"), [])

    def test_real_branch_cannot_leak_unparseable_points(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json",
                                   return_value={"points": ["不是对象", {"minutes": 15}]}):
                self.assertEqual(ai_service.generate_review_points(
                    task_id="1301", project_id="", task_text="闭包"), [])

    def test_mock_grade_returns_verdict_shape(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            verdict = ai_service.grade_review_answer(
                code=REAL_POINT_CODE, question_type="concept", answer="函数定义时求值一次",
                reference={"prompt": "默认参数什么时候求值？"})
        self.assertEqual(set(verdict), {"correct", "missing", "wrongAt", "hint"})
        self.assertTrue(verdict["correct"])
        self.assertEqual(verdict["missing"], [])

    def test_grade_failure_returns_empty_dict(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json", side_effect=TimeoutError("timed out")):
                self.assertEqual(ai_service.grade_review_answer(
                    code=REAL_POINT_CODE, question_type="concept", answer="x", reference={}), {})

    def test_mock_remedial_points_use_remedial_namespace(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            generated = ai_service.generate_review_points(
                task_id="1202", project_id="p-1202", task_text="可变默认参数",
                count=2, remedial=True, gap="把自由变量说成全局变量")
        self.assertEqual([entry["code"] for entry in generated],
                         ["py.ai.1202.remedial.1", "py.ai.1202.remedial.2"])
        self.assertEqual(review_content.validate_points(generated), [])
        for entry in generated:
            self.assertTrue(all(kind in entry for kind in review_content.QUESTION_TYPES))
            self.assertTrue(any(ref["taskId"] == "1202" and ref["relation"] == "exercises"
                                for ref in entry["taskRefs"]))
        self.assertIn("自由变量", generated[0]["title"])

    def test_real_remedial_branch_uses_remedial_prompt_and_gap(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json",
                                   return_value={"points": [ai_draft()]}) as fake:
                generated = ai_service.generate_review_points(
                    task_id="1301", project_id="p-2", task_text="闭包",
                    count=2, remedial=True, gap="答非所问：没讲清自由变量绑定")
        fake.assert_called_once()
        body = fake.call_args.args[1]
        self.assertEqual(body["messages"][0]["content"], prompts.REVIEW_REMEDIAL_PROMPT)
        self.assertNotEqual(prompts.REVIEW_REMEDIAL_PROMPT, prompts.REVIEW_POINTS_PROMPT)
        self.assertIn("自由变量", body["messages"][1]["content"])
        self.assertEqual([entry["code"] for entry in generated], ["py.ai.1301.remedial.1"])
        self.assertEqual(review_content.validate_points(generated), [])


class _QuietHandler(local_server.TodoHandler):
    def log_message(self, *args) -> None:
        pass


class ReviewGenerateHttpTests(unittest.TestCase):
    """接口层：无 key 只回预规划点 / ai-grade 503 / mock 模式返回固定内容。"""

    @classmethod
    def setUpClass(cls) -> None:
        storage.ensure_schema()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(APP_DIR)))
        cls.port = int(cls.server.server_address[1])
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        reset_review_data()

    def call(self, path: str, body: dict):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=15)
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        connection.request("POST", path, body=payload,
                           headers={"X-Todo-Session": local_server.SESSION_TOKEN,
                                    "Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        connection.close()
        return response.status, json.loads(raw or "{}")

    def stored_ai_codes(self, task_id: str) -> list[str]:
        with storage.open_state_database() as connection:
            rows = connection.execute(
                "SELECT code FROM review_points WHERE code LIKE ?",
                (f"py.ai.{task_id}.%",)).fetchall()
        return [row["code"] for row in rows]

    def test_generate_without_ai_returns_preplanned_points(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": ""}, clear=False):
            status, payload = self.call("/api/review/generate", {"taskId": SEED_TASK_ID,
                                                                 "projectId": SEED_PROJECT_ID})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["usedAi"])
        self.assertEqual(payload["inserted"], 0, "已存在的预规划点不能算新增")
        self.assertEqual([entry["code"] for entry in payload["created"]],
                         ["py.gen.intro", "py.gen.exercise"])
        self.assertTrue(all("origin" not in entry for entry in payload["created"]))

    def test_generate_mock_fills_gap_and_persists_task_link(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            status, payload = self.call("/api/review/generate",
                                        {"taskId": "88888", "projectId": "p-9",
                                         "taskText": "闭包", "count": 2})
        self.assertEqual(status, 200)
        self.assertTrue(payload["usedAi"])
        self.assertEqual(len(payload["created"]), 2)
        self.assertEqual(payload["inserted"], 2)
        self.assertEqual(payload["unchanged"], 0)
        self.assertTrue(all(entry["origin"] == "ai" for entry in payload["created"]))
        linked = {entry["code"] for entry in review_storage.points_for_task("88888")}
        self.assertEqual(linked, {entry["code"] for entry in payload["created"]})
        self.assertTrue(all(review_storage.read_state(code) is not None for code in linked))
        # 再次生成同一任务：没有新写入 → inserted 归零（前端据此静默，不再误报"已生成 N 个"）。
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            status, again = self.call("/api/review/generate",
                                      {"taskId": "88888", "projectId": "p-9",
                                       "taskText": "闭包", "count": 2})
        self.assertEqual(status, 200)
        self.assertEqual(again["inserted"], 0)
        self.assertTrue(again["created"])

    def test_generate_remedial_marks_weak_and_reports_inserted(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            status, payload = self.call("/api/review/generate",
                                        {"taskId": SEED_TASK_ID, "projectId": SEED_PROJECT_ID,
                                         "taskText": "可变默认参数", "count": 2,
                                         "gap": "说不清默认参数求值时机", "remedial": True})
        self.assertEqual(status, 200)
        self.assertTrue(payload["usedAi"])
        self.assertEqual(payload["inserted"], 2)
        remedial = [entry["code"] for entry in payload["created"]
                    if entry["code"].startswith(f"py.ai.{SEED_TASK_ID}.remedial.")]
        self.assertEqual(len(remedial), 2)
        # 该任务所有相关知识点（含预规划点）都要进薄弱点列表。
        for code in ("py.gen.intro", "py.gen.exercise", f"py.ai.{SEED_TASK_ID}.remedial.1"):
            self.assertTrue(review_storage.read_state(code)["weak"], code)

    def test_generate_remedial_repeat_is_unchanged_and_stays_weak(self) -> None:
        body = {"taskId": SEED_TASK_ID, "projectId": SEED_PROJECT_ID, "taskText": "可变默认参数",
                "count": 2, "gap": "说不清求值时机", "remedial": True}
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            first = self.call("/api/review/generate", body)[1]
            second = self.call("/api/review/generate", body)[1]
        self.assertEqual(first["inserted"], 2)
        self.assertEqual(second["inserted"], 0, "补漏题已存在时不能重复计为新增")
        self.assertEqual(second["unchanged"], 2)
        self.assertTrue(review_storage.read_state(f"py.ai.{SEED_TASK_ID}.remedial.1")["weak"])

    def test_generate_remedial_without_ai_still_marks_weak(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": ""}, clear=False):
            status, payload = self.call("/api/review/generate",
                                        {"taskId": SEED_TASK_ID, "projectId": SEED_PROJECT_ID,
                                         "taskText": "可变默认参数", "remedial": True,
                                         "gap": "没讲清机制"})
        self.assertEqual(status, 200)
        self.assertFalse(payload["usedAi"])
        self.assertEqual(payload["inserted"], 0)
        # 没有 AI 也把该任务已有的知识点标弱（补漏题本身退化为空，但薄弱点列表照常更新）。
        for code in ("py.gen.intro", "py.gen.exercise"):
            self.assertTrue(review_storage.read_state(code)["weak"], code)

    def test_generate_meta_task_returns_nothing_and_writes_nothing(self) -> None:
        """纯元任务（1104）不挂知识点：AI 可用也不能生成，更不能入库。"""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            status, payload = self.call("/api/review/generate",
                                        {"taskId": "1104", "projectId": "p-meta",
                                         "taskText": "纯元任务", "count": 3})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["inserted"], 0)
        self.assertEqual(payload["unchanged"], 0)
        self.assertEqual(payload["created"], [])
        self.assertFalse(payload["usedAi"])
        self.assertEqual(self.stored_ai_codes("1104"), [], "元任务不能留下任何 py.ai.1104.* 行")

    def test_generate_meta_task_remedial_cannot_bypass_gate(self) -> None:
        """remedial=true 也不能绕过元任务闸门。"""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            status, payload = self.call("/api/review/generate",
                                        {"taskId": "1504", "projectId": "p-meta",
                                         "taskText": "纯元任务", "remedial": True,
                                         "gap": "验收失败"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["inserted"], 0)
        self.assertEqual(payload["created"], [])
        self.assertFalse(payload["usedAi"])
        self.assertEqual(self.stored_ai_codes("1504"), [], "补漏分支也不能给元任务写入")

    def test_generate_ignores_ai_points_named_for_another_task(self) -> None:
        """接口层确证：模型给的别的任务 code 不会写进库。"""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "TODO_AI_MOCK": ""}, clear=False):
            with mock.patch.object(ai_service, "_post_json",
                                   return_value={"points": [ai_draft(), ai_draft("py.ai.9999.1")]}):
                status, payload = self.call("/api/review/generate",
                                            {"taskId": "88888", "projectId": "p-9",
                                             "taskText": "闭包", "count": 3})
        self.assertEqual(status, 200)
        self.assertEqual([entry["code"] for entry in payload["created"]], ["py.ai.88888.1"])
        self.assertEqual(payload["inserted"], 1)
        self.assertEqual(self.stored_ai_codes("9999"), [])

    def test_generate_missing_task_id_is_400(self) -> None:
        status, payload = self.call("/api/review/generate", {"projectId": "p-1"})
        self.assertEqual(status, 400)
        self.assertIn("taskId", payload["error"])

    def test_ai_grade_without_key_is_503_and_content_review_unaffected(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": ""}, clear=False):
            status, payload = self.call("/api/review/ai-grade",
                                        {"code": REAL_POINT_CODE, "type": "concept", "answer": "x"})
        self.assertEqual(status, 503)
        self.assertIn("未配置 AI", payload["error"])
        # 内置内容复习完全不依赖 AI：揭示答案与按 taskRefs 回流都照常可用。
        self.assertTrue(review_storage.reveal(REAL_POINT_CODE, "concept")["answer"])
        self.assertIn(REAL_POINT_CODE,
                      [entry["code"] for entry in review_storage.points_for_task(REAL_TASK_ID)])

    def test_ai_grade_mock_returns_verdict(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "TODO_AI_MOCK": "1"}, clear=False):
            status, payload = self.call("/api/review/ai-grade",
                                        {"code": REAL_POINT_CODE, "type": "concept",
                                         "answer": "函数定义时求值一次"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(set(payload["verdict"]), {"correct", "missing", "wrongAt", "hint"})
        self.assertTrue(payload["verdict"]["correct"])

    def test_ai_grade_bad_type_is_400(self) -> None:
        status, payload = self.call("/api/review/ai-grade",
                                    {"code": REAL_POINT_CODE, "type": "essay", "answer": "x"})
        self.assertEqual(status, 400)
        self.assertIn("题型", payload["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
