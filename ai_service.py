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

from prompts import QUESTION_PROMPT, SYSTEM_PROMPT

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


def mock_call_question() -> dict[str, Any]:
    return {
        "questions": [
            "（模拟题1）预测下面这段代码的输出，并解释可变默认参数的创建时机：",
            "（模拟题2）解释 nonlocal 与 global 的差别，并给一个可运行的例子：",
            "（模拟题3）定位这段代码的 bug，说明根因与修复方向：",
        ],
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

    try:
        content = upstream["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("DeepSeek API 响应格式不正确") from None
    parsed = parse_json_object(str(content))
    result = normalize_result(parsed)
    result["reply"] = str(parsed.get("reply", ""))[:2000]
    return result


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
    if _mock_enabled():
        return mock_call_question()
    user_prompt = json.dumps({
        "课程": str(context.get("project", ""))[:500],
        "周": str(context.get("week", ""))[:500],
        "学习单元": str(context.get("unit", ""))[:500],
        "当前任务": task,
        "上传代码（只读，不执行）": files_text(files),
    }, ensure_ascii=False, indent=2)
    request_body = {
        "model": models[alias],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": QUESTION_PROMPT},
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
    questions = [str(item).strip()[:5000] for item in questions[:5] if str(item).strip()]
    if len(questions) < 3:
        raise RuntimeError("模型没有返回至少三道有效题目")
    return {"questions": questions, "focus": str(parsed.get("focus", ""))[:1000]}