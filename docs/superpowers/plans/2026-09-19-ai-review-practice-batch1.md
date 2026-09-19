# AI 现场出题（复习加练）· 第一批 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在复习会话卡片与知识点页各加一个「AI 出题」入口：AI 现场出一道新题（只给题面）→ 你作答 → AI 批改并给示范解法 → 满意可「收进题库」（本批先只入库并可在知识点页管理，不参与自动轮换）。

**Architecture:** 新增一张 `review_ai_questions` 表（schema v9→v10，纯增量 DDL）存收藏题；新增 5 个 HTTP 端点；AI 层新增两个提示词与两个函数（`generate_ai_question` / `review_ai_answer`），全部走现有 `_post_json` 与 `TODO_AI_MOCK` 通道；前端把整块「AI 加练」UI 做成**一个动态渲染器**，两个入口只是换容器（复习卡片内联、知识点页弹窗），判分与示范解法用同一个 `renderAiVerdict`。临时加练**不写任何复习状态**（不落库、不改排期）。

**Tech Stack:** Python 3.10+ 标准库（`http.server` / `sqlite3` / `urllib` / `threading`），原生 HTML/CSS/JS，unittest，Playwright（可选，CI 有），DOM 桩冒烟脚本。

**Spec:** `docs/superpowers/specs/2026-09-19-ai-review-practice-design.md`（第一批 = spec §10 的第一行）

**与 spec 的一处实现细化（更省、语义不变）：** spec §6.3 写的是"复习卡片用固定 id 内联渲染、弹窗用动态 DOM"。本计划改为**整块加练 UI 都动态渲染**，两个入口只是传入不同容器；固定题那套 DOM（`#reviewAnswerInput` 等）在加练期间整体隐藏。少一套并行渲染代码，`renderAiVerdict` 仍是共用边界。

## Global Constraints

- 代码文件（`*.py` / `*.js` / `*.css` / `*.html` / `*.md`）必须 **CRLF**；`*.sh`、`.gitignore`、`requirements*.txt`、`*.yml`、`*.mjs`、`package*.json` 必须 **LF**。`./scripts/check.sh` 第 9 步强制检查。
- 运行时**零第三方依赖**（只用 Python 标准库）；测试只用 `unittest` + `unittest.mock`。
- 所有测试都在临时库里跑：模块级 `os.environ["TODO_SQLITE_FILE"] = tempfile...`；**绝不碰真实 `data/`**。
- 后端状态码口径：参数非法 **400**、资源不存在 **404**、未配置 AI **503**、AI 调用失败 **502**、其余 500；任何分支都不能返回空 body。
- 新增 HTTP 路径必须同时登记进 `do_GET` / `do_POST` / `do_DELETE` 的**白名单**，否则会被 404 兜底。
- 改了 `js/app.js` 或 `css/style.css` 必须同步提升 `index.html` 里的 `?v=`（本批：`app.js?v=58→59`、`style.css?v=36→37`）。
- 数据库变更只允许**增量 DDL**（建表/加列，无回填）；迁移失败必须回滚（现成机制），迁移前自动快照。
- 每个任务结束都要能独立验证；**提交前必须 `./scripts/check.sh` 9/9 通过**（第 4 步含 509+ 单测、第 8 步反向验证）。
- 反向验证脚本条数与 `scripts/check.sh` 第 8 步标签必须同步（本批 65 → 68）。
- 提交信息用中文、动词开头；不提交 `data/`、不提交 `.superpowers/`。
- 命令一律在仓库根目录执行；测试命令形如 `python3 -m unittest tests.test_xxx -v`。

---

## 文件结构

| 文件 | 责任 | 本批动作 |
| --- | --- | --- |
| `storage.py` | schema 版本、建表 DDL、迁移阶梯 | 改：`SCHEMA_VERSION=10` + 新表 DDL + 迁移注释 |
| `review_content.py` | 内容清洗与校验（题库 + AI 题共用） | 改：`normalize_ai_question` / `validate_ai_question` |
| `review_storage.py` | 复习数据的读写（知识点、作答、排期） | 改：AI 题的收藏/列表/读取/删除 + 出题上下文 |
| `prompts.py` | 全部提示词 | 改：`REVIEW_AI_QUESTION_PROMPT` / `REVIEW_AI_ANSWER_PROMPT` |
| `ai_service.py` | DeepSeek 调用、mock、结构校验 | 改：`generate_ai_question` / `review_ai_answer` + 两个 mock |
| `local_server.py` | HTTP 路由与错误映射 | 改：5 个新端点 + 白名单 |
| `index.html` | 页面骨架 + 缓存号 | 改：复习卡片加「AI 出道新题」按钮与 `#reviewAiPractice` 容器 + `?v=` |
| `js/app.js` | 全部前端行为 | 改：加练状态机、动态渲染器、知识点页徽标/弹窗/删除 |
| `css/style.css` | 样式 | 改：`.ai-badge` / `.review-ai-*` |
| `tests/test_review_migration.py` | 迁移阶梯回归 | 改：版本断言 + v9→v10 新用例 |
| `tests/test_review_content.py` | 内容清洗/校验回归 | 改：AI 题清洗与校验用例 |
| `tests/test_review_ai_questions.py` | AI 题存储层回归 | 建 |
| `tests/test_ai_review_questions.py` | AI 出题/批改层回归 | 建 |
| `tests/test_review_http.py` | 复习接口 HTTP 层 | 改：新端点 200/400/404/502/503 用例 |
| `tests/frontend/dom-smoke.js` | 前端运行时冒烟 | 改：新端点桩 + 两个入口的交互断言 |
| `tests/e2e-verify.sh` | 端到端 HTTP 断言 | 改：加练全流程 + 零留痕断言 |
| `scripts/verify-tests-catch.py` | 反向验证 | 改：+3 条 |
| `scripts/check.sh` | 门禁 | 改：标签 65 → 68 |
| `README.md` | 使用说明 | 改：一行说明 AI 加练入口 |

---

### Task 1: schema v9 → v10（新增 `review_ai_questions` 表）

**Files:**
- Modify: `storage.py:45`（`SCHEMA_VERSION`）、`storage.py:481-495`（复习表 DDL 区）、`storage.py:1050-1060`（`ensure_schema` 阶梯注释）
- Test: `tests/test_review_migration.py:22-42`

**Interfaces:**
- Consumes: 现有 `_bootstrap_state_database()`（幂等 DDL 重放）、`ensure_schema()`（版本阶梯 + 快照 + 回滚）
- Produces: 表 `review_ai_questions(question_id TEXT PRIMARY KEY, code TEXT, question_type TEXT, content_json TEXT, created_at TEXT, updated_at TEXT)` + 索引 `idx_review_ai_questions_code`；`storage.SCHEMA_VERSION == 10`

- [ ] **Step 1: 写失败的测试**

把 `tests/test_review_migration.py` 第 22-23 行改成：

```python
    def test_schema_version_is_10(self) -> None:
        self.assertEqual(storage.SCHEMA_VERSION, 10)
```

在同文件 `ReviewMigrationTests` 末尾追加：

```python
    def test_v9_database_gains_ai_question_table(self) -> None:
        """v9 -> v10：新增 AI 加练收藏库（review_ai_questions），旧数据一行不动。"""
        storage.ensure_schema()
        project = {
            "id": "p-ai", "name": "迁移不动我", "description": "", "createdAt": "2026-09-19",
            "assessmentEnabled": False,
            "tree": [{"id": "w-ai", "type": "week", "text": "第1周", "completed": False,
                      "expanded": False, "createdAt": "2026-09-19", "children": [
                          {"id": "i-ai", "type": "item", "text": "任务", "completed": False,
                           "completedAt": None, "optional": False, "assessmentRequired": False,
                           "assessmentHistory": 0, "assessment": None,
                           "createdAt": "2026-09-19", "children": []}]}],
        }
        storage.write_project(project, None)
        before = storage.read_project("p-ai")[0]
        # 伪装成"升级前的 v9 库"：删掉新表并把版本退回去
        with storage.open_state_database() as connection:
            connection.execute("DROP TABLE IF EXISTS review_ai_questions")
            connection.execute("PRAGMA user_version=9")
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertEqual(version, storage.SCHEMA_VERSION)
        self.assertIn("review_ai_questions", tables)
        self.assertIn("idx_review_ai_questions_code", indexes)
        self.assertEqual(storage.read_project("p-ai")[0], before, "迁移不得改动项目数据")
        self.assertTrue(storage.check_database_integrity())
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.test_review_migration -v
```

Expected: `test_schema_version_is_10` FAIL（`9 != 10`）；`test_v9_database_gains_ai_question_table` FAIL（`review_ai_questions` 不在 tables 里）

- [ ] **Step 3: 改 `storage.py`**

第 45 行：

```python
SCHEMA_VERSION = 10
```

在 `_bootstrap_state_database()` 的 `executescript` 里，把 `CREATE TABLE IF NOT EXISTS review_sessions (...)` 之后、现有那批 `CREATE INDEX` 之前插入：

```sql
        CREATE TABLE IF NOT EXISTS review_ai_questions (
            question_id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            question_type TEXT NOT NULL,
            content_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_review_ai_questions_code
            ON review_ai_questions(code, question_type, created_at);
```

在 `ensure_schema()` 的阶梯注释里，`_drop_removed_tables()` 之前补一行：

```python
            # v9 -> v10：新增 review_ai_questions（AI 加练收藏库）。纯增量 DDL、幂等、不回填，
            # 由 open_state_database 的 bootstrap 建表 + 版本号跃迁触发；旧表旧行一律不动。
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.test_review_migration tests.test_schema_and_import -v
```

Expected: 全部 `ok`（`tests/test_schema_and_import.py` 用的是 `storage.SCHEMA_VERSION` 常量，不需要改）

- [ ] **Step 5: 提交**

```bash
git add storage.py tests/test_review_migration.py
git commit -m "feat(review): schema v10 新增 AI 加练收藏表 review_ai_questions"
```

---

### Task 2: AI 题的清洗与校验（`review_content.py`）

**Files:**
- Modify: `review_content.py`（在 `load_content_file` 之前追加两个公开函数）
- Test: `tests/test_review_content.py`（在 `ReviewContentTests` 里追加）

**Interfaces:**
- Consumes: 现有私有助手 `_text` / `_text_list`、常量 `QUESTION_TYPES`
- Produces:
  - `review_content.normalize_ai_question(value: Any) -> dict[str, Any]` → `{"questionType", "prompt", "code", "focus", "reference": {...}}`
  - `review_content.validate_ai_question(question: Any, *, require_reference: bool = False) -> list[str]`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_review_content.py` 的 `ReviewContentTests` 里追加：

```python
    def test_normalize_ai_question_shapes_reference(self) -> None:
        normalized = review_content.normalize_ai_question({
            "questionType": "predict", "prompt": "  写出输出  ",
            "code": "print(1)", "focus": "默认参数", "ignoreMe": "丢掉",
            "reference": {"expected": ["1", "  "], "explain": " 因为定义时求值 ",
                          "unknown": "丢掉"},
        })
        self.assertEqual(normalized["questionType"], "predict")
        self.assertEqual(normalized["prompt"], "写出输出")
        self.assertEqual(normalized["focus"], "默认参数")
        self.assertNotIn("ignoreMe", normalized)
        self.assertEqual(normalized["reference"]["expected"], ["1"])
        self.assertEqual(normalized["reference"]["explain"], "因为定义时求值")
        self.assertNotIn("unknown", normalized["reference"])

    def test_normalize_ai_question_tolerates_garbage(self) -> None:
        normalized = review_content.normalize_ai_question("不是对象")
        self.assertEqual(normalized["prompt"], "")
        self.assertEqual(normalized["reference"]["answer"], [])

    def test_validate_ai_question_requires_type_and_prompt(self) -> None:
        errors = review_content.validate_ai_question(
            {"questionType": "essay", "prompt": ""})
        self.assertTrue(any("题型" in error for error in errors), errors)
        self.assertTrue(any("prompt" in error for error in errors), errors)

    def test_validate_ai_question_requires_reference_when_collecting(self) -> None:
        question = {"questionType": "concept", "prompt": "讲讲机制", "reference": {}}
        self.assertEqual(review_content.validate_ai_question(question), [])
        errors = review_content.validate_ai_question(question, require_reference=True)
        self.assertTrue(any("参考解" in error for error in errors), errors)
        question["reference"] = {"reference": "def f():\n    return 1"}
        self.assertEqual(review_content.validate_ai_question(question, require_reference=True), [])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.test_review_content -v
