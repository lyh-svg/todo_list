"""AI 层测试：JSON 解析、流式解析、超时/取消/错误响应、mock 与规模上限。

全部离线：真实网络路径用假的 urlopen 替换（不发出任何请求），
DEEPSEEK_API_KEY 用环境变量注入（read_settings 环境变量优先于 deepseek.env）。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import ai_service  # noqa: E402

FENCE = chr(96) * 3


def payload(**overrides) -> dict:
    base = {
        "model": "flash",
        "task": "解释闭包为什么能记住外层变量",
        "answer": "因为函数对象保存了定义时的作用域引用。",
        "stage": "questions",
        "questions": ["闭包捕获的是变量还是值？"],
        "context": {"project": "Python", "week": "第2周", "unit": "单元1"},
    }
    base.update(overrides)
    return base


class FakeResponse:
    """模拟 urlopen 返回的响应：可迭代（SSE 行）、可关闭（取消时验证是否关闭）。"""

    def __init__(self, lines: list[bytes], *, fail_after: int | None = None,
                 error: Exception | None = None):
        self.lines = lines
        self.fail_after = fail_after
        self.error = error
        self.closed = False
        self.yielded = 0

    def __iter__(self):
        for index, line in enumerate(self.lines):
            if self.fail_after is not None and index >= self.fail_after:
                raise self.error or TimeoutError("timed out")
            self.yielded += 1
            yield line

    def read(self) -> bytes:
        if self.error is not None:
            raise self.error
        return b"".join(self.lines)

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> bool:
        self.close()
        return False


def sse(*contents: str) -> list[bytes]:
    """把若干段模型输出拼成 DeepSeek 风格的 SSE 行。"""
    lines = []
    for content in contents:
        body = {"choices": [{"delta": {"content": content}}]}
        lines.append(("data: " + json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8"))
    lines.append(b"data: [DONE]\n")
    return lines


def collect(generator) -> list[dict]:
    return list(generator)


class ParseJsonObjectTests(unittest.TestCase):
    def test_plain_object(self) -> None:
        self.assertEqual(ai_service.parse_json_object('{"passed": true}'), {"passed": True})

    def test_fenced_object(self) -> None:
        text = f'{FENCE}json\n{{"score": 90}}\n{FENCE}'
        self.assertEqual(ai_service.parse_json_object(text), {"score": 90})
        self.assertEqual(ai_service.parse_json_object(f'{FENCE}\n{{"a": 1}}\n{FENCE}'), {"a": 1})

    def test_object_embedded_in_prose(self) -> None:
        """模型很爱在 JSON 前后加解释文字：必须能抠出来。"""
        text = '好的，我的评估如下：\n{"passed": true, "score": 88}\n希望有帮助！'
        self.assertEqual(ai_service.parse_json_object(text), {"passed": True, "score": 88})

    def test_nested_braces_inside_strings_do_not_confuse_it(self) -> None:
        text = '说明 {"reply": "用 { 和 } 举例", "score": 80}'
        self.assertEqual(ai_service.parse_json_object(text)["reply"], "用 { 和 } 举例")

    def test_invalid_inputs_raise_value_error(self) -> None:
        for bad in ("", "   ", "没有大括号", "{不完整", "{'单引号': 1}", '{{"a": 1}}'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ai_service.parse_json_object(bad)

    def test_non_object_json_is_rejected(self) -> None:
        for bad in ("[1, 2]", '"字符串"', "42", "null", f"{FENCE}json\n[1,2]\n{FENCE}"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as ctx:
                    ai_service.parse_json_object(bad)
                self.assertIn("不是 JSON 对象", str(ctx.exception))


class ReplyScannerTests(unittest.TestCase):
    def scan(self, chunks: list[str]) -> str:
        scanner = ai_service.ReplyScanner()
        return "".join(scanner.push(chunk) for chunk in chunks)

    def test_extracts_reply_from_single_chunk(self) -> None:
        text = json.dumps({"reply": "讲得很清楚", "score": 90}, ensure_ascii=False)
        self.assertEqual(self.scan([text]), "讲得很清楚")

    def test_reassembles_reply_split_across_chunks(self) -> None:
        text = json.dumps({"passed": True, "reply": "第一句。第二句！", "score": 91}, ensure_ascii=False)
        # 逐字符推送是最坏情况：任何位置都可能被切断
        self.assertEqual(self.scan(list(text)), "第一句。第二句！")

    def test_key_itself_split_across_chunks(self) -> None:
        self.assertEqual(self.scan(['{"rep', 'ly": "ok"}']), "ok")

    def test_escapes_are_decoded(self) -> None:
        text = '{"reply": "换行\\n引号\\"制表\\t中文\\u4e2d文"}'
        self.assertEqual(self.scan([text]), '换行\n引号"制表\t中文中文')
        # 转义序列被切断
        self.assertEqual(self.scan(['{"reply": "a\\', 'n\\u4e', '2db"}']), "a\n中b")

    def test_only_first_reply_key_is_used(self) -> None:
        text = '{"reply": "第一", "note": {"reply": "第二"}}'
        self.assertEqual(self.scan([text]), "第一")

    def test_nested_object_before_reply(self) -> None:
        self.assertEqual(self.scan(['{"meta": {"a": 1, "b": [1, 2]}, "reply": "值"}']), "值")

    def test_stream_stops_after_closing_quote(self) -> None:
        scanner = ai_service.ReplyScanner()
        first = scanner.push('{"reply": "完整值"')
        self.assertEqual(first, "完整值")
        # 结束引号之后的内容不再进入 reply
        self.assertEqual(scanner.push(', "reply": "第二个"}'), "")

    def test_no_reply_key_returns_empty(self) -> None:
        scanner = ai_service.ReplyScanner()
        self.assertEqual(scanner.push('{"passed": true}'), "")
        self.assertEqual(scanner.value, "")

    def test_unicode_escape_split_after_backslash_u(self) -> None:
        scanner = ai_service.ReplyScanner()
        scanner.push('{"reply": "\\u')
        self.assertEqual(scanner.push("4e2d"), "中")


class AiValidationTests(unittest.TestCase):
    """参数校验必须发生在发请求之前（否则会白等一次网络往返）。"""

    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key",
                                                "TODO_AI_MOCK": "1"}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_missing_api_key_is_reported(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
            with self.assertRaises(RuntimeError) as ctx:
                collect(ai_service.call_deepseek_stream(payload()))
            self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))

    def test_unknown_model_alias(self) -> None:
        with self.assertRaises(ValueError):
            collect(ai_service.call_deepseek_stream(payload(model="gpt-9")))

    def test_stage_questions_accepts_exactly_one_question(self) -> None:
        with self.assertRaises(ValueError):
            collect(ai_service.call_deepseek_stream(payload(questions=[])))
        with self.assertRaises(ValueError):
            collect(ai_service.call_deepseek_stream(payload(questions=["a", "b"])))

    def test_stage_implementation_needs_answer_or_files(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            collect(ai_service.call_deepseek_stream(payload(stage="implementation", answer="", files=[])))
        self.assertIn("代码文件", str(ctx.exception))

    def test_unknown_stage(self) -> None:
        with self.assertRaises(ValueError):
            collect(ai_service.call_deepseek_stream(payload(stage="敲定")))

    def test_empty_task_or_answer(self) -> None:
        with self.assertRaises(ValueError):
            collect(ai_service.call_deepseek_stream(payload(task="   ")))
        with self.assertRaises(ValueError):
            collect(ai_service.call_deepseek_stream(payload(answer="   ")))

    def test_non_dict_payload_fields_are_tolerated(self) -> None:
        """context/conversation/files 传错类型不能崩，按空处理。"""
        events = collect(ai_service.call_deepseek_stream(payload(context="不是字典", conversation="x", files=5)))
        self.assertEqual(events[-1]["type"], "result")


class MockStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key",
                                                "TODO_AI_MOCK": "1"}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_mock_stream_shape(self) -> None:
        events = collect(ai_service.call_deepseek_stream(payload()))
        self.assertEqual([event["type"] for event in events], ["text", "result"])
        self.assertTrue(events[0]["text"].startswith("通过"))
        result = events[1]["result"]
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 92)
        self.assertEqual(events[1]["humanText"], result["reply"])

    def test_mock_question_and_plan(self) -> None:
        questions = ai_service.call_question(payload())
        self.assertEqual(len(questions["questions"]), 3)
        plan = ai_service.plan_project("Rust 所有权")
        self.assertIn("Rust 所有权", plan["description"])
        self.assertGreaterEqual(len(plan["tree"]), 2)
        self.assertTrue(plan["tree"][0]["children"][0]["children"])

    def test_empty_topic_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ai_service.plan_project("   ")


class StreamParsingTests(unittest.TestCase):
    """用假的 urlopen 走真实 SSE 解析路径（不联网）。"""

    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key",
                                                "TODO_AI_MOCK": ""}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_stream_reassembles_text_and_result(self) -> None:
        final = json.dumps({"passed": True, "score": 87, "reply": "思路完整，但少了失败路径。",
                            "summary": "不错", "strengths": ["因果清楚"], "problems": ["没有反例"],
                            "missingEvidence": [], "nextAction": "补一个反例。"}, ensure_ascii=False)
        chunks = ["先评估一下：\n", "REPLY_JSON_MARKER\n", final[:20], final[20:]]
        response = FakeResponse(sse(*chunks))
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=response):
            events = collect(ai_service.call_deepseek_stream(payload()))
        self.assertEqual(events[0]["type"], "text")
        self.assertTrue(events[0]["text"].startswith("思路完整"))
        self.assertEqual("".join(event["text"] for event in events if event["type"] == "text"),
                         "思路完整，但少了失败路径。")
        result = events[-1]["result"]
        self.assertEqual(result["score"], 87)
        self.assertEqual(result["strengths"], ["因果清楚"])
        self.assertFalse(result["passed"] is False and result["score"] < 80)

    def test_stream_uses_plain_json_when_marker_absent(self) -> None:
        final = json.dumps({"passed": False, "score": 40, "reply": "需要重做"}, ensure_ascii=False)
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=FakeResponse(sse(final))):
            events = collect(ai_service.call_deepseek_stream(payload()))
        self.assertEqual(events[-1]["result"]["score"], 40)
        self.assertFalse(events[-1]["result"]["passed"])

    def test_stream_ignores_broken_and_irrelevant_lines(self) -> None:
        final = json.dumps({"passed": True, "score": 85, "reply": "可以"}, ensure_ascii=False)
        lines = [b": keep-alive\n",
                 "data: 不是JSON\n".encode("utf-8"),
                 b'data: {"choices": []}\n',
                 b"data: " + json.dumps({"choices": [{"delta": {}}]}).encode() + b"\n"]
        lines += sse(final)
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=FakeResponse(lines)):
            events = collect(ai_service.call_deepseek_stream(payload()))
        self.assertEqual(events[-1]["result"]["score"], 85)

    def test_unparseable_stream_raises_readable_error(self) -> None:
        with mock.patch.object(ai_service.urllib.request, "urlopen",
                               return_value=FakeResponse(sse("我只想说：做得不错"))):
            with self.assertRaises(RuntimeError) as ctx:
                collect(ai_service.call_deepseek_stream(payload()))
        self.assertIn("可解析", str(ctx.exception))

    def test_http_error_is_reported_with_status_and_body(self) -> None:
        error = urllib.error.HTTPError("http://x", 429, "Too Many Requests", {},
                                       __import__("io").BytesIO(b'{"error":"rate limit"}'))
        with mock.patch.object(ai_service.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as ctx:
                collect(ai_service.call_deepseek_stream(payload()))
        self.assertIn("429", str(ctx.exception))
        self.assertIn("rate limit", str(ctx.exception))

    def test_connection_error_is_reported(self) -> None:
        with mock.patch.object(ai_service.urllib.request, "urlopen",
                               side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaises(RuntimeError) as ctx:
                collect(ai_service.call_deepseek_stream(payload()))
        self.assertIn("无法连接", str(ctx.exception))

    def test_midstream_timeout_becomes_readable_error(self) -> None:
        """连接建立之后读超时不会被 urllib 包成 URLError，必须自己兜住。"""
        response = FakeResponse(sse("开始"), fail_after=0, error=TimeoutError("timed out"))
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(RuntimeError) as ctx:
                collect(ai_service.call_deepseek_stream(payload()))
        self.assertIn("超时", str(ctx.exception))
        self.assertTrue(response.closed, "异常路径也要关掉响应")

    def test_cancel_closes_the_upstream_response(self) -> None:
        """前端断开（生成器被 close）时，必须离开 with 块并关闭上游连接。"""
        response = FakeResponse(sse('{"reply": "第一段', '第二段", "passed": true, "score": 80}'))
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=response):
            generator = ai_service.call_deepseek_stream(payload())
            first = next(generator)
            self.assertEqual(first["type"], "text")
            generator.close()          # 等价于客户端断开、服务端不再消费
        self.assertTrue(response.closed, "取消后必须关闭上游响应")

    def test_timeout_is_passed_to_urlopen(self) -> None:
        response = FakeResponse(sse(json.dumps({"passed": True, "score": 80, "reply": "ok"})))
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=response) as fake:
            collect(ai_service.call_deepseek_stream(payload()))
        self.assertEqual(fake.call_args.kwargs.get("timeout"), 120, "必须显式设置超时")


class NonStreamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key",
                                                "TODO_AI_MOCK": ""}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def _upstream(self, content: str) -> FakeResponse:
        body = json.dumps({"choices": [{"message": {"content": content}}]}, ensure_ascii=False)
        return FakeResponse([body.encode("utf-8")])

    def test_call_deepseek_parses_fenced_json(self) -> None:
        content = f'{FENCE}json\n{json.dumps({"passed": True, "score": 95, "reply": "好"}, ensure_ascii=False)}\n{FENCE}'
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=self._upstream(content)):
            result = ai_service.call_deepseek(payload())
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 95)
        self.assertEqual(result["reply"], "好")

    def test_call_deepseek_rejects_unparseable_content(self) -> None:
        with mock.patch.object(ai_service.urllib.request, "urlopen",
                               return_value=self._upstream("我觉得你做得很好")):
            with self.assertRaises(ValueError):
                ai_service.call_deepseek(payload())

    def test_call_deepseek_reports_weird_upstream_shape(self) -> None:
        body = json.dumps({"choices": []}).encode("utf-8")
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=FakeResponse([body])):
            with self.assertRaises(RuntimeError) as ctx:
                ai_service.call_deepseek(payload())
        self.assertIn("响应格式", str(ctx.exception))

    def test_call_deepseek_midstream_timeout_is_readable(self) -> None:
        response = FakeResponse([], error=TimeoutError("read timed out"))
        with mock.patch.object(ai_service.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(RuntimeError) as ctx:
                ai_service.call_deepseek(payload())
        self.assertIn("超时", str(ctx.exception))


class ResultNormalizationTests(unittest.TestCase):
    def test_score_is_clamped_and_passed_needs_80(self) -> None:
        self.assertEqual(ai_service.normalize_result({"score": 999})["score"], 100)
        self.assertEqual(ai_service.normalize_result({"score": -5})["score"], 0)
        self.assertEqual(ai_service.normalize_result({"score": "88"})["score"], 88)
        self.assertEqual(ai_service.normalize_result({"score": "abc"})["score"], 0)
        self.assertFalse(ai_service.normalize_result({"passed": True, "score": 79})["passed"])
        self.assertTrue(ai_service.normalize_result({"passed": True, "score": 80})["passed"])
        self.assertFalse(ai_service.normalize_result({"passed": "true", "score": 95})["passed"],
                         "passed 必须是真正的布尔 true")

    def test_lists_are_capped_and_stringified(self) -> None:
        result = ai_service.normalize_result({"strengths": [1, 2, 3, 4, 5, 6, 7]})
        self.assertEqual(result["strengths"], ["1", "2", "3", "4", "5"])
        self.assertGreaterEqual(len(ai_service.normalize_result({"strengths": "字符串"})["strengths"]), 0)
        self.assertEqual(ai_service.normalize_result({"problems": None})["problems"], [])

    def test_long_text_is_truncated(self) -> None:
        result = ai_service.normalize_result({"summary": "长" * 5000, "nextAction": "长" * 5000})
        self.assertEqual(len(result["summary"]), 1000)
        self.assertEqual(len(result["nextAction"]), 1000)


class PlanTreeSafetyTests(unittest.TestCase):
    """AI 返回的计划不能无限大，也不能带奇怪结构进数据库。"""

    def test_scale_caps(self) -> None:
        weeks = [{"text": f"第{i}周", "children": [
            {"text": f"单元{j}", "children": [{"text": f"任务{k}"} for k in range(20)]}
            for j in range(10)]} for i in range(30)]
        tree = ai_service._normalize_plan_tree(weeks)
        self.assertLessEqual(len(tree), 8)
        self.assertTrue(all(len(week["children"]) <= 6 for week in tree))
        self.assertTrue(all(len(day["children"]) <= 8 for day in tree[0]["children"]))

    def test_bad_shapes_are_dropped(self) -> None:
        tree = ai_service._normalize_plan_tree([
            "字符串", {}, {"text": "  "}, {"text": "第1周", "children": "不是列表"},
            {"text": "第2周", "children": [{"text": ""}, {"text": "单元1", "children": [{"text": ""}]},
                                           {"text": "单元2", "children": [{"text": "任务"}]}]},
        ])
        self.assertEqual([week["text"] for week in tree], ["第2周"])
        self.assertEqual([day["text"] for day in tree[0]["children"]], ["单元2"])
        self.assertIsNone(tree[0]["id"])
        self.assertEqual(tree[0]["children"][0]["children"][0]["type"], "item")

    def test_non_list_returns_empty(self) -> None:
        for bad in (None, "x", {}, 5):
            self.assertEqual(ai_service._normalize_plan_tree(bad), [])

    def test_long_text_is_truncated(self) -> None:
        tree = ai_service._normalize_plan_tree([{"text": "周" * 500, "children": [
            {"text": "单元" * 300, "children": [{"text": "任务" * 400}]}]}])
        self.assertEqual(len(tree[0]["text"]), 200)
        self.assertEqual(len(tree[0]["children"][0]["text"]), 200)
        self.assertEqual(len(tree[0]["children"][0]["children"][0]["text"]), 300)

    def test_optional_flag_becomes_bool(self) -> None:
        tree = ai_service._normalize_plan_tree([{"text": "周", "children": [
            {"text": "单元", "children": [{"text": "可选任务", "optional": "yes"},
                                          {"text": "必做任务"}]}]}])
        items = tree[0]["children"][0]["children"]
        self.assertTrue(items[0]["optional"])
        self.assertFalse(items[1]["optional"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
