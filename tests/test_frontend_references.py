"""前端静态引用检查（防止"用了没声明的变量"这类只在浏览器里才炸的错误）。

背景：批次 2/3 里有两处 DOM 引用插入因为锚点行不存在而静默失败，
`quickAddBtn` / `viewBar` / `batchToggleBtn` 等标识符从未声明，
`node --check` 只查语法查不出来，页面却会在加载时直接 ReferenceError。

这个测试用"去掉注释与字符串后做标识符盘点"的粗粒度静态分析来兜住这类问题：
  1. app.js 里 `getElementById('x')` 的每个 id 必须存在于 index.html；
  2. 用到的标识符必须在本文件声明过（const/let/var/function/参数/catch/解构），
     或者在白名单里（浏览器全局、JS 内置、关键字等）。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
APP_JS = APP_DIR / "js" / "app.js"
INDEX_HTML = APP_DIR / "index.html"

GLOBALS = {
    # JS 内置
    "Object", "Array", "String", "Number", "Boolean", "Math", "JSON", "Date", "Map", "Set", "WeakMap",
    "Promise", "RegExp", "Error", "TypeError", "RangeError", "Symbol", "BigInt", "Proxy", "Reflect",
    "parseInt", "parseFloat", "isNaN", "isFinite", "encodeURIComponent", "decodeURIComponent",
    "encodeURI", "decodeURI", "structuredClone", "Infinity", "NaN", "undefined", "globalThis",
    # 浏览器 / 宿主
    "window", "document", "navigator", "location", "history", "localStorage", "sessionStorage",
    "console", "fetch", "Headers", "Request", "Response", "URL", "URLSearchParams", "Blob", "File",
    "FileReader", "Image", "TextDecoder", "TextEncoder", "AbortController", "Notification",
    "setTimeout", "clearTimeout", "setInterval", "clearInterval", "requestAnimationFrame",
    "cancelAnimationFrame", "alert", "confirm", "prompt", "crypto", "MutationObserver", "CustomEvent",
    "Event", "FormData", "Intl", "performance", "queueMicrotask", "module", "exports", "require",
    # 语法关键字/字面量（正则抓标识符时会带上一些）
    "true", "false", "null", "this", "new", "typeof", "instanceof", "in", "of", "return", "if",
    "else", "for", "while", "do", "switch", "case", "break", "continue", "function", "class",
    "const", "let", "var", "try", "catch", "finally", "throw", "delete", "void", "yield", "await",
    "async", "get", "set", "static", "extends", "super", "import", "export", "default", "from",
    "as", "with", "debugger",
    # 本文件里通过 window.X 注入的
    "TodoApiClient", "TodoStudyTools",
}


REGEX_ALLOWED_BEFORE = set("([{,;:!&|?=+-*%<>~^") | {"return", "typeof", "case", "in", "of", "do", "else", "new", "delete", "void", "instanceof", "yield", "await"}


def strip_comments_and_strings(source: str) -> str:
    """把注释、字符串、模板串、正则字面量替换成占位符（状态机，避免误吞代码）。"""
    out: list[str] = []
    i = 0
    length = len(source)
    # 记录上一个有意义的字符/单词，用来判断 `/` 是除号还是正则开头
    prev_chars = ""

    def prev_significant() -> str:
        for char in reversed(prev_chars):
            if not char.isspace():
                return char
        return ""

    def prev_word() -> str:
        word = ""
        for char in reversed(prev_chars):
            if char.isalnum() or char in "_$":
                word = char + word
            elif not char.isspace():
                break
        return word

    while i < length:
        ch = source[i]
        if source.startswith("//", i):
            newline = source.find("\n", i)
            i = length if newline < 0 else newline
            continue
        if source.startswith("/*", i):
            close = source.find("*/", i + 2)
            i = length if close < 0 else close + 2
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            while i < length and source[i] != quote:
                i += 2 if source[i] == "\\" else 1
            i += 1
            out.append(' "" ')
            prev_chars += ' "" '
            continue
        if ch == "`":
            depth = 0
            i += 1
            while i < length:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == "`" and depth == 0:
                    i += 1
                    break
                if source.startswith("${", i):
                    depth += 1
                    i += 2
                    continue
                if source[i] == "}" and depth > 0:
                    depth -= 1
                    i += 1
                    continue
                i += 1
            out.append(' `` ')
            prev_chars += ' `` '
            continue
        if ch == "/" and (not prev_significant() or prev_significant() in REGEX_ALLOWED_BEFORE
                          or prev_word() in REGEX_ALLOWED_BEFORE):
            i += 1
            in_class = False
            while i < length:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == "[":
                    in_class = True
                elif source[i] == "]":
                    in_class = False
                elif source[i] == "/" and not in_class:
                    i += 1
                    while i < length and source[i].isalpha():
                        i += 1  # 正则 flags（gimsuy）
                    break
                elif source[i] == "\n":
                    break
                i += 1
            out.append(' 0 ')
            prev_chars += ' 0 '
            continue
        out.append(ch)
        prev_chars = (prev_chars + ch)[-40:]
        i += 1
    return "".join(out)


def get_element_ids(source: str) -> list[str]:
    return re.findall(r"getElementById\(\s*'([^']+)'\s*\)", source) + \
        re.findall(r'getElementById\(\s*"([^"]+)"\s*\)', source)


class FrontendReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = APP_JS.read_text(encoding="utf-8")
        cls.source = strip_comments_and_strings(cls.raw)
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_every_get_element_by_id_target_exists_in_html(self) -> None:
        # 注意：必须用 raw，不能用 strip_comments_and_strings 之后的 source——
        # 那个版本把字符串字面量换成 ` 0 `，getElementById('x') 永远匹配不到，断言会变成空转。
        html_ids = set(re.findall(r'id="([^"]+)"', self.html))
        missing = sorted({element_id for element_id in get_element_ids(self.raw)
                          if element_id not in html_ids})
        self.assertEqual(missing, [], f"app.js 引用了 index.html 里不存在的 id：{missing}")

    def test_element_id_check_would_catch_a_missing_id(self) -> None:
        """自测：这个检查必须真的能抓到"绑定到不存在的元素"（之前用 stripped 源是空转的）。"""
        sample = "const missing = document.getElementById('thisIdDoesNotExist123');\n"
        # 旧的错误做法（stripped 源）匹配不到任何东西——这正是它空转的原因。
        self.assertEqual(get_element_ids(strip_comments_and_strings(sample)), [])
        self.assertEqual(get_element_ids(sample), ["thisIdDoesNotExist123"])

    @staticmethod
    def source_of(text: str) -> str:
        return strip_comments_and_strings(text)

    def test_no_undeclared_identifiers(self) -> None:
        undeclared = undeclared_identifiers(self.source)
        self.assertEqual(undeclared, [],
                         "app.js 里用到但没声明的标识符（会 ReferenceError）：" + ", ".join(undeclared))

    def test_analyzer_would_catch_the_real_bug(self) -> None:
        """自测：分析器必须能抓出"用了没声明"的标识符（这正是本会话踩过的坑）。"""
        sample = (
            "const known = 1;\n"
            "function initEvents() {\n"
            "    quickAddBtn.addEventListener('click', () => known);\n"
            "}\n"
        )
        self.assertIn("quickAddBtn", undeclared_identifiers(sample))

    def test_frontend_api_paths_exist_in_backend(self) -> None:
        """前端调用的每个 /api 路径都必须在 local_server.py 里声明过。"""
        server = (APP_DIR / "local_server.py").read_text(encoding="utf-8")
        declared = set(re.findall(r'"(/api/[a-zA-Z0-9_\-/]+)"', server))
        used = set(re.findall(r"/api/[a-zA-Z0-9_\-/]+", self.raw))
        missing = sorted(path for path in used if path not in declared)
        self.assertEqual(missing, [], "前端调用了后端没有的接口：" + ", ".join(missing))

    def test_view_switching_is_centralized(self) -> None:
        """视图切换必须只走 activateView：新增视图后忘记移除 active 会让两个视图同时显示且退不出去。"""
        self.assertIn("function activateView(activeView)", self.source, "缺少统一的视图切换函数")
        helper = re.search(r"function activateView\(activeView\) \{(.*?)\n    \}", self.source, re.S)
        self.assertIsNotNone(helper, "找不到 activateView 的实现")
        body = helper.group(1)
        view_ids = re.findall(r'id="(\w*View)"', self.html)
        for view_id in view_ids:
            name = view_id[0].lower() + view_id[1:]
            self.assertIn(name, body, f"{view_id} 没有出现在 activateView 的视图列表里（会退不出去）")
        # 除了 helper 内部，不应再有别处直接 add/remove active
        stray = [line for line in self.source.splitlines()
                 if "classList.add('active')" in line or "classList.remove('active')" in line]
        self.assertEqual(stray, [], "视图 active 只允许在 activateView 里切换：" + " | ".join(stray))

    def test_dom_references_are_declared_once(self) -> None:
        for element_id in sorted(set(get_element_ids(self.source))):
            pattern = rf"const\s+\w+\s*=\s*document\.getElementById\(\s*['\"]{re.escape(element_id)}['\"]\s*\)"
            self.assertEqual(len(re.findall(pattern, self.source)), 1,
                             f"{element_id} 的 DOM 引用必须恰好声明一次")


def undeclared_identifiers(source: str) -> list[str]:
    if True:
        declared: set[str] = set()
        declared.update(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", source))
        declared.update(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)", source))
        declared.update(re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", source))
        # 函数/箭头函数参数（含解构里的名字）
        param_blocks = (re.findall(r"\(([^()]*)\)\s*=>", source)
                        + re.findall(r"function\s*[\w$]*\s*\(([^()]*)\)", source)
                        + re.findall(r"(?<![\w$])([A-Za-z_$][\w$]*)\s*=>", source))
        for params in param_blocks:
            for piece in re.split(r"[,{}\[\]\s:=]+", params):
                if re.fullmatch(r"[A-Za-z_$][\w$]*", piece or ""):
                    declared.add(piece)
        declared.update(re.findall(r"\bcatch\s*\(\s*([A-Za-z_$][\w$]*)", source))
        # 解构声明：const { a, b } = ... / const [a, b] = ...
        for block in re.findall(r"\b(?:const|let|var)\s*[{[]([^{}[\]]*)[}\]]", source):
            for piece in re.split(r"[,:\s]+", block):
                if re.fullmatch(r"[A-Za-z_$][\w$]*", piece or ""):
                    declared.add(piece)
        # 对象的简写属性 { foo } 也算声明过；这里把"出现在冒号左侧的 key"排除
        candidates = set(re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)", source))
        # 去掉属性访问与对象键
        for name in re.findall(r"\.\s*([A-Za-z_$][\w$]*)", source):
            candidates.discard(name)
        for name in re.findall(r"([A-Za-z_$][\w$]*)\s*:", source):
            candidates.discard(name)
        return sorted(name for name in candidates
                      if name not in declared and name not in GLOBALS)

if __name__ == "__main__":
    unittest.main(verbosity=2)