```

Expected: 4 个新用例 FAIL（`AttributeError: module 'review_content' has no attribute 'normalize_ai_question'`）

- [ ] **Step 3: 实现**

在 `review_content.py` 的 `def load_content_file(` 之前插入：

```python
def normalize_ai_question(value: Any) -> dict[str, Any]:
    """清洗 AI 现场出的题：题面 + （作答后才有）参考解。

    与固定题的关系：`reference` 的键刻意与 `review_storage.reveal()` 返回的字段同名，
    收藏之后前端「看答案」面板不用改就能渲染。
    """
    source = value if isinstance(value, dict) else {}
    raw_reference = source.get("reference") if isinstance(source.get("reference"), dict) else {}
    return {
        "questionType": _text(source.get("questionType")),
        "prompt": _text(source.get("prompt"))[:4000],
        "code": _text(source.get("code"))[:4000],
        "focus": _text(source.get("focus"))[:300],
        "reference": {
            "answer": _text_list(raw_reference.get("answer"))[:12],
            "expected": _text_list(raw_reference.get("expected"))[:12],
            "explain": _text(raw_reference.get("explain"))[:2000],
            "rootCause": _text(raw_reference.get("rootCause"))[:2000],
            "fix": _text(raw_reference.get("fix"))[:2000],
            "reference": _text(raw_reference.get("reference"))[:4000],
            "pitfalls": _text_list(raw_reference.get("pitfalls"))[:12],
        },
    }


def validate_ai_question(question: Any, *, require_reference: bool = False) -> list[str]:
    """AI 题的闸门：题型必须是四种之一、题面必须有 prompt；收藏时参考解至少一项有内容。"""
    errors: list[str] = []
    if not isinstance(question, dict):
        return ["AI 题必须是对象"]
    if _text(question.get("questionType")) not in QUESTION_TYPES:
        errors.append("题型必须是 " + "/".join(QUESTION_TYPES) + " 之一")
    if not _text(question.get("prompt")):
        errors.append("缺少题面 prompt")
    if require_reference:
        reference = question.get("reference") if isinstance(question.get("reference"), dict) else {}
        filled = any(
            _text(reference.get(key)) or _text_list(reference.get(key))
            for key in ("reference", "answer", "expected", "explain")
        )
        if not filled:
            errors.append("参考解至少要有示范解/要点/期望输出/解释之一")
    return errors
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.test_review_content -v
```

Expected: 全部 `ok`

- [ ] **Step 5: 提交**

```bash
git add review_content.py tests/test_review_content.py
git commit -m "feat(review): AI 题的清洗与校验（normalize_ai_question / validate_ai_question）"
```

---

### Task 3: AI 题的存储层（`review_storage.py`）

**Files:**
- Modify: `review_storage.py`（在 `finish_session` 之后追加一节）
- Test: Create `tests/test_review_ai_questions.py`

**Interfaces:**
- Consumes: `review_content.normalize_ai_question` / `validate_ai_question`（Task 2）、`_connection()` / `_now()` / `_json()` / `storage.state_lock()`
- Produces:
  - `review_storage.ai_question_context(code: str) -> dict`（知识点内容 + 最近 5 条作答 + weak/due；`code` 不存在抛 `ValueError("知识点不存在")`）
  - `review_storage.collect_ai_question(code, question_type, prompt, question_code="", focus="", reference=None) -> {"id","code","questionType","createdAt","duplicated"}`
  - `review_storage.list_ai_questions(code: str | None = None) -> list[dict]`（字段：`id/code/questionType/prompt/questionCode/focus/createdAt`，**不含 reference**）
  - `review_storage.read_ai_question(question_id) -> dict | None`（含 `reference`）
  - `review_storage.delete_ai_question(question_id) -> {"code","items"}`（未知 id 抛 `ValueError("AI 题不存在")`）

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_review_ai_questions.py`：

```python
"""AI 加练题（收藏库）的存储层回归：收藏 / 去重 / 列表 / 读取 / 删除 / 出题上下文。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-ai-questions-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")

import review_content  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402

POINT = {
    "code": "py.mutability.default-arg", "title": "可变默认参数与求值时机",
    "minutes": 20, "module": "函数", "level": "基础",
    "taskRefs": [{"taskId": "1103", "relation": "introduces"}],
    "concept": {"prompt": "默认参数什么时候求值？", "answer": ["函数定义时求值一次"]},
    "predict": {"prompt": "写出输出", "code": "print(1)", "expected": ["1"], "explain": "常量"},
    "debug": {"prompt": "找 bug", "code": "x = 1", "rootCause": "无", "fix": "无"},
    "code_task": {"prompt": "写实现", "acceptance": ["能跑"], "reference": "def f(): return 1"},
    "pitfalls": ["默认值是可变对象"],
}
REFERENCE = {"answer": ["定义时求值一次"], "expected": ["[1]", "[1, 2]"],
             "explain": "两次调用共享同一个列表",
             "reference": "def f(items=None):\n    items = [] if items is None else items"}


class AiQuestionStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_point_tasks")
            connection.execute("DELETE FROM review_attempts")
            connection.execute("DELETE FROM review_states")
            connection.execute("DELETE FROM review_ai_questions")
        review_storage.import_content([POINT], week=1)

    def _collect(self, prompt: str = "现场出的题：写出 f() 两次调用的输出",
                 kind: str = "predict") -> dict:
        return review_storage.collect_ai_question(
            POINT["code"], kind, prompt, "def f(items=[]):\n    items.append(1)\n    return items",
            "可变默认参数", dict(REFERENCE))

    def test_collect_then_list_without_reference(self) -> None:
        saved = self._collect()
        self.assertFalse(saved["duplicated"])
        items = review_storage.list_ai_questions(POINT["code"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], saved["id"])
        self.assertEqual(items[0]["questionType"], "predict")
        self.assertEqual(items[0]["focus"], "可变默认参数")
        self.assertNotIn("reference", items[0], "列表不能吐参考答案")
        self.assertNotIn("reference", items[0].get("content_json", ""), items[0])

    def test_collect_is_idempotent_for_identical_question(self) -> None:
        first = self._collect()
        second = self._collect()
        self.assertTrue(second["duplicated"])
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(len(review_storage.list_ai_questions(POINT["code"])), 1)

    def test_collect_rejects_unknown_point_and_empty_reference(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            review_storage.collect_ai_question("py.nope.nope", "predict", "题面", "", "", dict(REFERENCE))
        self.assertIn("知识点不存在", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx2:
            review_storage.collect_ai_question(POINT["code"], "predict", "题面", "", "", {})
        self.assertIn("参考解", str(ctx2.exception))

    def test_read_and_delete_question(self) -> None:
        saved = self._collect()
        stored = review_storage.read_ai_question(saved["id"])
        self.assertEqual(stored["prompt"], "现场出的题：写出 f() 两次调用的输出")
        self.assertEqual(stored["reference"]["expected"], ["[1]", "[1, 2]"])
        self.assertIsNone(review_storage.read_ai_question("no-such-id"))
        result = review_storage.delete_ai_question(saved["id"])
        self.assertEqual(result["code"], POINT["code"])
        self.assertEqual(result["items"], [])
        self.assertIsNone(review_storage.read_ai_question(saved["id"]))
        with self.assertRaises(ValueError) as ctx:
            review_storage.delete_ai_question("no-such-id")
        self.assertIn("不存在", str(ctx.exception))

    def test_list_all_when_code_omitted(self) -> None:
        self._collect("第一题")
        self._collect("第二题")
        self.assertEqual(len(review_storage.list_ai_questions()), 2)
        self.assertEqual(len(review_storage.list_ai_questions(POINT["code"])), 2)

    def test_context_carries_point_prompts_and_recent_history(self) -> None:
        review_storage.apply_grade(POINT["code"], "concept", 2, today="2026-09-19",
                                   answer="我答错了")
        # 注意：`weak` 不是"答过一次 2 分"就会有 —— 现有语义要求 lapses≥WEAK_LAPSES(2)
        # 或显式 mark_weak（见 review_storage.mark_weak 的说明）。这里显式标弱，
        # 才能同时覆盖"最近作答"与"薄弱标记"两条上下文来源。
        review_storage.mark_weak([POINT["code"]])
        context = review_storage.ai_question_context(POINT["code"])
        self.assertEqual(context["title"], POINT["title"])
        self.assertEqual(context["module"], "函数")
        self.assertEqual(context["pitfalls"], ["默认值是可变对象"])
        self.assertTrue(context["existingPrompts"]["concept"], "要带上现有题面做风格参考")
        self.assertNotIn("answer", context["existingPrompts"], "上下文不能泄露参考答案")
        self.assertEqual(len(context["history"]), 1)
        self.assertEqual(context["history"][0]["questionType"], "concept")
        self.assertEqual(context["history"][0]["grade"], 2)
        self.assertEqual(context["history"][0]["answer"], "我答错了")
        self.assertTrue(context["weak"])

    def test_context_rejects_unknown_code(self) -> None:
        with self.assertRaises(ValueError):
            review_storage.ai_question_context("py.nope.nope")

    def test_collect_dispatches_reference_through_validator(self) -> None:
        errors = review_content.validate_ai_question(
            review_content.normalize_ai_question({"questionType": "predict", "prompt": "x"}),
            require_reference=True)
        self.assertTrue(errors, "没有参考解时必须被闸门拦住")


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    _TEMP.cleanup()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.test_review_ai_questions -v
```

Expected: `AttributeError: module 'review_storage' has no attribute 'collect_ai_question'`

- [ ] **Step 3: 实现**

在 `review_storage.py` 的 `def finish_session(` **之前**插入（`uuid` / `json` / `storage` 已在文件顶部导入）：

```python
# ---------- AI 现场出题（临时加练 + 收藏库） ----------

AI_QUESTION_HISTORY_LIMIT = 5


def ai_question_context(code: str) -> dict[str, Any]:
    """出题上下文：知识点内容（含四种题型的"题面"，**不含答案**）+ 最近 5 条作答 + 薄弱标记。"""
    with _connection() as connection:
        point = connection.execute(
            "SELECT title,content_json,module,level,minutes FROM review_points WHERE code=?",
            (str(code),)).fetchone()
        if point is None:
            raise ValueError("知识点不存在")
        rows = connection.execute(
            "SELECT question_type,grade,answer,reviewed_on FROM review_attempts "
            "WHERE code=? ORDER BY created_at DESC LIMIT ?",
            (str(code), AI_QUESTION_HISTORY_LIMIT)).fetchall()
        state = connection.execute(
            "SELECT due,weak FROM review_states WHERE code=?", (str(code),)).fetchone()
    content = json.loads(point["content_json"])
    prompts = {
        kind: str((content.get(kind) or {}).get("prompt") or "").strip()
        for kind in review_content.QUESTION_TYPES
    }
    return {
        "code": str(code), "title": point["title"], "module": point["module"],
        "level": point["level"], "minutes": int(point["minutes"]),
        "pitfalls": [str(item) for item in (content.get("pitfalls") or [])],
        "existingPrompts": prompts,
        "weak": bool(state["weak"]) if state else False,
        "due": str(state["due"]) if state else "",
        "history": [{"questionType": str(row["question_type"]), "grade": int(row["grade"]),
                     "answer": str(row["answer"])[:200], "reviewedOn": str(row["reviewed_on"])}
                    for row in rows],
    }


def collect_ai_question(code: str, question_type: str, prompt: str, question_code: str = "",
                        focus: str = "", reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """把 AI 现场出的题收进题库：校验 → 规范化 → 落库（完全相同的题复用已有行，防连点重复）。"""
    question = review_content.normalize_ai_question({
        "questionType": question_type, "prompt": prompt, "code": question_code,
        "focus": focus, "reference": reference or {},
    })
    errors = review_content.validate_ai_question(question, require_reference=True)
    if errors:
        raise ValueError("AI 题不合法：" + "；".join(errors[:3]))
    payload = _json(question)
    stamp = _now()
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM review_points WHERE code=?", (str(code),)).fetchone() is None:
            raise ValueError("知识点不存在")
        existing = connection.execute(
            "SELECT question_id,created_at FROM review_ai_questions WHERE code=? AND content_json=?",
            (str(code), payload)).fetchone()
        if existing is not None:
            return {"id": str(existing["question_id"]), "code": str(code),
                    "questionType": question["questionType"],
                    "createdAt": str(existing["created_at"]), "duplicated": True}
        question_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO review_ai_questions(question_id,code,question_type,content_json,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (question_id, str(code), question["questionType"], payload, stamp, stamp))
    return {"id": question_id, "code": str(code), "questionType": question["questionType"],
            "createdAt": stamp, "duplicated": False}


def list_ai_questions(code: str | None = None) -> list[dict[str, Any]]:
    """已收藏的 AI 题：只给题面与考察点，参考答案走 reveal（列表绝不吐 reference）。"""
    sql = ("SELECT question_id,code,question_type,content_json,created_at "
           "FROM review_ai_questions")
    params: tuple[Any, ...] = ()
    if code:
        sql += " WHERE code=?"
        params = (str(code),)
    sql += " ORDER BY created_at,question_id"
    items: list[dict[str, Any]] = []
    with _connection() as connection:
        for row in connection.execute(sql, params):
            content = json.loads(row["content_json"])
            items.append({"id": str(row["question_id"]), "code": str(row["code"]),
                          "questionType": str(row["question_type"]),
                          "prompt": str(content.get("prompt") or ""),
                          "questionCode": str(content.get("code") or ""),
                          "focus": str(content.get("focus") or ""),
                          "createdAt": str(row["created_at"])})
    return items


def read_ai_question(question_id: Any) -> dict[str, Any] | None:
    """读一道收藏题的完整内容（含 reference）；不存在返回 None。"""
    with _connection() as connection:
        row = connection.execute(
            "SELECT question_id,code,question_type,content_json,created_at "
            "FROM review_ai_questions WHERE question_id=?", (str(question_id),)).fetchone()
    if row is None:
        return None
    content = json.loads(row["content_json"])
    return {"id": str(row["question_id"]), "code": str(row["code"]),
            "questionType": str(row["question_type"]), "createdAt": str(row["created_at"]),
            **content}


def delete_ai_question(question_id: Any) -> dict[str, Any]:
    """删除一道收藏题，返回 {code, items}（该点删除后的剩余列表）；未知 id 抛 ValueError。"""
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT code FROM review_ai_questions WHERE question_id=?",
                                 (str(question_id),)).fetchone()
        if row is None:
            raise ValueError("AI 题不存在")
        code = str(row["code"])
        connection.execute("DELETE FROM review_ai_questions WHERE question_id=?",
                           (str(question_id),))
    return {"code": code, "items": list_ai_questions(code)}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.test_review_ai_questions -v
```

Expected: 8 个用例全部 `ok`

- [ ] **Step 5: 提交**

```bash
git add review_storage.py tests/test_review_ai_questions.py
git commit -m "feat(review): AI 题的收藏/列表/读取/删除与出题上下文"
```

---

### Task 4: 出题与批改的 AI 层（`prompts.py` + `ai_service.py`）

**Files:**
- Modify: `prompts.py`（在 `QUESTION_PROMPT` 之后追加两个提示词）
- Modify: `ai_service.py`（在 `grade_review_answer` 之后追加两个函数与两个 mock）
- Test: Create `tests/test_ai_review_questions.py`

**Interfaces:**
- Consumes: Task 3 的 `ai_question_context` 输出形状、Task 2 的清洗/校验、现有 `_post_json` / `_mock_enabled` / `read_settings` / `model_aliases` / `string_list`
- Produces:
  - `ai_service.is_configured() -> bool`（已存在，端点用它判 503）
  - `ai_service.generate_ai_question(*, context: dict, question_type: str = "") -> {"questionType","prompt","code","focus"}`
  - `ai_service.review_ai_answer(*, context: dict, question: dict, answer: str) -> {"verdict": {"correct","summary","missing","wrongAt","hint"}, "focus", "reference"}`

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_ai_review_questions.py`：

```python
"""AI 出题 / 批改层：mock 通道、结构校验、失败可读化（全部离线，不发真实请求）。"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import ai_service  # noqa: E402
import review_content  # noqa: E402

CONTEXT = {
    "code": "py.mutability.default-arg", "title": "可变默认参数与求值时机",
    "module": "函数", "level": "基础", "minutes": 20,
    "pitfalls": ["默认值是可变对象"],
    "existingPrompts": {"concept": "默认参数什么时候求值？", "predict": "写出输出",
                        "debug": "找 bug", "code_task": "写实现"},
    "weak": True, "due": "2026-09-19",
    "history": [{"questionType": "concept", "grade": 2, "answer": "答错了", "reviewedOn": "2026-09-18"}],
}


def good_question() -> dict:
    return {"questionType": "predict", "prompt": "写出两次调用的输出",
            "code": "def f(items=[]):\n    items.append(1)\n    return items",
            "focus": "默认参数的求值时机"}


def good_verdict() -> dict:
    return {"verdict": {"correct": False, "summary": "机制说反了",
                        "missing": ["定义时求值一次"], "wrongAt": "把共享说成每次新建",
                        "hint": "想想默认值在何时创建"},
            "focus": "默认参数的求值时机",
            "reference": {"answer": ["定义时求值一次"], "expected": ["[1]", "[1, 2]"],
                          "explain": "两次调用共享同一个列表",
                          "reference": "def f(items=None):\n    items = [] if items is None else items"}}

class AiGenerateQuestionTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TODO_AI_MOCK"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("TODO_AI_MOCK", None)

    def test_mock_mode_returns_renderable_question(self) -> None:
        question = ai_service.generate_ai_question(context=CONTEXT)
        self.assertEqual(review_content.validate_ai_question(question), [])
        self.assertIn(question["questionType"], review_content.QUESTION_TYPES)
        self.assertTrue(question["prompt"])
        self.assertTrue(question["code"], "mock 也要给可运行的代码片段")
        self.assertIn("默认参数", question["focus"])

    def test_mock_mode_honours_explicit_type(self) -> None:
        question = ai_service.generate_ai_question(context=CONTEXT, question_type="debug")
        self.assertEqual(question["questionType"], "debug")

    def test_structure_failure_raises_readable_error(self) -> None:
        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": ""}, clear=False), \
                mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=False), \
                mock.patch.object(ai_service, "_post_json",
                                  return_value={"questionType": "essay", "prompt": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                ai_service.generate_ai_question(context=CONTEXT)
        self.assertIn("不合规", str(ctx.exception))

    def test_real_branch_passes_context_without_answers(self) -> None:
        captured = {}

        def fake_post(settings, body, **kwargs):
            captured["body"] = body
            return good_question()

        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": "", "DEEPSEEK_API_KEY": "test-key"},
                             clear=False), \
                mock.patch.object(ai_service, "_post_json", side_effect=fake_post):
            question = ai_service.generate_ai_question(context=CONTEXT)
        self.assertEqual(question["questionType"], "predict")
        user_payload = json.loads(captured["body"]["messages"][1]["content"])
        self.assertEqual(user_payload["知识点"], CONTEXT["title"])
        self.assertIn("concept", user_payload["现有题面（风格参考，请勿重复）"])
        self.assertEqual(user_payload["最近作答"][0]["grade"], 2)
        self.assertTrue(user_payload["薄弱"])
        self.assertNotIn("answer", user_payload["现有题面（风格参考，请勿重复）"],
                         "风格参考只给题面，不能带上参考答案")


class AiReviewAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TODO_AI_MOCK"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("TODO_AI_MOCK", None)

    def test_mock_verdict_contains_demo_solution(self) -> None:
        result = ai_service.review_ai_answer(context=CONTEXT, question=good_question(), answer="")
        self.assertFalse(result["verdict"]["correct"], "空作答不能算对")
        self.assertTrue(result["verdict"]["missing"])
        errors = review_content.validate_ai_question(
            {"questionType": "predict", "prompt": "x", "reference": result["reference"]},
            require_reference=True)
        self.assertEqual(errors, [], "示范解法必须能直接用于收藏")

    def test_mock_verdict_marks_non_empty_answer_correct(self) -> None:
        result = ai_service.review_ai_answer(context=CONTEXT, question=good_question(),
                                             answer="默认参数在定义时求值一次")
        self.assertTrue(result["verdict"]["correct"])

    def test_real_branch_normalizes_and_requires_demo(self) -> None:
        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": "", "DEEPSEEK_API_KEY": "test-key"},
                             clear=False), \
                mock.patch.object(ai_service, "_post_json", return_value=good_verdict()):
            result = ai_service.review_ai_answer(context=CONTEXT, question=good_question(),
                                                 answer="我的答案")
        self.assertEqual(result["verdict"]["missing"], ["定义时求值一次"])
        self.assertEqual(result["reference"]["expected"], ["[1]", "[1, 2]"])
        self.assertEqual(result["focus"], "默认参数的求值时机")

    def test_real_branch_without_demo_raises_readable_error(self) -> None:
        broken = {"verdict": {"correct": True}, "focus": "x", "reference": {}}
        with mock.patch.dict(os.environ, {"TODO_AI_MOCK": "", "DEEPSEEK_API_KEY": "test-key"},
                             clear=False), \
                mock.patch.object(ai_service, "_post_json", return_value=broken):
            with self.assertRaises(RuntimeError) as ctx:
                ai_service.review_ai_answer(context=CONTEXT, question=good_question(), answer="x")
        self.assertIn("不合规", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.test_ai_review_questions -v
```

Expected: `AttributeError: module 'ai_service' has no attribute 'generate_ai_question'`

- [ ] **Step 3: 加两个提示词**

在 `prompts.py` 的 `QUESTION_PROMPT` 之后追加：

```python
REVIEW_AI_QUESTION_PROMPT = """\
你是带练教练。学习者正在复习一个 Python 知识点，请就**这一个点**现场出一道新题，逼出因果理解。

出题要求：
1. 只考这个知识点本身，不要跨到别的主题；题目不要与"现有题面"重复（它们已经做过）。
2. 优先给真实的、可运行的代码片段（含陷阱/边界），让学习者预测输出、解释机制、定位 bug 或写实现。
3. 若给了"最近作答"，针对他答错/含糊的地方出题；没给就按知识点本身出。
4. 代码一律放进以 python 标注的 markdown 代码围栏，严格保留 4 空格缩进，禁止压成一行。
5. 难度贴合该知识点的层级：基础=能跑通并说清机制，实用=能处理边界，进阶=能设计验证或改错。
6. **不要给出答案、不要给提示、不要给参考实现** —— 学习者要先自己答。

只返回 JSON 对象：{"questionType":"concept|predict|debug|code_task 之一","prompt":"题面","code":"要预测/排查的代码，不需要代码时给空串","focus":"考察点一句话"}
"""

REVIEW_AI_ANSWER_PROMPT = """\
你是批改教练。学习者刚做了一道现场出的题，请批改并给出示范解法。

批改要求：
1. 先判对错：`correct` 只有在核心机制都说到/做到时才是 true；沾边不算对。
2. `missing` 列出缺少的关键点（每条一句话）；`wrongAt` 指出答错的具体位置（没有就给空串）；
   `hint` 给一句怎么补（不要说教）。
3. 必须给示范解法：`reference.reference` 是可运行的参考实现或完整解题步骤（放 python 围栏、4 空格缩进）；
   `reference.answer` 给要点清单；`reference.expected` 给期望输出（有输出才给）；
   `reference.explain` 讲清为什么；如果是找错题，再给 `reference.rootCause` 与 `reference.fix`。
4. 学习者的作答可能是空的或写着"我不会"：这时 `correct=false`、`missing` 说明没作答，
   **照样给出完整示范解法**，让他能照着学。
5. 不要重复题目、不要输出与 JSON 无关的文字。

只返回 JSON 对象：{"verdict":{"correct":true|false,"summary":"一句总评","missing":[],"wrongAt":"","hint":""},"focus":"考察点一句话","reference":{"answer":[],"expected":[],"explain":"","rootCause":"","fix":"","reference":"","pitfalls":[]}}
"""
```

在 `ai_service.py` 顶部的 `from prompts import (` 括号里补上两个新名字（保持字母序无关，与现有排列一致即可）：

```python
    REVIEW_AI_ANSWER_PROMPT,
    REVIEW_AI_QUESTION_PROMPT,
```

- [ ] **Step 4: 实现两个函数与两个 mock**

在 `ai_service.py` 的 `def call_question(` **之前**插入：

```python
def _mock_ai_question(context: dict[str, Any], question_type: str) -> dict[str, Any]:
    kind = question_type if question_type in review_content.QUESTION_TYPES else "predict"
    title = str(context.get("title") or "当前知识点")
    return {"questionType": kind,
            "prompt": f"（模拟出题）针对「{title}」写出下面代码两次调用的输出，并说明原因",
            "code": "def collect(item, items=[]):\n    items.append(item)\n    return items\n\n"
                    "print(collect(1))\nprint(collect(2))",
            "focus": "可变默认参数在定义时求值一次"}


def _mock_ai_verdict(question: dict[str, Any], answer: str) -> dict[str, Any]:
    answered = bool(str(answer).strip())
    return {
        "verdict": {
            "correct": answered,
            "summary": "（模拟批改）核心机制说清了" if answered else "（模拟批改）这次没有作答",
            "missing": [] if answered else ["没有写出内容"],
            "wrongAt": "",
            "hint": "对照示范解法看：默认值在函数定义时创建一次，之后所有调用共享它",
        },
        "focus": str(question.get("focus") or "可变默认参数在定义时求值一次"),
        "reference": {
            "answer": ["默认参数在函数定义时求值一次", "可变默认值会被所有调用共享"],
            "expected": ["[1]", "[1, 2]"],
            "explain": "两次调用复用同一个列表对象，所以第二次看到上一次的结果",
            "rootCause": "", "fix": "",
            "reference": "def collect(item, items=None):\n    items = [] if items is None else items\n"
                         "    items.append(item)\n    return items",
            "pitfalls": ["把默认值当成每次新建", "在调用侧共享同一个列表"],
        },
    }


def generate_ai_question(*, context: dict[str, Any], question_type: str = "") -> dict[str, Any]:
    """现场出一道新题（**只出题面**）。结构不合格抛可读 RuntimeError，绝不吐半成品。"""
    if _mock_enabled():
        return _mock_ai_question(context, question_type)
    settings = read_settings()
    user_payload = {
        "知识点": str(context.get("title") or ""),
        "模块": str(context.get("module") or ""),
        "层级": str(context.get("level") or ""),
        "易错点": context.get("pitfalls") or [],
        "现有题面（风格参考，请勿重复）": context.get("existingPrompts") or {},
        "最近作答": context.get("history") or [],
        "薄弱": bool(context.get("weak")),
        "指定题型": question_type or "由你决定",
    }
    request_body = {
        "model": model_aliases(settings).get("flash", "deepseek-chat"),
        "temperature": 0.6,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": REVIEW_AI_QUESTION_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    parsed = _post_json(settings, request_body)
    question = review_content.normalize_ai_question(parsed)
    errors = review_content.validate_ai_question(question)
    if errors:
        raise RuntimeError("AI 出的题不合规：" + "；".join(errors[:3]))
    return {"questionType": question["questionType"], "prompt": question["prompt"],
            "code": question["code"], "focus": question["focus"]}


def review_ai_answer(*, context: dict[str, Any], question: dict[str, Any],
                     answer: str) -> dict[str, Any]:
    """批改 AI 题的作答：返回 {verdict, focus, reference}；作答可以是空的（照样给示范解法）。"""
    if _mock_enabled():
        return _mock_ai_verdict(question, answer)
    settings = read_settings()
    user_payload = {
        "知识点": str(context.get("title") or ""),
        "模块": str(context.get("module") or ""),
        "层级": str(context.get("level") or ""),
        "题面": str(question.get("prompt") or ""),
        "题面代码": str(question.get("code") or ""),
        "考察点": str(question.get("focus") or ""),
        "我的作答": str(answer or "")[:8000],
    }
    request_body = {
        "model": model_aliases(settings).get("flash", "deepseek-chat"),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": REVIEW_AI_ANSWER_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    parsed = _post_json(settings, request_body)
    raw_verdict = parsed.get("verdict") if isinstance(parsed.get("verdict"), dict) else {}
    normalized = review_content.normalize_ai_question({
        "questionType": question.get("questionType"), "prompt": question.get("prompt"),
        "code": question.get("code"), "focus": parsed.get("focus") or question.get("focus"),
        "reference": parsed.get("reference"),
    })
    errors = review_content.validate_ai_question(normalized, require_reference=True)
    if errors:
        raise RuntimeError("AI 批改结果不合规：" + "；".join(errors[:3]))
    return {
        "verdict": {"correct": raw_verdict.get("correct") is True,
                    "summary": str(raw_verdict.get("summary") or "")[:1000],
                    "missing": string_list(raw_verdict.get("missing")),
                    "wrongAt": str(raw_verdict.get("wrongAt") or "")[:1000],
                    "hint": str(raw_verdict.get("hint") or "")[:1000]},
        "focus": normalized["focus"],
        "reference": normalized["reference"],
    }
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python3 -m unittest tests.test_ai_review_questions tests.test_ai_service -v
```

Expected: 新用例全 `ok`，`tests.test_ai_service` 不回归

- [ ] **Step 6: 提交**

```bash
git add prompts.py ai_service.py tests/test_ai_review_questions.py
git commit -m "feat(review): AI 现场出题与批改（含 mock 与结构闸门）"
```

---

### Task 5: 5 个 HTTP 端点（`local_server.py`）

**Files:**
- Modify: `local_server.py`（GET 复习块、POST 白名单 + 三个分支、DELETE 白名单 + 一个分支）
- Test: `tests/test_review_http.py`（在 `ReviewHttpTests` 之后新增 `ReviewAiQuestionHttpTests` 类）

**Interfaces:**
- Consumes: `review_storage.ai_question_context / collect_ai_question / list_ai_questions / delete_ai_question`（Task 3）、`ai_service.generate_ai_question / review_ai_answer / is_configured`（Task 4）
- Produces: `GET /api/review/ai-questions?code=`、`POST /api/review/ai-question|ai-answer|ai-collect`、`DELETE /api/review/ai-question?id=`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_review_http.py` 的 `ReviewBootstrapTests` **之前**插入（`MIN_POINTS` / `MUTABLE_DEFAULT` 常量已存在）：

```python
class ReviewAiQuestionHttpTests(unittest.TestCase):
    """AI 加练题的 HTTP 契约：收藏/列表/删除 200；参数非法 400；未知 id 404；未配置 AI 503；
    AI 层失败 502（可读错误，不是"未预期错误"）。"""

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

    def setUp(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_ai_questions")

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

    def collect(self, prompt: str = "现场题：写出两次调用的输出") -> dict:
        status, payload = self.call("/api/review/ai-collect", "POST", {
            "code": MUTABLE_DEFAULT, "questionType": "predict", "prompt": prompt,
            "questionCode": "def f(items=[]):\n    return items",
            "focus": "默认参数求值时机",
            "reference": {"expected": ["[1]"], "explain": "定义时求值一次",
                          "reference": "def f(items=None):\n    return items"},
        })
        self.assertEqual(status, 200, payload)
        return payload["question"]

    def test_collect_then_list_then_delete(self) -> None:
        saved = self.collect()
        status, payload = self.call(f"/api/review/ai-questions?code={MUTABLE_DEFAULT}")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in payload["items"]], [saved["id"]])
        self.assertNotIn("reference", payload["items"][0])
        status, all_items = self.call("/api/review/ai-questions")
        self.assertEqual(status, 200)
        self.assertEqual(len(all_items["items"]), 1, "不传 code 要返回全部（知识点页一次拉取）")
        status, payload = self.call(f"/api/review/ai-question?id={saved['id']}", "DELETE")
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["code"], MUTABLE_DEFAULT)
        self.assertEqual(payload["items"], [])
        status, second = self.call(f"/api/review/ai-question?id={saved['id']}", "DELETE")
        self.assertEqual(status, 404, second)

    def test_collect_rejects_bad_payload_with_400(self) -> None:
        status, payload = self.call("/api/review/ai-collect", "POST", {
            "code": "py.nope.nope", "questionType": "predict", "prompt": "x",
            "reference": {"explain": "y"}})
        self.assertEqual(status, 400, payload)
        self.assertIn("知识点不存在", payload["error"])
        status, payload = self.call("/api/review/ai-collect", "POST", {
            "code": MUTABLE_DEFAULT, "questionType": "essay", "prompt": "x",
            "reference": {"explain": "y"}})
        self.assertEqual(status, 400, payload)
        self.assertIn("题型", payload["error"])

    def test_generate_and_answer_report_503_without_ai(self) -> None:
        with mock.patch.object(ai_service, "is_configured", return_value=False):
            status, payload = self.call("/api/review/ai-question", "POST", {"code": MUTABLE_DEFAULT})
            self.assertEqual(status, 503, payload)
            self.assertIn("未配置 AI", payload["error"])
            status, payload = self.call("/api/review/ai-answer", "POST", {
                "code": MUTABLE_DEFAULT, "questionType": "predict", "prompt": "x", "answer": ""})
            self.assertEqual(status, 503, payload)

    def test_generate_returns_question_without_reference(self) -> None:
        with mock.patch.object(ai_service, "is_configured", return_value=True), \
                mock.patch.object(ai_service, "generate_ai_question", return_value={
                    "questionType": "predict", "prompt": "现场题", "code": "print(1)",
                    "focus": "求值时机"}):
            status, payload = self.call("/api/review/ai-question", "POST", {"code": MUTABLE_DEFAULT})
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["question"]["prompt"], "现场题")
        self.assertNotIn("reference", payload["question"], "出题阶段不能有答案")

    def test_answer_returns_verdict_and_demo(self) -> None:
        with mock.patch.object(ai_service, "is_configured", return_value=True), \
                mock.patch.object(ai_service, "review_ai_answer", return_value={
                    "verdict": {"correct": True, "summary": "不错", "missing": [],
                                "wrongAt": "", "hint": ""},
                    "focus": "求值时机",
                    "reference": {"reference": "def f(items=None): ...", "expected": ["[1]"]}}):
            status, payload = self.call("/api/review/ai-answer", "POST", {
                "code": MUTABLE_DEFAULT, "questionType": "predict", "prompt": "现场题",
                "questionCode": "", "focus": "求值时机", "answer": "我的答案"})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["verdict"]["correct"])
        self.assertIn("reference", payload["reference"])

    def test_ai_failure_becomes_502_with_readable_error(self) -> None:
        with mock.patch.object(ai_service, "is_configured", return_value=True), \
                mock.patch.object(ai_service, "generate_ai_question",
                                  side_effect=RuntimeError("DeepSeek API 返回 429: rate limit")):
            status, payload = self.call("/api/review/ai-question", "POST", {"code": MUTABLE_DEFAULT})
        self.assertEqual(status, 502, payload)
        self.assertIn("429", payload["error"])
```

同文件顶部的 import 区补一个 `import ai_service`（放在 `import local_server` 上方）：

```python
import ai_service  # noqa: E402
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.test_review_http.ReviewAiQuestionHttpTests -v
```

Expected: 全部 FAIL（`/api/review/ai-collect` 返回 404 `接口不存在`）

- [ ] **Step 3: 实现 GET / POST / DELETE 三处**

(a) GET：在 `local_server.py` 的 `if path == "/api/review/history":` 分支之后、`except ValueError` 之前插入：

```python
                if path == "/api/review/ai-questions":
                    code = (params.get("code", [""])[0] or "").strip()
                    self.send_json(200, {"items": review_storage.list_ai_questions(code or None)})
                    return
```

(b) POST 白名单：在 `"/api/review/generate", "/api/review/ai-grade"}:` 这一行改成：

```python
                        "/api/review/generate", "/api/review/ai-grade",
                        "/api/review/ai-question", "/api/review/ai-answer", "/api/review/ai-collect"}:
```

(c) POST 分支：在 `elif path == "/api/review/ai-grade":` 分支之后插入：

```python
            elif path == "/api/review/ai-question":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("questionType") or "").strip()
                if kind and kind not in review_content.QUESTION_TYPES:
                    raise ValueError("题型不正确")
                if not ai_service.is_configured():
                    self.send_json(503, {"error": "未配置 AI，出题不可用（复习本身不受影响）"})
                    return
                try:
                    question = ai_service.generate_ai_question(
                        context=review_storage.ai_question_context(code), question_type=kind)
                except RuntimeError as error:
                    self.send_json(502, {"error": f"AI 出题失败：{error}"})
                    return
                self.send_json(200, {"ok": True, "question": question})
            elif path == "/api/review/ai-answer":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("questionType") or "").strip()
                if kind not in review_content.QUESTION_TYPES:
                    raise ValueError("题型不正确")
                if not ai_service.is_configured():
                    self.send_json(503, {"error": "未配置 AI，批改不可用（复习本身不受影响）"})
                    return
                try:
                    result = ai_service.review_ai_answer(
                        context=review_storage.ai_question_context(code),
                        question={"questionType": kind, "prompt": payload.get("prompt"),
                                  "code": payload.get("questionCode"),
                                  "focus": payload.get("focus")},
                        answer=str(payload.get("answer") or ""))
                except RuntimeError as error:
                    self.send_json(502, {"error": f"AI 批改失败：{error}"})
                    return
                self.send_json(200, {"ok": True, **result})
            elif path == "/api/review/ai-collect":
                question = review_storage.collect_ai_question(
                    str(payload.get("code") or "").strip(),
                    str(payload.get("questionType") or "").strip(),
                    str(payload.get("prompt") or ""),
                    str(payload.get("questionCode") or ""),
                    str(payload.get("focus") or ""),
                    payload.get("reference") if isinstance(payload.get("reference"), dict) else {})
                self.send_json(200, {"ok": True, "question": question})
```

(d) DELETE 白名单与分支：把 `if path not in {"/api/project", "/api/memo"}:` 改成：

```python
        if path not in {"/api/project", "/api/memo", "/api/review/ai-question"}:
```

并在 `/api/memo` 分支之后插入：

```python
            if path == "/api/review/ai-question":
                question_id = required_param(params, "id")
                try:
                    result = review_storage.delete_ai_question(question_id)
                except ValueError as error:
                    # 未知 id → 404；不能落进下面通用的 ValueError→400 分支
                    self.send_json(404, {"error": str(error)})
                    return
                self.send_json(200, {"ok": True, **result})
                return
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.test_review_http -v
```

Expected: 全部 `ok`（新类 6 个用例 + 原有用例不回归）

- [ ] **Step 5: 提交**

```bash
git add local_server.py tests/test_review_http.py
git commit -m "feat(review): AI 加练的 5 个 HTTP 端点（出题/批改/收藏/列表/删除）"
```

---

### Task 6: 前端 · 复习卡片入口（状态机 + 动态渲染器）

**Files:**
- Modify: `index.html`（复习卡片：加容器与按钮；`app.js?v=`）
- Modify: `js/app.js`（元素引用、状态、渲染器与四个动作）
- Modify: `css/style.css`（`.ai-badge` / `.review-ai-*`；`style.css?v=`）
- Test: `tests/frontend/dom-smoke.js`（新端点桩 + 卡片流程断言）

**Interfaces:**
- Consumes: Task 5 的四个端点
- Produces（后续 Task 7 复用）：
  - `aiPractice` 状态对象：`{surface, code, title, question, verdict, reference, collected, busy, answer, container}`
  - `renderAiVerdict(container, verdict, reference)` — 判分 + 示范解法共用渲染
  - `startAiPractice(code, container, title)` / `submitAiPracticeAnswer()` / `collectAiPracticeQuestion()` / `discardAiPractice()` / `retryAiPractice()`
  - `renderAiPractice()` — 按 `aiPractice.container` 动态渲染整块 UI

- [ ] **Step 1: 写失败的测试（DOM 桩）**

在 `tests/frontend/dom-smoke.js` 的 review 桩之后（`if (path === '/api/review/session')` 附近）加入：

```js
    // AI 加练：出题（无答案）→ 批改（判分 + 示范解法）→ 收藏。
    if (path === '/api/review/ai-question') {
        if (options.body) {
            try { reviewAiQuestionBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
        }
        return reply(200, { ok: true, question: {
            questionType: 'predict', prompt: '（AI 出的）写出两次调用的输出',
            code: 'def f(items=[]):\n    items.append(1)\n    return items',
            focus: '默认参数在定义时求值一次' } });
    }
    if (path === '/api/review/ai-answer') {
        if (options.body) {
            try { reviewAiAnswerBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
        }
        return reply(200, { ok: true,
            verdict: { correct: false, summary: '机制说反了', missing: ['定义时求值一次'],
                wrongAt: '把共享说成每次新建', hint: '想想默认值何时创建' },
            focus: '默认参数在定义时求值一次',
            reference: { answer: ['定义时求值一次'], expected: ['[1]', '[1, 2]'],
                explain: '两次调用共享同一个列表', rootCause: '', fix: '',
                reference: 'def f(items=None):\n    items = [] if items is None else items',
                pitfalls: ['把默认值当成每次新建'] } });
    }
    if (path === '/api/review/ai-collect') {
        if (options.body) {
            try { reviewAiCollectBodies.push(JSON.parse(options.body)); } catch (error) { fetchLog.push('BAD-BODY'); }
        }
        return reply(200, { ok: true, question: { id: 'ai-q-1', code: 'py.a.b',
            questionType: 'predict', createdAt: '2026-09-19T10:00:00', duplicated: false } });
    }
    if (path === '/api/review/ai-questions') {
        aiQuestionsFixture.forEach(entry => {});
        return reply(200, { items: aiQuestionsFixture });
    }
```

并在文件顶部的桩状态区（`let aiGradeUnavailable = false;` 附近）声明：

```js
// AI 加练：请求体留证 + 收藏列表夹具（知识点页徽标用）。
const reviewAiQuestionBodies = [];
const reviewAiAnswerBodies = [];
const reviewAiCollectBodies = [];
let aiQuestionsFixture = [];
```

在 `(async () => {` 主流程里，**复习会话流程用例之后**插入：

```js
    // ⑮ AI 加练：出题 → 批改 → 收藏（临时加练不写复习状态，前端也不该隐藏"放弃"）
    const aiQuestionBefore = fetchLog.length;
    elementsById.get('reviewAiQuestionBtn').dispatch('click');
    await sleep(60);
    check('AI 出题发出了 /api/review/ai-question 且带 code',
        fetchLog.slice(aiQuestionBefore).includes('POST /api/review/ai-question')
        && reviewAiQuestionBodies.slice(-1)[0]?.code === 'py.a.b',
        JSON.stringify({ log: fetchLog.slice(-3), body: reviewAiQuestionBodies.slice(-1)[0] }));
    const practiceText = textOf(elementsById.get('reviewAiPractice'));
    check('加练模式显示 AI 题面与考察点，并藏起固定题的「看答案」',
        practiceText.includes('（AI 出的）写出两次调用的输出')
        && practiceText.includes('默认参数在定义时求值一次')
        && elementsById.get('reviewRevealBtn').hidden === true
        && elementsById.get('reviewAiPractice').hidden === false,
        practiceText.slice(0, 200));
    const aiTextarea = findAll(elementsById.get('reviewAiPractice'), el => el._tag === 'textarea')[0];
    if (aiTextarea) aiTextarea.value = '默认参数在函数定义时求值一次';
    const submitBtn = findAll(elementsById.get('reviewAiPractice'), el => el.textContent === '提交给 AI 批改')[0];
    if (submitBtn) step('点击「提交给 AI 批改」不抛异常', () => submitBtn.dispatch('click'));
    await sleep(80);
    const verdictText = textOf(elementsById.get('reviewAiPractice'));
    check('批改结果渲染判分要点与示范解法',
        verdictText.includes('机制说反了') && verdictText.includes('示范解法')
        && verdictText.includes('定义时求值一次')
        && reviewAiAnswerBodies.slice(-1)[0]?.answer === '默认参数在函数定义时求值一次',
        JSON.stringify({ text: verdictText.slice(0, 200), body: reviewAiAnswerBodies.slice(-1)[0] }));
    const collectBtn = findAll(elementsById.get('reviewAiPractice'), el => el.textContent === '收进题库')[0];
    if (collectBtn) step('点击「收进题库」不抛异常', () => collectBtn.dispatch('click'));
    await sleep(80);
    check('收藏把题面 + 示范解法一起提交',
        reviewAiCollectBodies.slice(-1)[0]?.reference?.reference.includes('items is None')
        && textOf(elementsById.get('reviewAiPractice')).includes('已收藏'),
        JSON.stringify(reviewAiCollectBodies.slice(-1)[0]).slice(0, 240));
    const discardBtn = findAll(elementsById.get('reviewAiPractice'), el => el.textContent === '放弃加练')[0];
    if (discardBtn) step('点击「放弃加练」不抛异常', () => discardBtn.dispatch('click'));
    await sleep(60);
    check('放弃加练后回到固定题（看答案回来、加练块收起）',
        elementsById.get('reviewAiPractice').hidden === true
        && elementsById.get('reviewRevealBtn').hidden === false,
        JSON.stringify({ practiceHidden: elementsById.get('reviewAiPractice').hidden,
            revealHidden: elementsById.get('reviewRevealBtn').hidden }));
```

- [ ] **Step 2: 运行确认失败**

```bash
node tests/frontend/dom-smoke.js 2>&1 | tail -12
```

Expected: 至少 `点击「AI 出道新题」…` 相关断言失败（`#reviewAiQuestionBtn` 还不存在 / 点击后无请求）

- [ ] **Step 3: 改 `index.html`**

把复习卡片里 `reviewAnswerPanel` 之前插入容器：

```html
<div class="review-ai-practice" id="reviewAiPractice" hidden></div>
```

把看答案那行改成：

```html
<div class="review-actions-row">
<button type="button" id="reviewRevealBtn" class="utility-primary-btn">看答案</button>
<button type="button" id="reviewAiQuestionBtn" class="utility-secondary-btn">AI 出道新题</button>
</div>
```

并把缓存号提升：`js/app.js?v=58` → `js/app.js?v=59`、`css/style.css?v=36` → `css/style.css?v=37`。

- [ ] **Step 4: 改 `js/app.js`**

(a) 元素引用（复习会话那一组之后）：

```js
const reviewAiQuestionBtn = document.getElementById('reviewAiQuestionBtn');
const reviewAiPractice = document.getElementById('reviewAiPractice');
```

(b) 在 `function renderReviewQuestion()` **之前**插入一整节：

```js
    // ---------- AI 现场出题（临时加练 + 收藏） ----------
    // 状态机：generating → ready(题面) → grading → graded(判分+示范解法) → collected。
    // 临时加练零留痕：不写 attempts、不改 due、不动题型轮换；只有「收进题库」才落库。
    let aiPractice = null;
    const AI_TYPE_LABELS = { concept: '概念题', predict: '输出预测', debug: '找错', code_task: '写实现' };

    function renderAiVerdict(container, verdict, reference) {
        container.replaceChildren();
        const head = document.createElement('h4');
        head.textContent = verdict.correct ? 'AI 批改：答对了' : 'AI 批改：还需要补';
        container.appendChild(head);
        const summary = document.createElement('div');
        summary.textContent = verdict.summary || '（AI 没有补充说明）';
        container.appendChild(summary);
        (verdict.missing || []).forEach(line => {
            const item = document.createElement('div');
            item.className = 'expected-answer';
            item.textContent = `缺：${line}`;
            container.appendChild(item);
        });
        if (verdict.wrongAt) {
            const wrong = document.createElement('div');
            wrong.className = 'expected-answer';
            wrong.textContent = `错在：${verdict.wrongAt}`;
            container.appendChild(wrong);
        }
        if (verdict.hint) {
            const hint = document.createElement('div');
            hint.textContent = `提示：${verdict.hint}`;
            container.appendChild(hint);
        }
        const demoTitle = document.createElement('h4');
        demoTitle.textContent = '示范解法';
        container.appendChild(demoTitle);
        const demo = reviewBodyBlock(reference.reference);
        if (demo) container.appendChild(demo);
        (reference.answer || []).forEach(line => {
            const item = document.createElement('div');
            item.className = 'expected-answer';
            item.textContent = String(line);
            container.appendChild(item);
        });
        (reference.expected || []).forEach(line => {
            const item = document.createElement('div');
            item.className = 'expected-answer';
            item.textContent = `期望输出：${line}`;
            container.appendChild(item);
        });
        if (reference.explain) {
            const explain = document.createElement('div');
            explain.textContent = `解释：${reference.explain}`;
            container.appendChild(explain);
        }
        if (reference.rootCause) {
            const cause = document.createElement('div');
            cause.textContent = `根因：${reference.rootCause}（修法：${reference.fix || ''}）`;
            container.appendChild(cause);
        }
        (reference.pitfalls || []).forEach(line => {
            const item = document.createElement('div');
            item.className = 'expected-answer';
            item.textContent = `易错：${line}`;
            container.appendChild(item);
        });
    }

    function aiPracticeButton(text, className, onClick, disabled) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = className;
        button.textContent = text;
        button.disabled = Boolean(disabled);
        button.addEventListener('click', onClick);
        return button;
    }

    function renderAiPractice() {
        const state = aiPractice;
        if (!state || !state.container) return;
        const container = state.container;
        container.hidden = false;
        container.replaceChildren();
        const head = document.createElement('div');
        head.className = 'review-ai-head';
        const badge = document.createElement('span');
        badge.className = 'ai-badge';
        badge.textContent = state.question
            ? `AI 加练 · ${AI_TYPE_LABELS[state.question.questionType] || state.question.questionType}`
            : 'AI 加练 · 正在出题…';
        head.appendChild(badge);
        if (state.question && state.question.focus) {
            const focus = document.createElement('span');
            focus.className = 'review-ai-focus';
            focus.textContent = state.question.focus;
            head.appendChild(focus);
        }
        container.appendChild(head);
        if (!state.question) {
            const loading = document.createElement('div');
            loading.textContent = 'AI 正在出题…';
            container.appendChild(loading);
        } else {
            const prompt = document.createElement('div');
            prompt.textContent = state.question.prompt || '（这道题没有题面）';
            container.appendChild(prompt);
            const body = reviewBodyBlock(state.question.code);
            if (body) container.appendChild(body);
            const answer = document.createElement('textarea');
            answer.rows = 6;
            answer.className = 'review-ai-answer';
            answer.placeholder = '先自己写，再看 AI 怎么批改';
            answer.value = state.answer || '';
            answer.addEventListener('input', () => { state.answer = answer.value; });
            container.appendChild(answer);
            if (state.reference) {
                const verdictBox = document.createElement('div');
                verdictBox.className = 'review-ai-verdict';
                renderAiVerdict(verdictBox, state.verdict || {}, state.reference);
                container.appendChild(verdictBox);
            }
        }
        const actions = document.createElement('div');
        actions.className = 'review-ai-actions';
        if (state.question && !state.reference) {
            actions.appendChild(aiPracticeButton(state.busy ? 'AI 正在批改…' : '提交给 AI 批改',
                'utility-primary-btn', () => { submitAiPracticeAnswer(); }, state.busy));
        }
        if (state.reference && !state.collected) {
            actions.appendChild(aiPracticeButton('收进题库', 'utility-secondary-btn',
                () => { collectAiPracticeQuestion(); }, state.busy));
        }
        if (state.reference && state.collected) {
            const collected = document.createElement('span');
            collected.className = 'review-ai-collected';
            collected.textContent = '已收藏（可在知识点页管理）';
            actions.appendChild(collected);
        }
        if (state.reference) {
            actions.appendChild(aiPracticeButton('再来一题', 'utility-secondary-btn',
                () => { retryAiPractice(); }, state.busy));
        }
        actions.appendChild(aiPracticeButton('放弃加练', 'utility-secondary-btn',
            () => { discardAiPractice(); }, false));
        container.appendChild(actions);
    }

    function aiPracticeTarget(container) {
        // 复习卡片里加练期间把固定题那一套藏起来；弹窗（知识点页）没有这些元素。
        if (container === reviewAiPractice) {
            reviewQuestionPrompt.hidden = true;
            reviewAnswerInput.hidden = true;
            reviewRevealBtn.hidden = true;
            reviewAiQuestionBtn.hidden = true;
            reviewAnswerPanel.hidden = true;
            reviewAiGradeRow.hidden = true;
            reviewGradeButtons.hidden = true;
        }
    }

    function aiPracticeRestoreCard() {
        reviewQuestionPrompt.hidden = false;
        reviewAnswerInput.hidden = false;
        reviewRevealBtn.hidden = false;
        reviewAiQuestionBtn.hidden = false;
        reviewAiPractice.hidden = true;
        reviewAiPractice.replaceChildren();
        renderReviewQuestion();
    }

    async function startAiPractice(code, container, title) {
        if (aiPractice && aiPractice.busy) return;
        aiPractice = { surface: container === reviewAiPractice ? 'card' : 'modal', code: code,
            title: title || '', question: null, verdict: null, reference: null,
            collected: false, busy: true, answer: '', container: container };
        aiPracticeTarget(container);
        renderAiPractice();
        let payload = null;
        try {
            payload = await callApi('/api/review/ai-question', 'POST', { code: code });
        } catch (error) {
            payload = null;
            showToast(error.message || 'AI 出题失败，请重试');
        }
        if (!aiPractice || aiPractice.code !== code) return;
        if (!payload || !payload.question) {
            discardAiPractice();
            return;
        }
        aiPractice.question = payload.question;
        aiPractice.busy = false;
        renderAiPractice();
    }

    async function submitAiPracticeAnswer() {
        const state = aiPractice;
        if (!state || !state.question || state.busy) return;
        state.busy = true;
        renderAiPractice();
        try {
            const payload = await callApi('/api/review/ai-answer', 'POST', {
                code: state.code, questionType: state.question.questionType,
                prompt: state.question.prompt, questionCode: state.question.code || '',
                focus: state.question.focus || '', answer: state.answer || '' });
            state.verdict = payload.verdict || {};
            state.reference = payload.reference || null;
        } catch (error) {
            showToast(error.message || 'AI 批改失败，请重试');
        }
        state.busy = false;
        renderAiPractice();
    }

    async function collectAiPracticeQuestion() {
        const state = aiPractice;
        if (!state || !state.reference || state.busy) return;
        state.busy = true;
        renderAiPractice();
        try {
            await callApi('/api/review/ai-collect', 'POST', {
                code: state.code, questionType: state.question.questionType,
                prompt: state.question.prompt, questionCode: state.question.code || '',
                focus: state.question.focus || '', reference: state.reference });
            state.collected = true;
            aiQuestionsLoaded = false;   // 知识点页徽标下次打开重新拉
            showToast('已收进题库，以后和固定题一起复习');
        } catch (error) {
            showToast(error.message || '收藏失败，请重试');
        }
        state.busy = false;
        renderAiPractice();
    }

    function retryAiPractice() {
        const state = aiPractice;
        if (!state) return;
        startAiPractice(state.code, state.container, state.title);
    }

    function discardAiPractice() {
        const state = aiPractice;
        aiPractice = null;
        if (!state) return;
        if (state.surface === 'card') {
            aiPracticeRestoreCard();
        } else {
            state.container.replaceChildren();
            state.container.hidden = true;
            closeUtilityModal();
        }
    }
```

(c) 事件绑定（和 `reviewRevealBtn` 那一组放在一起）：

```js
        reviewAiQuestionBtn.addEventListener('click', () => {
            const item = reviewSessionState.items[reviewSessionState.index];
            if (!item) return;
            startAiPractice(item.code, reviewAiPractice, item.title);
        });
```

(d) 顶部声明 `let aiQuestionsLoaded = false;`：

```js
    let aiQuestionsLoaded = false;
```

- [ ] **Step 5: 改 `css/style.css`**

在 `.review-ai-grade` 附近追加：

```css
.ai-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background: #eef4ff;
    color: #2b6cb0;
    font-size: 12px;
    font-weight: 600;
}

.review-ai-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}

.review-ai-focus {
    color: #657287;
    font-size: 13px;
}

.review-ai-practice {
    border: 1px dashed #cdd8ea;
    border-radius: 10px;
    padding: 12px;
    margin: 12px 0;
    background: #fbfdff;
}

.review-ai-answer {
    width: 100%;
    margin: 8px 0;
}

.review-ai-verdict {
    margin: 8px 0;
}

.review-ai-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
}

.review-ai-collected {
    color: #2f855a;
    font-size: 13px;
}
```

- [ ] **Step 6: 运行确认通过**

```bash
node tests/frontend/dom-smoke.js 2>&1 | tail -14
```

Expected: `通过 N 项，失败 0 项`（新增约 8 项）

- [ ] **Step 7: 提交**

```bash
git add index.html js/app.js css/style.css tests/frontend/dom-smoke.js
git commit -m "feat(review): 复习卡片加「AI 出道新题」（出题/批改/收藏/放弃）"
```

---

### Task 7: 前端 · 知识点页入口与收藏管理

**Files:**
- Modify: `js/app.js`（知识点页徽标 + 弹窗 + 删除）
- Modify: `tests/frontend/dom-smoke.js`（知识点页断言）
- Modify: `css/style.css`（徽标/列表样式）

**Interfaces:**
- Consumes: Task 6 的 `startAiPractice(code, container, title)` / `createClient` 等；Task 5 的 `GET /api/review/ai-questions`、`DELETE /api/review/ai-question`
- Produces: `aiQuestions`（全量收藏题数组）、`loadAiQuestions()`、`openAiPracticeModal(code, title)`、`aiQuestionsFor(code)`

- [ ] **Step 1: 写失败的测试**

在 `tests/frontend/dom-smoke.js` 的 AI 加练断言之后追加：

```js
    // ⑯ 知识点页：AI 出题入口 + 已收藏徽标 + 删除
    aiQuestionsFixture = [{ id: 'ai-q-1', code: 'py.a.b', questionType: 'predict',
        prompt: '（AI 出的）写出两次调用的输出', questionCode: '', focus: '默认参数',
        createdAt: '2026-09-19T10:00:00' }];
    elementsById.get('openKnowledgeBtn').dispatch('click');
    await sleep(80);
    const knowledgeText = textOf(elementsById.get('knowledgeList'));
    check('知识点卡片出现「AI 出题」与已收藏徽标',
        knowledgeText.includes('AI 出题') && knowledgeText.includes('AI 题 1'),
        knowledgeText.slice(0, 200));
    const aiButton = findAll(elementsById.get('knowledgeList'), el => el.textContent === 'AI 出题')[0];
    if (aiButton) step('点击知识点页「AI 出题」不抛异常', () => aiButton.dispatch('click'));
    await sleep(80);
    check('知识点页出题走弹窗且渲染出题面',
        textOf(elementsById.get('utilityBody')).includes('（AI 出的）写出两次调用的输出'),
        textOf(elementsById.get('utilityBody')).slice(0, 200));
    const closeBtn = elementsById.get('utilityCloseBtn');
    if (closeBtn) step('关闭弹窗不抛异常', () => closeBtn.dispatch('click'));
    await sleep(40);
    check('关闭弹窗后加练状态清空', elementsById.get('utilityBody').children.length === 0,
        String(elementsById.get('utilityBody').children.length));
```

- [ ] **Step 2: 运行确认失败**

```bash
node tests/frontend/dom-smoke.js 2>&1 | tail -8
```

Expected: 知识点页两条断言失败（没有「AI 出题」按钮 / 徽标）

- [ ] **Step 3: 实现（`js/app.js`）**

(a) 在 AI 加练那一节里补上收藏列表与徽标：

```js
    let aiQuestions = [];
    let aiQuestionsByCode = {};

    function aiQuestionsFor(code) {
        return aiQuestionsByCode[code] || [];
    }

    async function loadAiQuestions(force = false) {
        if (aiQuestionsLoaded && !force) return aiQuestions;
        try {
            const response = await apiFetch('/api/review/ai-questions', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取 AI 题失败');
            aiQuestions = Array.isArray(payload.items) ? payload.items : [];
        } catch (error) {
            aiQuestions = [];
        }
        aiQuestionsByCode = {};
        aiQuestions.forEach(entry => {
            (aiQuestionsByCode[entry.code] = aiQuestionsByCode[entry.code] || []).push(entry);
        });
        aiQuestionsLoaded = true;
        return aiQuestions;
    }

    function openAiPracticeModal(code, title) {
        showUtilityModal('AI 加练', title || '现场出题');
        const container = utilityBody;
        aiPractice = null;
        startAiPractice(code, container, title);
    }

    async function deleteAiQuestion(questionId, code, title) {
        try {
            const response = await apiFetch(`/api/review/ai-question?id=${encodeURIComponent(questionId)}`,
                { method: 'DELETE' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '删除失败');
            aiQuestionsLoaded = false;
            await loadAiQuestions(true);
            openAiPracticeModal(code, title);
            showToast('已删除这道 AI 题');
        } catch (error) {
            showToast(error.message || '删除失败，请重试');
        }
    }

    function renderAiQuestionLibrary(code, title) {
        const container = utilityBody;
        const items = aiQuestionsFor(code);
        const box = document.createElement('div');
        box.className = 'ai-question-library';
        const heading = document.createElement('h4');
        heading.textContent = `我的 AI 题（${items.length}）`;
        box.appendChild(heading);
        if (items.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '这个知识点还没有收藏的 AI 题；点上面的「AI 出题」现场来一道。';
            box.appendChild(empty);
        }
        items.forEach(entry => {
            const card = document.createElement('div');
            card.className = 'ai-question-item';
            const head = document.createElement('div');
            head.className = 'ai-question-title';
            head.textContent = `[${AI_TYPE_LABELS[entry.questionType] || entry.questionType}] ${entry.prompt}`;
            const actions = document.createElement('div');
            actions.className = 'review-ai-actions';
            actions.append(
                aiPracticeButton('关闭', 'utility-secondary-btn', () => { closeUtilityModal(); }, false),
                aiPracticeButton('删除', 'utility-secondary-btn',
                    () => { deleteAiQuestion(entry.id, code, title); }, false));
            card.append(head, actions);
            box.appendChild(card);
        });
        container.appendChild(box);
    }
```

(b) `renderKnowledgeList()` 的卡片里加按钮与徽标（`card.append(title, meta, practice);` 改成）：

```js
            const aiButton = document.createElement('button');
            aiButton.type = 'button';
            aiButton.className = 'utility-secondary-btn';
            aiButton.textContent = 'AI 出题';
            aiButton.addEventListener('click', () => {
                showUtilityModal('AI 加练', point.title);
                renderAiQuestionLibrary(point.code, point.title);
                startAiPractice(point.code, utilityBody, point.title);
            });
            const saved = aiQuestionsFor(point.code);
            if (saved.length > 0) {
                const badge = document.createElement('span');
                badge.className = 'ai-badge';
                badge.textContent = `AI 题 ${saved.length}`;
                badge.addEventListener('click', () => {
                    showUtilityModal('AI 加练', point.title);
                    renderAiQuestionLibrary(point.code, point.title);
                });
                card.append(title, meta, practice, aiButton, badge);
            } else {
                card.append(title, meta, practice, aiButton);
            }
```

(c) `showKnowledgeLibrary()` 里在 `renderKnowledgeList()` 之前拉一次收藏：

```js
        await loadAiQuestions();
        populateModuleFilter(knowledgeModuleFilter, knowledgeModuleNames());
        renderKnowledgeList();
```

- [ ] **Step 4: 加样式**

在 `css/style.css` 追加：

```css
.ai-question-library {
    margin-top: 12px;
    border-top: 1px solid #e6ecf5;
    padding-top: 10px;
}

.ai-question-item {
    border: 1px solid #e6ecf5;
    border-radius: 8px;
    padding: 8px;
    margin-bottom: 8px;
}

.ai-question-title {
    margin-bottom: 6px;
}

.knowledge-item .ai-badge {
    margin-left: 6px;
    cursor: pointer;
}
```

- [ ] **Step 5: 运行确认通过**

```bash
node tests/frontend/dom-smoke.js 2>&1 | tail -10
```

Expected: `失败 0 项`

- [ ] **Step 6: 提交**

```bash
git add js/app.js css/style.css tests/frontend/dom-smoke.js
git commit -m "feat(review): 知识点页 AI 出题入口 + 已收藏 AI 题的查看与删除"
```

---

### Task 8: 端到端覆盖 + 零留痕硬断言（`tests/e2e-verify.sh`）

**Files:**
- Modify: `tests/e2e-verify.sh`（在 HTTP 断言 python 块的最后一段之前插入新段）

**Interfaces:**
- Consumes: Task 5 的 5 个端点；`TODO_AI_MOCK=1`（脚本已导出）、`TODO_SQLITE_FILE`（脚本已导出）
- Produces: e2e 断言 `AI 加练` 全流程 + 「临时加练不写 attempts/states」的硬证据

- [ ] **Step 1: 写断言（先跑一次看它失败）**

在 `tests/e2e-verify.sh` 的 python 断言块里，`print(f"\n   通过 {len(passed)} 项，失败 {len(failed)} 项")` **之前**插入：

```python
# --- AI 加练：出题（无答案）→ 批改（判分 + 示范解法）→ 收藏 → 列表 → 删除 ---
import os as _os
import sqlite3 as _sqlite3

def review_table_counts():
    connection = _sqlite3.connect(_os.environ["TODO_SQLITE_FILE"])
    try:
        return (connection.execute("SELECT COUNT(*) FROM review_attempts").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM review_states").fetchone()[0])
    finally:
        connection.close()

target_code = "py.mutability.default-arg"
before_counts = review_table_counts()
status, _, data = call("/api/review/ai-question", method="POST", body={"code": target_code})
question = json.loads(data).get("question") if status == 200 else {}
check("AI 加练 出题 200（mock）", status == 200 and question.get("prompt"), f"status={status} body={data[:160]}")
check("AI 加练 出题不带参考答案", "reference" not in question, str(question)[:160])
check("AI 加练 出题题型合法",
      question.get("questionType") in ("concept", "predict", "debug", "code_task"), str(question)[:160])

status, _, data = call("/api/review/ai-answer", method="POST", body={
    "code": target_code, "questionType": question.get("questionType"),
    "prompt": question.get("prompt"), "questionCode": question.get("code") or "",
    "focus": question.get("focus") or "", "answer": ""})
verdict = json.loads(data).get("verdict") if status == 200 else {}
reference = json.loads(data).get("reference") if status == 200 else {}
check("AI 加练 空作答也能批改（200 + verdict）", status == 200 and verdict, f"status={status} body={data[:200]}")
check("AI 加练 空作答必须给示范解法", bool(reference.get("reference")), str(reference)[:200])
check("AI 加练 空作答判为未通过", verdict.get("correct") is False, str(verdict)[:160])

status, _, data = call("/api/review/ai-collect", method="POST", body={
    "code": target_code, "questionType": question.get("questionType"),
    "prompt": question.get("prompt"), "questionCode": question.get("code") or "",
    "focus": question.get("focus") or "", "reference": reference})
saved_id = (json.loads(data).get("question") or {}).get("id") if status == 200 else ""
check("AI 加练 收藏 200", status == 200 and bool(saved_id), f"status={status} body={data[:200]}")

status, _, data = call("/api/review/ai-questions?code=" + urllib.parse.quote(target_code))
items = json.loads(data).get("items") if status == 200 else []
check("AI 加练 列表含刚收藏的题且不吐参考答案",
      status == 200 and any(item["id"] == saved_id for item in items)
      and all("reference" not in item for item in items), f"status={status} body={data[:200]}")

after_counts = review_table_counts()
check("临时加练零留痕：attempts/states 行数不变", before_counts == after_counts,
      f"{before_counts} -> {after_counts}")

status, _, data = call("/api/review/ai-question?id=" + urllib.parse.quote(saved_id), method="DELETE")
check("AI 加练 删除 200 且返回该点剩余列表",
      status == 200 and json.loads(data)["items"] == [], f"status={status} body={data[:200]}")
status, _, data = call("/api/review/ai-question?id=" + urllib.parse.quote(saved_id), method="DELETE")
check("AI 加练 重复删除 → 404", status == 404, f"status={status}")
status, headers, data = call("/api/review/ai-collect", method="POST", body={
    "code": target_code, "questionType": "essay", "prompt": "x", "reference": {"explain": "y"}})
check_json_error("AI 加练 非法题型 → 400 JSON", status, headers.get("Content-Type", ""), data, 400)
```

> `check_json_error(name, status, ctype, data, expect_status)` 是同文件已有的助手（第 259 行），`data` 是 `call()` 返回的**原始 bytes**，`ctype` 取自 `headers.get("Content-Type", "")`。

- [ ] **Step 2: 运行确认失败**

```bash
bash tests/e2e-verify.sh 2>&1 | tail -20
```

Expected: 新断言全 ✘（端点还不存在或参数不符）

- [ ] **Step 3: 修正断言细节直至通过**

重跑上一条命令，Expected: 全部 ✔，最后一行 `通过 N 项，失败 0 项`

- [ ] **Step 4: 提交**

```bash
git add tests/e2e-verify.sh
git commit -m "test(review): 端到端覆盖 AI 加练全流程 + 临时加练零留痕硬断言"
```

---

### Task 9: 反向验证 +3 条（`scripts/verify-tests-catch.py` + `scripts/check.sh`）

**Files:**
- Modify: `scripts/verify-tests-catch.py`（`CASES` 列表末尾）
- Modify: `scripts/check.sh:93`（标签 65 → 68）

**Interfaces:**
- Consumes: Task 3/4/5 的产品代码与既有测试
- Produces: 3 条"把产品改回旧行为、测试必须红"的用例

- [ ] **Step 1: 追加 3 条用例**

在 `CASES` 列表的最后一个 `),` 之后、`]` 之前插入：

```python
    (
        "收藏 AI 题时必须连同示范解一起落库（否则收藏后无从复习）",
        "review_storage.py",
        crlf('        "focus": focus, "reference": reference or {},\n'
             "    })\n"
             "    errors = review_content.validate_ai_question(question, require_reference=True)\n"),
        crlf('        "focus": focus, "reference": {},\n'
             "    })\n"
             "    errors = review_content.validate_ai_question(question)\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_review_ai_questions.AiQuestionStorageTests.test_read_and_delete_question"],
    ),
    (
        "出题上下文必须带现有题面与最近作答（否则 AI 只在瞎猜）",
        "review_storage.py",
        crlf('        "existingPrompts": prompts,\n'),
        crlf('        "existingPrompts": {},\n'),
        [sys.executable, "-m", "unittest",
         "tests.test_review_ai_questions.AiQuestionStorageTests"
         ".test_context_carries_point_prompts_and_recent_history"],
    ),
    (
        "AI 题结构不合规必须变成可读 502（不能静默吞掉）",
        "local_server.py",
        crlf("                except RuntimeError as error:\n"
             '                    self.send_json(502, {"error": f"AI 出题失败：{error}"})\n'
             "                    return\n"),
        crlf("                except RuntimeError:\n"
             '                    self.send_json(200, {"ok": True, "question": {}})\n'
             "                    return\n"),
        [sys.executable, "-m", "unittest",
         "tests.test_review_http.ReviewAiQuestionHttpTests.test_ai_failure_becomes_502_with_readable_error"],
    ),
```

- [ ] **Step 2: 改 `check.sh` 标签**

```bash
    run "verify-tests-catch.py（68 条）" python3 scripts/verify-tests-catch.py
```

- [ ] **Step 3: 运行确认 68 条全绿**

```bash
python3 scripts/verify-tests-catch.py 2>&1 | tail -6
```

Expected: `全部 68 条都能被测试抓到 ✔`

- [ ] **Step 4: 提交**

```bash
git add scripts/verify-tests-catch.py scripts/check.sh
git commit -m "test(review): 反向验证 +3 条（收藏带示范解、出题上下文、502 可读错误）"
```

---

### Task 10: 全量检查 + 性能实测 + README 说明

**Files:**
- Modify: `README.md`（复习功能那一节补一句 AI 加练）
- 产出：性能与门禁的实测证据（写在提交信息里）

**Interfaces:**
- Consumes: 前 9 个任务的全部产物
- Produces: 可交付的第一批（门禁 9/9 + 性能达标 + 文档）

- [ ] **Step 1: README 补一句**

在 `README.md` 的「功能」清单里，复习那一条后面追加：

```markdown
- 复习加练：任意知识点都能让 AI 现场出一道新题（先做题、AI 再批改并给示范解法），
  满意可以「收进题库」，之后和内置题一起参与复习轮换；临时加练不改动复习排期
```

- [ ] **Step 2: 性能实测（把数字记下来）**

```bash
python3 - <<'PY'
import json, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, "/home/lyh/todo_list")
tmp = tempfile.TemporaryDirectory(prefix="ai-q-perf-")
os.environ["TODO_SQLITE_FILE"] = str(Path(tmp.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(tmp.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(tmp.name) / "memo.sqlite3")
os.environ["TODO_AI_MOCK"] = "1"
import review_storage, storage
storage.ensure_schema()
review_storage.ensure_content_imported()
codes = [point["code"] for point in review_storage.list_points(limit=500)["points"]]
for index in range(500):
    review_storage.collect_ai_question(
        codes[index % len(codes)], "predict", f"现场第 {index} 题", "print(1)", "求值时机",
        {"reference": "def f(): return 1", "explain": "常量"})
start = time.perf_counter()
items = review_storage.list_ai_questions()
list_ms = (time.perf_counter() - start) * 1000
start = time.perf_counter()
queue = review_storage.build_queue("2026-09-19", limit=50)
queue_ms = (time.perf_counter() - start) * 1000
print(f"  收藏 500 条：列表 {len(items)} 条 / {list_ms:.1f} ms（要求 < 5 ms）")
print(f"  构建 50 题队列：{len(queue['items'])} 题 / {queue_ms:.1f} ms（改动前后同量级）")
PY
```

Expected: 列表 < 5 ms（实测约 1-2 ms）；队列构建与改动前同量级（参考现基线：复习队列 1000 任务 2.2 ms / 10000 任务 8.1 ms）

- [ ] **Step 3: 重新生成并核对基准**

```bash
python3 scripts/benchmark_scale.py 2>&1 | tail -18
```

Expected: 与 spec 记录一致（10000 任务：保存 ≈380 ms、读取 ≈140 ms、patch ≈0.5 ms），无回归

- [ ] **Step 4: 全量门禁**

```bash
./scripts/check.sh 2>&1 | tail -30
```

Expected: 9 步全 ✔（含 `verify-tests-catch.py（68 条）`）

- [ ] **Step 5: 真实库只读核对（不写真实数据）**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('file:data/todo.sqlite3?mode=ro', uri=True)
print('v', c.execute('PRAGMA user_version').fetchone()[0], c.execute('PRAGMA quick_check').fetchone()[0],
      '项目', c.execute('SELECT COUNT(*) FROM projects').fetchone()[0],
      '节点', c.execute('SELECT COUNT(*) FROM nodes').fetchone()[0])"
```

Expected: `v 9 ok 项目 2 节点 223`（真实库仍是 v9：**不要**在真实库上跑 `ensure_schema`；迁移会在你下次启动 App 时自动完成，并留下 `before-migrate-v9-*.sqlite3` 快照）

- [ ] **Step 6: 提交**

```bash
git add README.md
git commit -m "docs(review): README 补一句 AI 加练；第一批性能实测：500 条收藏列表 <5ms"
```

---

## Self-Review（写完计划后自查）

**1. Spec 覆盖检查**

| Spec 需求 | 对应任务 |
| --- | --- |
| §2-1 默认临时、满意收藏 | Task 6（临时加练不落库）、Task 3/5（collect） |
| §2-2 AI 自动挑题型、结构固定四种 | Task 4（prompt 输出 questionType + 校验）、Task 2（闸门） |
| §2-3 不预生成参考解、作答后批改 + 示范解 | Task 4（`review_ai_answer`）、Task 6（提交按钮） |
| §2-4 收藏存示范解 + 考察点、与固定题同构 | Task 3（reference 落库）、Task 2（键对齐 reveal） |
| §2-5 临时加练零留痕 | Task 6（不调 `/api/review/answer`）、Task 8（行数不变硬断言） |
| §2-6 收藏的题与固定题一起轮换 | **第二批**（本计划不做，spec §10） |
| §2-7 两个入口 + 知识点页可看/删 | Task 6（卡片）、Task 7（知识点页 + 删除） |
| §2-8 出题上下文 = 知识点 + 最近 5 条历史 | Task 3（`ai_question_context`）、Task 4（透传）、Task 9（反向验证） |
| §4.1 新表（v9→v10） | Task 1 |
| §4.3 content_json 结构 | Task 2、Task 3 |
| §5.1 五个端点 | Task 5 |
| §5.3 两个 prompt + 两个函数 + mock | Task 4 |
| §5.4 失败降级（503/502/保留作答/防重入） | Task 5（503/502）、Task 6（状态位 + 保留作答） |
| §6 前端交互与共享渲染 | Task 6（`renderAiVerdict` + 动态渲染器）、Task 7 |
| §7 测试分层（单元/HTTP/前端/端到端/反向/性能） | Task 1-9 + Task 10 |
| §8 风险与回滚 | Task 1（增量 DDL，机制复用） |
| §9 YAGNI | 计划里没有任何选择题/多题/去重/编辑/项目代码喂入 |

缺口：spec §5.2（reveal/answer 的 `questionRef`）属**第二批**，本计划有意不做。

**2. 占位符扫描**：无 TBD/TODO；每个代码步骤都是可粘贴的完整实现；唯一需要实现者现场核对的是 Task 8 的 `check_json_error` 签名（已在步骤里给出替代写法）。

**3. 类型/命名一致性**（跨任务核对过）：
- `normalize_ai_question` / `validate_ai_question(…, require_reference=)`（Task 2）→ Task 3、Task 4、Task 9 用法一致
- `collect_ai_question(code, question_type, prompt, question_code, focus, reference)`（Task 3）→ Task 5 端点、Task 10 性能脚本一致
- `list_ai_questions(code=None)` 返回字段 `id/code/questionType/prompt/questionCode/focus/createdAt` → Task 5/7/8 一致（前端 Task 7 用 `entry.questionCode`，与列表字段同名）
- `generate_ai_question(*, context, question_type="")` / `review_ai_answer(*, context, question, answer)`（Task 4）→ Task 5 调用一致
- 前端：`aiPractice`（Task 6）→ Task 7 复用 `startAiPractice` / `aiPracticeButton` / `AI_TYPE_LABELS`；`aiQuestionsLoaded` 在 Task 6 声明、Task 7 使用（同一文件同一 IIFE 作用域）
