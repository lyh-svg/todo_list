"""P12 回归：直播文本扫描不能一边逐字符 += 一边整段重扫。

旧实现：`self.text += chunk` 后在整段 text 上 find/索引，且 `self.value += ch` 逐字符拼接。
实测按 4 字符一块推：2 万字符 15.9 ms、10 万字符 329.3 ms（超线性）。

这里既做"与旧实现逐字符等价"的对照（把旧实现原样拷进来当标准答案），
也钉住新实现的复杂度特征：解析过的前缀必须被丢掉，不能越堆越长。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-reply-scanner-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import ai_service  # noqa: E402

SIMPLE = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f"}


def reference_scan(chunks: list[str]) -> tuple[str, str, str]:
    """旧实现（P12 之前）的逐行拷贝：整段 text 查找 + 逐字符 value += 。返回 (直播文本, value, text)。"""
    text = ""
    value = ""
    yielded = 0
    state = "seek_key"
    i = 0
    esc_hex = ""
    visible_parts: list[str] = []
    for chunk in chunks:
        text += chunk
        while True:
            if state == "seek_key":
                idx = text.find('"reply"', i)
                if idx < 0:
                    break
                i = idx + len('"reply"')
                state = "seek_colon"
                continue
            if state == "seek_colon":
                idx = text.find(":", i)
                if idx < 0:
                    break
                i = idx + 1
                state = "seek_quote"
                continue
            if state == "seek_quote":
                k = i
                while k < len(text) and text[k] in " \t\r\n":
                    k += 1
                if k >= len(text):
                    break
                if text[k] == '"':
                    i = k + 1
                    state = "value"
                    continue
                state = "seek_key"
                continue
            if state == "u_hex":
                while i < len(text) and len(esc_hex) < 4:
                    ch = text[i]
                    i += 1
                    if ch in "0123456789abcdefABCDEF":
                        esc_hex += ch
                if len(esc_hex) == 4:
                    value += chr(int(esc_hex, 16))
                    esc_hex = ""
                    state = "value"
                    continue
                break
            if state == "value":
                while i < len(text):
                    ch = text[i]
                    i += 1
                    if ch == "\\":
                        if i < len(text):
                            nxt = text[i]
                            i += 1
                            if nxt == "u":
                                state = "u_hex"
                                esc_hex = ""
                                break
                            value += SIMPLE.get(nxt, nxt)
                        else:
                            i -= 1
                            break
                        continue
                    if ch == '"':
                        state = "done"
                        break
                    value += ch
                if state == "value":
                    break
                if state == "u_hex":
                    continue
                if state == "done":
                    break
            else:
                break
        visible_parts.append(value[yielded:])
        yielded = len(value)
    return "".join(visible_parts), value, text


def push_all(chunks: list[str]) -> tuple[str, str, str]:
    scanner = ai_service.ReplyScanner()
    visible = "".join(scanner.push(chunk) for chunk in chunks)
    return visible, scanner.value, scanner.text


def chunked(payload: str, size: int) -> list[str]:
    return [payload[index:index + size] for index in range(0, len(payload), size)]


class ReplyScannerEquivalenceTests(unittest.TestCase):
    PAYLOADS = [
        json.dumps({"reply": "普通的一段中文回复，包含标点。", "score": 90}, ensure_ascii=False),
        json.dumps({"reply": "带转义：\n换行\t制表 \"引号\" \\反斜杠 /斜杠", "x": 1}, ensure_ascii=False),
        json.dumps({"reply": "unicode 转义：\u4e2d\u6587\ud83d\ude00", "x": 1}, ensure_ascii=False),
        json.dumps({"passed": True, "summary": "先说别的", "reply": "第二段的 reply",
                    "nested": {"reply": "嵌套里的不算"}}, ensure_ascii=False),
        json.dumps({"reply": ""}, ensure_ascii=False),
        json.dumps({"passed": False, "problems": ["没有 reply"]}, ensure_ascii=False),
        json.dumps({"reply": "结尾就是反斜杠前的字符\\", "x": 1}, ensure_ascii=False),
    ]

    def test_matches_reference_for_every_chunk_size(self) -> None:
        for payload in self.PAYLOADS:
            for size in (1, 2, 3, 4, 5, 7, 13, 64, 1000):
                with self.subTest(payload=payload[:24], size=size):
                    expected = reference_scan(chunked(payload, size))
                    actual = push_all(chunked(payload, size))
                    self.assertEqual(actual, expected, f"chunk={size}")

    def test_matches_reference_for_every_split_point(self) -> None:
        payload = json.dumps({"reply": "a\\nb\u4e2d\"c", "z": 1}, ensure_ascii=False)
        for split in range(len(payload) + 1):
            chunks = [payload[:split], payload[split:]]
            self.assertEqual(push_all(chunks), reference_scan(chunks), f"split={split}")

    def test_done_state_ignores_later_reply_keys(self) -> None:
        chunks = ['{"reply": "第一个"', ', "reply": "第二个"}']
        self.assertEqual(push_all(chunks), reference_scan(chunks))
        self.assertEqual(push_all(chunks)[1], "第一个")


class ReplyScannerComplexityTests(unittest.TestCase):
    def test_consumed_prefix_is_dropped(self) -> None:
        """长回复分块推送后，未解析的尾巴必须很小，而且**不随回复长度增长**。"""
        tails = []
        for repeat in (500, 5000):
            payload = json.dumps({"reply": "中文回复内容与解释。" * repeat, "x": 1}, ensure_ascii=False)
            scanner = ai_service.ReplyScanner()
            chunks = chunked(payload, 4)
            for chunk in chunks:
                scanner.push(chunk)
            self.assertEqual(scanner.value, reference_scan(chunks)[1])
            self.assertEqual(len(scanner.text), len(payload), "完整原文仍要保留给最后的 JSON 解析")
            tails.append(len(scanner._buffer))
        self.assertLessEqual(max(tails), 64, f"未解析的尾巴应该很小，实际 {tails}")
        self.assertEqual(tails[0], tails[1],
                         f"尾巴长度不能随回复变长而增长（{tails[0]} vs {tails[1]}）")

    def test_visible_output_is_exactly_the_new_part(self) -> None:
        payload = json.dumps({"reply": "一二三四五六七八九十" * 20, "x": 1}, ensure_ascii=False)
        scanner = ai_service.ReplyScanner()
        visible = []
        for chunk in chunked(payload, 3):
            part = scanner.push(chunk)
            expected_value = reference_scan([chunk])[1]
            visible.append(part)
            if part:
                self.assertTrue(scanner.value.endswith(part), "直播出去的必须是 value 的新尾巴")
            del expected_value
        self.assertEqual("".join(visible), scanner.value)
        self.assertEqual("".join(visible), reference_scan(chunked(payload, 3))[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
