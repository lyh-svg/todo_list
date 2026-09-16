"""DeepSeek configuration, question generation, and assessment calls."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import review_content
from prompts import (
    PROJECT_PLAN_PROMPT,
    QUESTION_PROMPT,
    REVIEW_GRADE_PROMPT,
    REVIEW_POINTS_PROMPT,
    REVIEW_REMEDIAL_PROMPT,
    SUMMARY_PROMPT,
    SYSTEM_PROMPT,
)

APP_DIR = Path(__file__).resolve().parent
MAX_CONVERSATION_MESSAGES = 12
STREAM_SUFFIX_PROMPT = chr(10).join([
    chr(39) + '请先直接输出一段给学习者的回复正文：像教练当面点评那样，先给结论，再说哪里差、具体怎么补，最后一句鼓励。允许分多段，并可使用 Markdown 排版：加粗、行内代码（用反引号包住）、以及用三反引号围起的代码块。' + chr(39),
    chr(39) + '正文结束后，另起一行单独输出一行：REPLY_JSON_MARKER' + chr(39),
    chr(39) + '随后只输出一个 JSON 对象（不要任何 Markdown 围栏）。JSON 字段与验收要求完全一致：passed、score、summary、reply、strengths、problems、missingEvidence、nextAction。其中 reply 给一句简短总结即可。' + chr(39),
])

MAX_CONVERSATION_MESSAGE_CHARS = 8000
CONFIG_FILE = Path(os.environ.get("TODO_AI_ENV_FILE", str(APP_DIR / "deepseek.env"))).expanduser()
CONFIG_KEYS = {
    "DEEPSEEK_API_KEY", "DEEPSEEK_API_URL", "DEEPSEEK_BASE_URL",
    "DEEPSEEK_FLASH_MODEL", "DEEPSEEK_PRO_MODEL",
}


def read_settings() -> dict[str, str]:
    """Read whitelisted settings without executing the config file as shell code."""
    file_values: dict[str, str] = {}
    try:
        for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, separator, value = line.partition("=")
            key = key.strip()
            if not separator or key not in CONFIG_KEYS:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            file_values[key] = value
    except FileNotFoundError:
        pass
    except OSError as error:
        print(f"Unable to read {CONFIG_FILE}: {error}", file=sys.stderr)

    return {
        key: os.environ.get(key, file_values.get(key, "")).strip()
        for key in CONFIG_KEYS
    }


def model_aliases(settings: dict[str, str]) -> dict[str, str]:
    return {
        "flash": settings.get("DEEPSEEK_FLASH_MODEL") or "deepseek-v4-flash",
        "pro": settings.get("DEEPSEEK_PRO_MODEL") or "deepseek-v4-pro",
    }


def api_url(settings: dict[str, str]) -> str:
    explicit = settings.get("DEEPSEEK_API_URL")
    if explicit:
        return explicit
    base = (settings.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    return f"{base}/chat/completions"


def parse_json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    fence = chr(96) * 3
    if value.startswith(fence):
        value = re.sub(r"^" + re.escape(fence) + r"(?:json)?\s*", "", value)
        value = re.sub(r"\s*" + re.escape(fence) + r"$", "", value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型没有返回有效 JSON") from None
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("模型返回结果不是 JSON 对象")
    return parsed


def string_list(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:500] for item in value[:limit]]


def normalize_conversation(value: Any) -> list[dict[str, str]]:
    """Keep only a small, plain-text history for the current question."""
    if not isinstance(value, list):
        return []
    conversation = []
    for item in value[-MAX_CONVERSATION_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "")).strip()[:MAX_CONVERSATION_MESSAGE_CHARS]
        if content:
            conversation.append({"role": role, "content": content})
    return conversation


def normalize_files(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    files = []
    for item in value[:10]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "未命名文件"))[:200]
        content = str(item.get("content", ""))[:120000]
        if name and content:
            files.append({"name": name, "content": content})
    return files


def files_text(files: list[dict[str, str]]) -> str:
    if not files:
        return "未上传代码文件"
    return "\n\n".join(f"--- {item['name']} ---\n{item['content']}" for item in files)


def normalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        score = int(float(raw.get("score", 0)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    passed = raw.get("passed") is True and score >= 80
    return {
        "passed": passed,
        "score": score,
        "summary": str(raw.get("summary", ""))[:1000],
        "strengths": string_list(raw.get("strengths")),
        "problems": string_list(raw.get("problems")),
        "missingEvidence": string_list(raw.get("missingEvidence")),
        "nextAction": str(raw.get("nextAction", ""))[:1000],
    }



def _mock_enabled() -> bool:
    return os.environ.get("TODO_AI_MOCK", "") == "1"


def mock_call_question(count: int = 3) -> dict[str, Any]:
    count = max(1, min(5, int(count)))
    questions = []
    for index in range(count):
        questions.append(
            "（模拟题%d）针对薄弱点出的练习题：解释/预测/排错并说明原因。" % (index + 1)
        )
    return {
        "questions": questions,
        "focus": "模拟：作用域与可变默认参数",
    }


def mock_call_deepseek() -> dict[str, Any]:
    return {
        "passed": True,
        "score": 92,
        "summary": "模拟验收通过：核心理解清晰。",
        "reply": "通过。你已经把关键机制讲清楚了，继续保持这种讲因果的答法。",
        "strengths": ["结论正确", "解释了机制"],
        "problems": [],
        "missingEvidence": [],
        "nextAction": "进入下一题或提交实现。",
    }


class ReplyScanner:
    """Incrementally extracts the value of the first top-level "reply" key."""

    def __init__(self) -> None:
        self.text = ""
        self.value = ""
        self.yielded = 0
        self.state = "seek_key"
        self.i = 0
        self.esc_hex = ""
        self._simple = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f"}

    def push(self, chunk: str) -> str:
        self.text += chunk
        self._run()
        visible = self.value[self.yielded:]
        self.yielded = len(self.value)
        return visible

    def _run(self) -> None:
        while True:
            if self.state == "seek_key":
                idx = self.text.find('"reply"', self.i)
                if idx < 0:
                    break
                self.i = idx + len('"reply"')
                self.state = "seek_colon"
                continue
            if self.state == "seek_colon":
                idx = self.text.find(":", self.i)
                if idx < 0:
                    break
                self.i = idx + 1
                self.state = "seek_quote"
                continue
            if self.state == "seek_quote":
                k = self.i
                while k < len(self.text) and self.text[k] in " \t\r\n":
                    k += 1
                if k >= len(self.text):
                    break
                if self.text[k] == '"':
                    self.i = k + 1
                    self.state = "value"
                    continue
                # 冒号后不是引号: 可能遇到嵌套/乱序, 回到找键
                self.state = "seek_key"
                continue
            if self.state == "u_hex":
                while self.i < len(self.text) and len(self.esc_hex) < 4:
                    ch = self.text[self.i]
                    self.i += 1
                    if ch in "0123456789abcdefABCDEF":
                        self.esc_hex += ch
                if len(self.esc_hex) == 4:
                    self.value += chr(int(self.esc_hex, 16))
                    self.esc_hex = ""
                    self.state = "value"
                    continue
                break
            if self.state == "value":
                while self.i < len(self.text):
                    ch = self.text[self.i]
                    self.i += 1
                    if ch == "\\":
                        if self.i < len(self.text):
                            nxt = self.text[self.i]
                            self.i += 1
                            if nxt == "u":
                                self.state = "u_hex"
                                self.esc_hex = ""
                                break
                            self.value += self._simple.get(nxt, nxt)
                        else:
                            # 分块边界正好落在反斜杠之后：不能把这个反斜杠吃掉，
                            # 否则下一块的 "n"/"\"" 会被当成普通字符，直播文本缺一个换行/引号。
                            # 注意要 break（不是 continue），否则 while 会一直重读同一个字符。
                            self.i -= 1
                            break
                        continue
                    if ch == '"':
                        self.state = "done"
                        break
                    self.value += ch
                if self.state == "value":
                    break
                if self.state == "u_hex":
                    continue
                if self.state == "done":
                    break
            else:
                break


def call_deepseek_stream(payload: dict[str, Any]) -> Any:
    settings = read_settings()
    api_key = settings.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("未在 %s 中配置 DEEPSEEK_API_KEY" % CONFIG_FILE.name)
    alias = str(payload.get("model", "flash"))
    models = model_aliases(settings)
    if alias not in models:
        raise ValueError("不支持的模型选项")
    model = models[alias]
    task = str(payload.get("task", "")).strip()[:4000]
    answer = str(payload.get("answer", "")).strip()[:20000]
    files = normalize_files(payload.get("files"))
    stage = str(payload.get("stage", "questions"))
    questions = payload.get("questions") if isinstance(payload.get("questions"), list) else []
    conversation = normalize_conversation(payload.get("conversation"))
    if stage == "questions":
        if len(questions) != 1:
            raise ValueError("第一阶段每次只能提交当前一道题")
    elif stage == "implementation" and not files and not answer:
        raise ValueError("第二阶段请上传代码文件，或直接在回答框中写实现代码")
    elif stage not in {"questions", "implementation"}:
        raise ValueError("不支持的验收阶段")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    if not task or (stage == "questions" and not answer):
        raise ValueError("任务和回答不能为空")
    prior = str(payload.get("priorSummary") or "")[:2000]
    user_prompt = json.dumps(
        {
            "课程": str(context.get("project", ""))[:500],
            "周": str(context.get("week", ""))[:500],
            "学习单元": str(context.get("unit", ""))[:500],
            "验收任务": task,
            "学习者回答或代码": answer,
            "上传的代码文件（只读，不执行）": files_text(files),
            "验收阶段": stage,
            "第一阶段题目": [str(item)[:5000] for item in questions[:5]],
            "此前已通过的题（仅作参考，不要重复原题）": prior or "无",
        },
        ensure_ascii=False,
        indent=2,
    )
    if _mock_enabled():
        result = mock_call_deepseek()
        yield {"type": "text", "text": result["reply"] + chr(10)}
        yield {"type": "result", "result": result, "humanText": result["reply"]}
        return
    request_body = {
        "model": model,
        "temperature": 0.2,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + STREAM_SUFFIX_PROMPT},
            *conversation,
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        api_url(settings),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                 "Accept": "text/event-stream"},
        method="POST",
    )
    scanner = ReplyScanner()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except (TypeError, json.JSONDecodeError):
                    continue
                try:
                    content = obj["choices"][0]["delta"]["content"]
                except (KeyError, IndexError, TypeError):
                    continue
                if not content:
                    continue
                visible = scanner.push(content)
                if visible:
                    yield {"type": "text", "text": visible}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError("DeepSeek API 返回 %s: %s" % (error.code, detail)) from None
    except urllib.error.URLError as error:
        raise RuntimeError("无法连接 DeepSeek API: %s" % error.reason) from None
    except (TimeoutError, OSError) as error:
        # 连接建立之后的读超时/连接中断不是 URLError，原样冒出去会变成"未预期错误"。
        raise RuntimeError("DeepSeek API 连接中断或超时: %s" % error) from None
    full_text = scanner.text
    json_part = full_text
    if "REPLY_JSON_MARKER" in full_text:
        json_part = full_text.split("REPLY_JSON_MARKER", 1)[1]
    parsed = None
    try:
        parsed = parse_json_object(json_part)
    except ValueError:
        parsed = None
    if parsed is None:
        try:
            parsed = parse_json_object(full_text)
        except ValueError:
            parsed = None
    if parsed is None:
        raise RuntimeError("模型未返回可解析的验收结果，请重试")
    result = normalize_result(parsed)
    result["reply"] = str(parsed.get("reply", ""))[:2000]
    human = scanner.value.strip() or result["reply"]
    yield {"type": "result", "result": result, "humanText": human[:8000]}


def call_deepseek(payload: dict[str, Any]) -> dict[str, Any]:
    settings = read_settings()
    api_key = settings.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError(f"未在 {CONFIG_FILE.name} 中配置 DEEPSEEK_API_KEY")

    alias = str(payload.get("model", "flash"))
    models = model_aliases(settings)
    if alias not in models:
        raise ValueError("不支持的模型选项")
    model = models[alias]

    task = str(payload.get("task", "")).strip()[:4000]
    answer = str(payload.get("answer", "")).strip()[:20000]
    files = normalize_files(payload.get("files"))
    stage = str(payload.get("stage", "questions"))
    questions = payload.get("questions") if isinstance(payload.get("questions"), list) else []
    conversation = normalize_conversation(payload.get("conversation"))
    if stage == "questions":
        if len(questions) != 1:
            raise ValueError("第一阶段每次只能提交当前一道题")
    elif stage == "implementation" and not files and not answer:
        raise ValueError("第二阶段请上传代码文件，或直接在回答框中写实现代码")
    elif stage not in {"questions", "implementation"}:
        raise ValueError("不支持的验收阶段")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    if not task or (stage == "questions" and not answer):
        raise ValueError("任务和回答不能为空")

    user_prompt = json.dumps(
        {
            "课程": str(context.get("project", ""))[:500],
            "周": str(context.get("week", ""))[:500],
            "学习单元": str(context.get("unit", ""))[:500],
            "验收任务": task,
            "学习者回答或代码": answer,
            "上传的代码文件（只读，不执行）": files_text(files),
            "验收阶段": stage,
            "第一阶段题目": [str(item)[:5000] for item in questions[:5]],
            "此前已通过的题（仅作参考，不要重复原题）": str(payload.get("priorSummary") or "")[:2000] or "无",
        },
        ensure_ascii=False,
        indent=2,
    )
    if _mock_enabled():
        return mock_call_deepseek()
    request_body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *conversation,
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        api_url(settings),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            upstream = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"DeepSeek API 返回 {error.code}: {detail}") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"无法连接 DeepSeek API: {error.reason}") from None
    except (TimeoutError, OSError) as error:
        # 连接建立之后的读超时/连接中断不是 URLError，原样冒出去会变成"未预期错误"。
        raise RuntimeError(f"DeepSeek API 连接中断或超时: {error}") from None

    try:
        content = upstream["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("DeepSeek API 响应格式不正确") from None
    parsed = parse_json_object(str(content))
    result = normalize_result(parsed)
    result["reply"] = str(parsed.get("reply", ""))[:2000]
    return result




def _normalize_plan_tree(value: Any) -> list[dict[str, Any]]:
    """规范化 AI 返回的计划树（week/day/item），并做规模上限保护。"""
    if not isinstance(value, list):
        return []
    weeks = []
    for week in value[:8]:
        if not isinstance(week, dict):
            continue
        week_text = str(week.get("text") or "").strip()[:200]
        if not week_text:
            continue
        days = []
        for day in (week.get("children") if isinstance(week.get("children"), list) else [])[:6]:
            if not isinstance(day, dict):
                continue
            day_text = str(day.get("text") or "").strip()[:200]
            if not day_text:
                continue
            items = []
            for item in (day.get("children") if isinstance(day.get("children"), list) else [])[:8]:
                if not isinstance(item, dict):
                    continue
                item_text = str(item.get("text") or "").strip()[:300]
                if not item_text:
                    continue
                items.append({
                    "id": None,
                    "type": "item",
                    "text": item_text,
                    "optional": bool(item.get("optional")),
                })
                if len(items) >= 60:
                    break
            if not items:
                continue
            days.append({"id": None, "type": "day", "text": day_text, "children": items})
        if not days:
            continue
        weeks.append({"id": None, "type": "week", "text": week_text, "children": days})
        if len(weeks) >= 8:
            break
    return weeks


def plan_project(topic: str, model_alias: str = "flash") -> dict[str, Any]:
    settings = read_settings()
    api_key = settings.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("未在 %s 中配置 DEEPSEEK_API_KEY" % CONFIG_FILE.name)
    topic_text = str(topic or "").strip()[:2000]
    if not topic_text:
        raise ValueError("学习主题不能为空")
    if _mock_enabled():
        return {
            "description": "围绕“%s”由易到难、从概念到实践的系统学习路径。" % topic_text[:60],
            "tree": [
                {"type": "week", "text": "第1周：基础入门", "children": [
                    {"type": "day", "text": "单元1：核心概念", "children": [
                        {"type": "item", "text": "用自己的话解释“%s”是什么、解决什么问题。" % topic_text[:40], "optional": False},
                        {"type": "item", "text": "写出 3 个典型使用场景，各举一个最小示例。", "optional": False},
                        {"type": "item", "text": "给出一个最容易踩的坑并说明原因。", "optional": False},
                    ]},
                ]},
                {"type": "week", "text": "第2周：实践巩固", "children": [
                    {"type": "day", "text": "单元1：动手练习", "children": [
                        {"type": "item", "text": "完成一个包含%s的小项目并写清思路。" % topic_text[:40], "optional": False},
                        {"type": "item", "text": "为关键逻辑补 2-3 条测试。", "optional": False},
                        {"type": "item", "text": "复盘易错点并整理成清单。", "optional": False},
                    ]},
                ]},
            ],
        }
    models = model_aliases(settings)
    alias = model_alias if model_alias in models else "flash"
    user_prompt = json.dumps({"想学习的主题": topic_text}, ensure_ascii=False, indent=2)
    request_body = {
        "model": models[alias],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROJECT_PLAN_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        api_url(settings),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            upstream = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError("DeepSeek API 返回 %s: %s" % (error.code, detail)) from None
    except urllib.error.URLError as error:
        raise RuntimeError("无法连接 DeepSeek API: %s" % error.reason) from None
    except (TimeoutError, OSError) as error:
        # 连接建立之后的读超时/连接中断不是 URLError，原样冒出去会变成"未预期错误"。
        raise RuntimeError("DeepSeek API 连接中断或超时: %s" % error) from None
    try:
        content = upstream["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("DeepSeek API 响应格式不正确") from None
    try:
        parsed = parse_json_object(str(content))
    except ValueError:
        raise RuntimeError("AI 未返回可解析的项目规划") from None
    tree = _normalize_plan_tree(parsed.get("tree"))
    if not tree:
        raise RuntimeError("AI 未生成有效项目结构")
    return {
        "description": str(parsed.get("description", ""))[:500],
        "tree": tree,
    }


def summarize_knowledge(question: str, context: dict[str, Any] | None = None,
                        model_alias: str = "flash") -> dict[str, str]:
    settings = read_settings()
    api_key = settings.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("未在 %s 中配置 DEEPSEEK_API_KEY" % CONFIG_FILE.name)
    ctx = context if isinstance(context, dict) else {}
    user_prompt = json.dumps({
        "题目": str(question or "").strip()[:4000],
        "课程": str(ctx.get("project", ""))[:500],
        "周": str(ctx.get("week", ""))[:500],
        "学习单元": str(ctx.get("unit", ""))[:500],
    }, ensure_ascii=False, indent=2)
    if _mock_enabled():
        return {"summary": "（模拟摘要）本题核心：理解函数作用域与闭包变量查找；注意 inner 里的 x 是作用于内层的绑定，不影响外层 x。"}
    models = model_aliases(settings)
    alias = model_alias if model_alias in models else "flash"
    request_body = {
        "model": models[alias],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        api_url(settings),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            upstream = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError("DeepSeek API 返回 %s: %s" % (error.code, detail)) from None
    except urllib.error.URLError as error:
        raise RuntimeError("无法连接 DeepSeek API: %s" % error.reason) from None
    except (TimeoutError, OSError) as error:
        # 连接建立之后的读超时/连接中断不是 URLError，原样冒出去会变成"未预期错误"。
        raise RuntimeError("DeepSeek API 连接中断或超时: %s" % error) from None
    try:
        content = upstream["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("DeepSeek API 响应格式不正确") from None
    summary = ""
    try:
        parsed = parse_json_object(str(content))
        summary = str(parsed.get("summary", "")).strip()
    except ValueError:
        summary = str(content).strip()
    if not summary:
        raise RuntimeError("AI 未生成有效摘要")
    return {"summary": summary[:5000]}


def _review_point_count(count: Any) -> int:
    """生成数量夹到 1~3（坏值按默认 3 处理）。"""
    try:
        value = int(count)
    except (TypeError, ValueError):
        value = 3
    return max(1, min(3, value))


def _post_json(settings: dict[str, str], body: dict[str, Any], *, timeout: int = 75) -> dict[str, Any]:
    """POST 请求体到 DeepSeek 并解析出 JSON 对象（与既有非流式调用同一套超时/错误口径）。"""
    api_key = settings.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("未在 %s 中配置 DEEPSEEK_API_KEY" % CONFIG_FILE.name)
    request = urllib.request.Request(
        api_url(settings),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            upstream = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError("DeepSeek API 返回 %s: %s" % (error.code, detail)) from None
    except urllib.error.URLError as error:
        raise RuntimeError("无法连接 DeepSeek API: %s" % error.reason) from None
    except (TimeoutError, OSError) as error:
        # 连接建立之后的读超时/连接中断不是 URLError，原样冒出去会变成"未预期错误"。
        raise RuntimeError("DeepSeek API 连接中断或超时: %s" % error) from None
    try:
        content = upstream["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("DeepSeek API 响应格式不正确") from None
    return parse_json_object(str(content))


def is_configured() -> bool:
    """是否有可用的 AI 通道：配了 API key，或显式开启离线 mock（`TODO_AI_MOCK=1`）。"""
    return _mock_enabled() or bool(read_settings().get("DEEPSEEK_API_KEY"))


def generate_review_points(*, task_id: str, project_id: str, task_text: str, count: int = 3,
                           remedial: bool = False, gap: str = "") -> list[dict]:
    """按任务补 1~3 个知识点；mock 模式返回固定样例，真实分支失败时返回空列表。

    `remedial=True` 时走"针对失败点出补漏题"的提示词：`gap` 是验收失败的信息，
    mock 模式返回固定补漏点（code 形如 `py.ai.<taskId>.remedial.<n>`），
    真实分支把失败点一起发给模型。两种模式生成的 taskRefs 都回指当前任务。

    生成结果先过 `review_content.normalize_points` 清洗，再保证每个点都有一条回指当前任务的
    taskRef（模型漏写时补 exercises），最后逐条过 `validate_points` 闸门——不合格的点直接丢弃，
    不让整次生成失败（AI 是可选增强，不是完成任务的阻塞项）。
    """
    count = _review_point_count(count)
    focus = str(gap or "").strip() or task_text.strip()
    if _mock_enabled():
        base = focus[:20] or task_id
        namespace = f"py.ai.{task_id}.remedial" if remedial else f"py.ai.{task_id}"
        label = "补漏点" if remedial else "补充点"
        return [{
            "code": f"{namespace}.{index + 1}",
            "title": f"{base} · {label} {index + 1}",
            "minutes": 15, "module": "AI 补充", "level": "基础",
            "taskRefs": [{"taskId": task_id, "projectId": project_id, "relation": "exercises"}],
            "concept": {"prompt": f"用自己的话解释：{base}（第 {index + 1} 点）", "answer": ["AI 生成的要点"]},
            "predict": {"prompt": "写出输出", "code": "print(len([1, 2, 3]))", "expected": ["3"], "explain": "长度"},
            "debug": {"prompt": "找错", "code": "x = [1, 2]\nprint(x[2])", "rootCause": "越界", "fix": "改索引"},
            "code_task": {"prompt": "写一个函数", "acceptance": ["能处理空输入"], "reference": "def f(xs): return xs or []"},
            "pitfalls": ["边界输入"],
        } for index in range(count)]
    settings = read_settings()
    user_payload = {"任务": task_text, "任务ID": task_id, "项目ID": project_id, "数量": count}
    if remedial:
        user_payload["失败点"] = gap
    request_body = {
        "model": model_aliases(settings).get("flash", "deepseek-chat"),
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": REVIEW_REMEDIAL_PROMPT if remedial else REVIEW_POINTS_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    try:
        parsed = _post_json(settings, request_body)
    except Exception:
        return []
    draft = parsed.get("points") if isinstance(parsed, dict) else None
    if not isinstance(draft, list):
        return []
    fallback_prefix = f"py.ai.{task_id}.remedial" if remedial else f"py.ai.{task_id}"
    for index, point in enumerate(draft, start=1):
        if isinstance(point, dict):
            point.setdefault("code", f"{fallback_prefix}.{index}")
    points = []
    for point in review_content.normalize_points(draft):
        if task_id and not any(ref["taskId"] == task_id for ref in point["taskRefs"]):
            point["taskRefs"].append({"taskId": task_id, "projectId": project_id, "relation": "exercises"})
        if not review_content.validate_points([point]):
            points.append(point)
    return points


def grade_review_answer(*, code: str, question_type: str, answer: str, reference: dict) -> dict:
    """可选 AI 判分：返回 {correct, missing, wrongAt, hint}；失败时返回空 dict，不影响自评。"""
    if _mock_enabled():
        answered = bool(str(answer).strip())
        return {"correct": answered,
                "missing": [] if answered else ["没有写出内容"],
                "wrongAt": "",
                "hint": "（模拟判分）对照参考答案检查关键机制是否讲到"}
    settings = read_settings()
    request_body = {
        "model": model_aliases(settings).get("flash", "deepseek-chat"),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": REVIEW_GRADE_PROMPT},
            {"role": "user", "content": json.dumps(
                {"知识点": code, "题型": question_type, "我的答案": answer, "参考答案": reference},
                ensure_ascii=False)},
        ],
    }
    try:
        parsed = _post_json(settings, request_body)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {"correct": parsed.get("correct") is True,
            "missing": string_list(parsed.get("missing")),
            "wrongAt": str(parsed.get("wrongAt") or "")[:1000],
            "hint": str(parsed.get("hint") or "")[:1000]}


def call_question(payload: dict[str, Any]) -> dict[str, Any]:
    settings = read_settings()
    api_key = settings.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError(f"未在 {CONFIG_FILE.name} 中配置 DEEPSEEK_API_KEY")
    models = model_aliases(settings)
    alias = str(payload.get("model", "flash"))
    if alias not in models:
        raise ValueError("不支持的模型选项")
    task = str(payload.get("task", "")).strip()[:4000]
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    files = normalize_files(payload.get("files"))
    if not task:
        raise ValueError("任务不能为空")
    count_raw = payload.get("count")
    required = 3
    if count_raw is not None:
        try:
            required = int(count_raw)
        except (TypeError, ValueError):
            required = 3
        required = max(1, min(5, required))
    weak_point = str(payload.get("weakPoint") or "").strip()[:2000]
    prior = str(payload.get("priorSummary") or "")[:1800]
    if _mock_enabled():
        return mock_call_question(required)
    user_prompt = json.dumps({
        "课程": str(context.get("project", ""))[:500],
        "周": str(context.get("week", ""))[:500],
        "学习单元": str(context.get("unit", ""))[:500],
        "当前任务": task,
        "上传代码（只读，不执行）": files_text(files),
        "聚焦薄弱点": weak_point or "无",
        "此前已出的题（参考，不要重复）": prior or "无",
    }, ensure_ascii=False, indent=2)
    request_body = {
        "model": models[alias],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": QUESTION_PROMPT
                + ("" if count_raw is None else (
                    chr(10) + chr(10) + "请再生成 %d 道难度与当前题相当、不同角度、不重复的针对题。"
                    "题目要直击给定薄弱点，优先用真实可运行代码、预测输出、找 bug 或补测试；"
                    "严禁复述已有题目；若学习者上传了代码，可结合其代码出题。" % required
                ))},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = urllib.request.Request(
        api_url(settings), data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            upstream = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"DeepSeek API 返回 {error.code}: {detail}") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"无法连接 DeepSeek API: {error.reason}") from None
    except (TimeoutError, OSError) as error:
        # 连接建立之后的读超时/连接中断不是 URLError，原样冒出去会变成"未预期错误"。
        raise RuntimeError(f"DeepSeek API 连接中断或超时: {error}") from None
    try:
        content = upstream["choices"][0]["message"]["content"]
        parsed = parse_json_object(str(content))
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("DeepSeek API 响应格式不正确") from None
    questions = parsed.get("questions")
    if not isinstance(questions, list):
        # Compatibility with an older model response that returns one question.
        single = str(parsed.get("question", "")).strip()
        questions = [single] if single else []
    questions = [str(item).strip()[:5000] for item in questions[:required] if str(item).strip()]
    if len(questions) < required:
        raise RuntimeError("模型没有返回至少 %d 道有效题目" % required)
    return {"questions": questions[:required], "focus": str(parsed.get("focus", ""))[:1000]}
