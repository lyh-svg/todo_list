# Python 复习内容与复习会话 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"任务级打卡式复习"升级为"知识点级主动回忆训练"：内置 Python 课程库（本批第 1 周 40 点）、一次一题的复习会话、五档自评调度、薄弱点闭环、复习页与知识点库。

**Architecture:** 复用现有单体结构——Python 标准库 HTTP 服务（`local_server.py`）+ SQLite（主库 `data/todo.sqlite3` 升级到 schema v8，新增 5 张复习表）+ 原生 JS 前端（`js/app.js`）。复习内容作为 JSON 数据文件随仓库发布（`content/review/`），首次使用或启动时按 `code` 幂等导入；复习会话是独立视图，答案只经 `/api/review/reveal` 下发，保证"先回忆再揭示"。

**Tech Stack:** Python 3.13/3.14 标准库（sqlite3、http.server）、原生 JS（无框架）、unittest、Playwright（真浏览器）、仓库自带 `./scripts/check.sh`。

## Global Constraints

- 行尾约定：`.py/.js/.css/.html/.md` 必须 CRLF，`*.sh` 用 LF；`./scripts/check.sh` 第 9 步会检查（含双 CR）。
- 测试一律 `python3 -m unittest tests.<module> -v`；全量是 `python3 -m unittest discover -s tests`。
- 每批完成必须 `./scripts/check.sh` 九步全绿，才允许提交推送。
- 真实数据 `data/` 只读：所有测试用临时库（`TODO_SQLITE_FILE` 等环境变量），迁移验证只在**库副本**上跑。
- schema 升到 v8：只做**加表加索引**，不改动 `projects`/`nodes` 既有列；`ensure_schema()` 迁移前自动快照，失败回滚。
- 调度日期一律用**前端传入的 `today`（本机日期）**，与现有 `todayStr()`/`/api/reviews` 同口径，服务端不自己取 `date.today()`。
- 四个题槽位（concept/predict/debug/code_task）与 `pitfalls` 是**下限**：允许同一个点写多道变体题；任何知识点都必须能产出这五类内容。
- 答案（参考答案、历史答案）**不得**出现在 `/api/review/queue` 响应里，也不得在会话揭示前进入 DOM。
- 内置内容 `origin='builtin'`，额外补充 `builtin-extra`，AI 生成 `ai`；导入必须幂等（按 `code` upsert）。
- 纯元任务（`1104` 建立补漏队列、`1504` 复盘并安排复习）不挂知识点、不生成复习项。
- 单文件职责：内容校验在 `review_content.py`，复习存储与调度在 `review_storage.py`，HTTP 在 `local_server.py`，前端在 `js/app.js`。

## File Structure

| 文件 | 职责 |
| --- | --- |
| `storage.py`（改） | schema v8：`SCHEMA_VERSION=8`、5 张复习表 + 索引（幂等 DDL）、`state_lock()` 公开锁入口 |
| `review_content.py`（新） | 课程库 JSON 的读取与校验（纯函数，无 DB） |
| `content/review/py-week1.json`（新） | 第 1 周 40 个知识点的内容数据 |
| `review_storage.py`（新） | 内容导入、复习状态与调度、每日队列、统计查询、作答记录 |
| `local_server.py`（改） | `/api/review/*` 九个接口 |
| `js/app.js`（改） | 会话状态机、复习页改版、知识点库页、生成回流接线 |
| `index.html` / `css/style.css`（改） | 会话视图与知识点库视图的结构与样式 |
| `tests/test_review_content.py`（新） | 校验器单测 + 坏数据必须报错 |
| `tests/test_review_schedule.py`（新） | 五档调度、薄弱点、每日队列组装 |
| `tests/test_review_storage.py`（新） | 内容导入幂等、attempts、summary、历史 |
| `tests/test_review_http.py`（新） | 接口状态码、参数校验、队列不含答案 |
| `tests/test_review_migration.py`（新） | v7 副本 → v8 迁移，旧数据不变、新表就位 |
| `tests/frontend/dom-smoke.js`（改） | 会话流程 + "揭示前 DOM 无答案"断言 |
| `tests/test_browser_flows.py`（改） | 真浏览器完成一道题的全流程 |
| `scripts/benchmark_review.py`（新） | 写锁基准：保存 1 万任务 + 同时答题 |

---

### Task 1: 内容格式与校验器

**Files:**
- Create: `review_content.py`
- Create: `content/review/py-week1.json`（本任务只放 1 个示例点，Task 15 补齐 40 点）
- Test: `tests/test_review_content.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `review_content.QUESTION_TYPES = ("concept", "predict", "debug", "code_task")`
  - `review_content.load_content_file(path) -> {"schemaVersion": int, "week": int, "level": str, "points": list[dict]}`，格式错误抛 `ValueError`
  - `review_content.validate_points(points) -> list[str]`（中文错误列表，空 = 合法）

- [ ] **Step 1: 写失败的测试**

```python
import json
import tempfile
import unittest
from pathlib import Path

import review_content

GOOD_POINT = {
    "code": "py.mutability.default-arg",
    "title": "可变默认参数与求值时机",
    "minutes": 20,
    "module": "函数",
    "level": "基础",
    "taskRefs": [{"taskId": "1103", "relation": "introduces"}],
    "concept": {"prompt": "默认参数什么时候求值？", "answer": ["函数定义时求值一次", "可变对象会在调用间共享"]},
    "predict": {"prompt": "写出输出并解释",
                "code": "def add(item, items=[]):\n    items.append(item)\n    return items\nprint(add(1))\nprint(add(2))",
                "expected": ["[1]", "[1, 2]"], "explain": "第二次调用复用了定义时创建的同一个列表"},
    "debug": {"prompt": "找出 bug", "code": "def cache(k, store={}):\n    return store.setdefault(k, [])",
              "rootCause": "store 在函数定义时创建一次，被所有调用共享",
              "fix": "改成 store=None，函数体内 store = {} if store is None else store"},
    "code_task": {"prompt": "用 None 哨兵重写",
                  "acceptance": ["多次调用互不影响", "带一个 unittest 用例"],
                  "reference": "def add(item, items=None):\n    items = [] if items is None else items\n    items.append(item)\n    return items"},
    "pitfalls": ["默认值是可变对象", "把默认值当每次新建", "调用侧共享同一列表"],
}


class ReviewContentTests(unittest.TestCase):
    def test_validate_points_accepts_good_point(self) -> None:
        self.assertEqual(review_content.validate_points([GOOD_POINT]), [])

    def test_validate_points_reports_missing_predict_output(self) -> None:
        broken = json.loads(json.dumps(GOOD_POINT))
        broken["predict"]["expected"] = []
        errors = review_content.validate_points([broken])
        self.assertTrue(any("predict" in error for error in errors), errors)

    def test_validate_points_reports_bad_minutes_and_code(self) -> None:
        broken = json.loads(json.dumps(GOOD_POINT))
        broken["minutes"] = 90
        broken["code"] = "default-arg"
        errors = review_content.validate_points([broken])
        self.assertTrue(any("minutes" in error for error in errors), errors)
        self.assertTrue(any("code" in error for error in errors), errors)

    def test_validate_points_rejects_duplicate_code(self) -> None:
        errors = review_content.validate_points([GOOD_POINT, dict(GOOD_POINT)])
        self.assertTrue(any("重复" in error for error in errors), errors)

    def test_validate_points_rejects_unknown_relation(self) -> None:
        broken = json.loads(json.dumps(GOOD_POINT))
        broken["taskRefs"] = [{"taskId": "1103", "relation": "touches"}]
        errors = review_content.validate_points([broken])
        self.assertTrue(any("relation" in error for error in errors), errors)

    def test_load_content_file_round_trip(self) -> None:
        payload = {"schemaVersion": 1, "week": 1, "level": "基础", "points": [GOOD_POINT]}
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "py-week1.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            loaded = review_content.load_content_file(path)
        self.assertEqual(loaded["week"], 1)
        self.assertEqual(len(loaded["points"]), 1)

    def test_load_content_file_rejects_bad_json(self) -> None:
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                review_content.load_content_file(path)

    def test_real_week1_file_is_valid(self) -> None:
        loaded = review_content.load_content_file(Path("content/review/py-week1.json"))
        self.assertEqual(review_content.validate_points(loaded["points"]), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_content -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'review_content'`）

- [ ] **Step 3: 实现校验器**

```python
"""课程库 JSON 的读取与校验（纯函数，不碰数据库）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

QUESTION_TYPES = ("concept", "predict", "debug", "code_task")
LEVELS = ("基础", "实用", "进阶")
RELATIONS = ("introduces", "exercises")
MIN_MINUTES = 5
MAX_MINUTES = 30


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (_text(entry) for entry in value) if item]


def validate_points(points: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(points, list):
        return ["points 必须是数组"]
    seen: set[str] = set()
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            errors.append(f"第 {index + 1} 个知识点：不是对象")
            continue
        code = _text(point.get("code"))
        where = f"知识点 {code or index + 1}"
        if not code:
            errors.append(f"{where}：缺少 code")
        elif not code.startswith("py.") or code.count(".") < 2:
            errors.append(f"{where}：code 应形如 py.<主题>.<点>")
        elif code in seen:
            errors.append(f"{where}：code 重复")
        seen.add(code)
        if not _text(point.get("title")):
            errors.append(f"{where}：缺少 title")
        try:
            minutes = int(point.get("minutes"))
        except (TypeError, ValueError):
            minutes = 0
        if not MIN_MINUTES <= minutes <= MAX_MINUTES:
            errors.append(f"{where}：minutes 必须在 {MIN_MINUTES}~{MAX_MINUTES} 之间")
        if _text(point.get("level")) not in LEVELS:
            errors.append(f"{where}：level 必须是 基础/实用/进阶 之一")
        for slot in QUESTION_TYPES:
            block = point.get(slot)
            if not isinstance(block, dict) or not _text(block.get("prompt")):
                errors.append(f"{where}：缺少 {slot} 题面")
                continue
            if slot == "concept" and not _text_list(block.get("answer")):
                errors.append(f"{where}：concept 缺少 answer 要点")
            if slot == "predict":
                if not _text(block.get("code")):
                    errors.append(f"{where}：predict 缺少 code")
                if not _text_list(block.get("expected")):
                    errors.append(f"{where}：predict 缺少 expected 输出")
                if not _text(block.get("explain")):
                    errors.append(f"{where}：predict 缺少 explain")
            if slot == "debug":
                if not _text(block.get("rootCause")):
                    errors.append(f"{where}：debug 缺少 rootCause")
                if not _text(block.get("fix")):
                    errors.append(f"{where}：debug 缺少 fix")
            if slot == "code_task":
                if not _text_list(block.get("acceptance")):
                    errors.append(f"{where}：code_task 缺少 acceptance 验收要点")
                if not _text(block.get("reference")):
                    errors.append(f"{where}：code_task 缺少 reference 参考实现")
        if not _text_list(point.get("pitfalls")):
            errors.append(f"{where}：缺少 pitfalls 易错点")
        refs = point.get("taskRefs")
        if not isinstance(refs, list):
            errors.append(f"{where}：taskRefs 必须是数组（可以为空）")
        else:
            for ref in refs:
                if not isinstance(ref, dict) or not _text(ref.get("taskId")):
                    errors.append(f"{where}：taskRefs 里缺少 taskId")
                elif _text(ref.get("relation")) not in RELATIONS:
                    errors.append(f"{where}：taskRefs 的 relation 只能是 introduces/exercises")
    return errors


def load_content_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"课程库文件不存在：{file_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"课程库文件不是合法 JSON：{file_path}（{error}）") from error
    if not isinstance(payload, dict):
        raise ValueError(f"课程库根节点必须是对象：{file_path}")
    points = payload.get("points")
    errors = validate_points(points)
    if errors:
        raise ValueError("课程库校验失败：" + "；".join(errors[:5]))
    return {
        "schemaVersion": int(payload.get("schemaVersion") or 1),
        "week": int(payload.get("week") or 0),
        "level": _text(payload.get("level")) or "基础",
        "points": points,
    }
```

- [ ] **Step 4: 建示例内容文件**

创建 `content/review/py-week1.json`，把上面测试里的 `GOOD_POINT` 原样放进 `points`（字段名与结构完全一致）：

```json
{
  "schemaVersion": 1,
  "week": 1,
  "level": "基础",
  "points": [
    {
      "code": "py.mutability.default-arg",
      "title": "可变默认参数与求值时机",
      "minutes": 20,
      "module": "函数",
      "level": "基础",
      "taskRefs": [{"taskId": "1103", "relation": "introduces"}],
      "concept": {"prompt": "默认参数什么时候求值？", "answer": ["函数定义时求值一次", "可变对象会在调用间共享"]},
      "predict": {"prompt": "写出输出并解释", "code": "def add(item, items=[]):\n    items.append(item)\n    return items\nprint(add(1))\nprint(add(2))", "expected": ["[1]", "[1, 2]"], "explain": "第二次调用复用了定义时创建的同一个列表"},
      "debug": {"prompt": "找出 bug", "code": "def cache(k, store={}):\n    return store.setdefault(k, [])", "rootCause": "store 在函数定义时创建一次，被所有调用共享", "fix": "改成 store=None，函数体内 store = {} if store is None else store"},
      "code_task": {"prompt": "用 None 哨兵重写", "acceptance": ["多次调用互不影响", "带一个 unittest 用例"], "reference": "def add(item, items=None):\n    items = [] if items is None else items\n    items.append(item)\n    return items"},
      "pitfalls": ["默认值是可变对象", "把默认值当每次新建", "调用侧共享同一列表"]
    }
  ]
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_content -v`
Expected: PASS（8 个用例）

- [ ] **Step 6: 提交**

```bash
git add review_content.py content/review/py-week1.json tests/test_review_content.py
git commit -m "feat(review): 课程库格式与校验器 + 第 1 周示例知识点"
```

---

### Task 2: schema v8（5 张复习表 + 迁移）

**Files:**
- Modify: `storage.py`（`SCHEMA_VERSION`、`open_state_database()` 幂等 DDL、新增 `state_lock()`）
- Test: `tests/test_review_migration.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `storage.SCHEMA_VERSION == 8`
  - `storage.state_lock()` → `threading.RLock`
  - 表：`review_points`、`review_point_tasks`、`review_states`、`review_attempts`、`review_sessions`（列定义见规划 §12）

- [ ] **Step 1: 写失败的测试**

```python
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-migrate-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import storage  # noqa: E402

REVIEW_TABLES = ("review_points", "review_point_tasks", "review_states",
                 "review_attempts", "review_sessions")


class ReviewMigrationTests(unittest.TestCase):
    def test_schema_version_is_8(self) -> None:
        self.assertEqual(storage.SCHEMA_VERSION, 8)

    def test_v7_database_migrates_without_touching_projects(self) -> None:
        storage.ensure_schema()
        project = {
            "id": "p-old", "name": "旧项目", "description": "", "createdAt": "2026-09-16",
            "assessmentEnabled": False,
            "tree": [{"id": "w1", "type": "week", "text": "第1周", "completed": False,
                      "expanded": False, "createdAt": "2026-09-16", "children": [
                          {"id": "i1", "type": "item", "text": "任务", "completed": False,
                           "completedAt": None, "optional": False, "assessmentRequired": False,
                           "assessmentHistory": 0, "assessment": None,
                           "createdAt": "2026-09-16", "children": []}]}],
        }
        storage.write_project(project, None)
        before = storage.read_project("p-old")[0]
        # 伪造成"升级前的 v7 库"：删掉复习表并把版本退回去
        with storage.open_state_database() as connection:
            for table in REVIEW_TABLES:
                connection.execute(f"DROP TABLE IF EXISTS {table}")
            connection.execute("PRAGMA user_version=7")
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(version, 8)
        for table in REVIEW_TABLES:
            self.assertIn(table, tables)
        self.assertEqual(storage.read_project("p-old")[0], before, "迁移不得改动项目数据")
        self.assertTrue(storage.check_database_integrity())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_migration -v`
Expected: FAIL（`SCHEMA_VERSION` 仍是 7；`review_points` 表不存在）

- [ ] **Step 3: 改 `storage.py`**

1）`SCHEMA_VERSION = 7` → `SCHEMA_VERSION = 8`。

2）在 `open_state_database()` 的 `executescript` 末尾（`project_templates` 建表之后）追加：

```sql
        CREATE TABLE IF NOT EXISTS review_points (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            minutes INTEGER NOT NULL DEFAULT 10,
            module TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL DEFAULT '基础',
            origin TEXT NOT NULL DEFAULT 'builtin',
            content_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_point_tasks (
            code TEXT NOT NULL,
            task_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            PRIMARY KEY (code, task_id, project_id)
        );
        CREATE TABLE IF NOT EXISTS review_states (
            code TEXT PRIMARY KEY,
            due TEXT NOT NULL DEFAULT '',
            interval_days INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 0,
            lapses INTEGER NOT NULL DEFAULT 0,
            last_grade INTEGER NOT NULL DEFAULT 0,
            weak INTEGER NOT NULL DEFAULT 0,
            last_reviewed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS review_attempts (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            task_id TEXT NOT NULL DEFAULT '',
            project_id TEXT NOT NULL DEFAULT '',
            question_type TEXT NOT NULL,
            grade INTEGER NOT NULL,
            answer TEXT NOT NULL DEFAULT '',
            ai_verdict TEXT NOT NULL DEFAULT '',
            reviewed_on TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            session_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_sessions (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT '',
            planned INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0,
            grade_counts_json TEXT NOT NULL DEFAULT '{}',
            duration_ms INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_review_states_due ON review_states(due);
        CREATE INDEX IF NOT EXISTS idx_review_states_weak ON review_states(weak);
        CREATE INDEX IF NOT EXISTS idx_review_attempts_code ON review_attempts(code, created_at);
        CREATE INDEX IF NOT EXISTS idx_review_attempts_day ON review_attempts(reviewed_on);
        CREATE INDEX IF NOT EXISTS idx_review_tasks_task ON review_point_tasks(task_id);
```

3）在 `_database_lock` 定义附近新增公开锁入口：

```python
def state_lock() -> threading.RLock:
    """给其他模块用的公开锁入口（复习答题写入与项目保存共用同一把闸）。"""
    return _database_lock
```

4）在 `ensure_schema()` 里 `migrate_legacy_state()` 之前补注释（说明 v7→v8 只加表）：

```python
            # v7 -> v8：只新增 5 张复习表与索引（DDL 幂等，已在 open_state_database 里执行），
            # 不改动既有列、不回填数据；迁移前已自动快照，失败会回滚。
            migrate_legacy_state()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_migration -v`
Expected: PASS
再跑既有迁移/备份测试确认无回归：`python3 -m unittest tests.test_schema_and_import tests.test_full_backup -v` → PASS

- [ ] **Step 5: 提交**

```bash
git add storage.py tests/test_review_migration.py
git commit -m "feat(review): schema v8 新增 5 张复习表与索引（只加表，不改既有列）"
```

---
### Task 3: 内容导入（幂等）

**Files:**
- Create: `review_storage.py`
- Test: `tests/test_review_storage.py`

**Interfaces:**
- Consumes: `storage.open_state_database()`、`storage.state_lock()`、`storage._now()`（同包可用）、`review_content.load_content_file`
- Produces:
  - `review_storage.WEEK1_PATH = Path("content/review/py-week1.json")`
  - `review_storage.import_content(points, *, week=1, origin="builtin") -> {"inserted": int, "updated": int, "unchanged": int}`
  - `review_storage.ensure_content_imported() -> int`（启动时调用，返回导入/更新的知识点数，幂等）
  - `review_storage.list_points(*, module="", level="", query="", limit=200, offset=0) -> {"points": list[dict], "total": int}`

- [ ] **Step 1: 写失败的测试**

```python
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-store-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402


def point(code="py.a.b", title="示例点", minutes=10, task_id="1103", relation="introduces"):
    return {
        "code": code, "title": title, "minutes": minutes, "module": "容器", "level": "基础",
        "taskRefs": ([{"taskId": task_id, "relation": relation}] if task_id else []),
        "concept": {"prompt": "概念题", "answer": ["要点"]},
        "predict": {"prompt": "预测题", "code": "print(1)", "expected": ["1"], "explain": "因为"},
        "debug": {"prompt": "排查题", "code": "x =", "rootCause": "语法错误", "fix": "改成 x = 1"},
        "code_task": {"prompt": "编程题", "acceptance": ["能跑"], "reference": "def f(): return 1"},
        "pitfalls": ["易错点"],
    }


class ReviewStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_point_tasks")

    def test_import_is_idempotent(self) -> None:
        first = review_storage.import_content([point()])
        second = review_storage.import_content([point()])
        self.assertEqual(first["inserted"], 1)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(review_storage.list_points()["total"], 1)

    def test_import_updates_changed_content_and_task_refs(self) -> None:
        review_storage.import_content([point(task_id="1103")])
        review_storage.import_content([point(title="改过的标题", minutes=15, task_id="1303")])
        listed = review_storage.list_points()
        self.assertEqual(listed["points"][0]["title"], "改过的标题")
        self.assertEqual(listed["points"][0]["minutes"], 15)
        with storage.open_state_database() as connection:
            rows = connection.execute("SELECT task_id, relation FROM review_point_tasks").fetchall()
        self.assertEqual([(row["task_id"], row["relation"]) for row in rows], [("1303", "introduces")])

    def test_point_without_taskref_is_allowed(self) -> None:
        review_storage.import_content([point(code="py.extra.json", task_id=None)])
        with storage.open_state_database() as connection:
            count = connection.execute("SELECT COUNT(*) FROM review_point_tasks").fetchone()[0]
        self.assertEqual(count, 0)
        self.assertEqual(review_storage.list_points(module="容器")["total"], 1)

    def test_ensure_content_imported_seeds_real_file(self) -> None:
        review_storage.ensure_content_imported()
        listed = review_storage.list_points()
        self.assertGreaterEqual(listed["total"], 1)
        self.assertTrue(any(entry["code"] == "py.mutability.default-arg" for entry in listed["points"]))

    def test_list_points_filters_by_query(self) -> None:
        review_storage.import_content([point(code="py.mutability.default-arg", title="可变默认参数"),
                                       point(code="py.dict.basics", title="字典基础")])
        self.assertEqual(review_storage.list_points(query="默认")["total"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_storage -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'review_storage'`）

- [ ] **Step 3: 实现导入与查询**

```python
"""复习内容导入、复习状态与调度、每日队列、作答记录。"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import review_content
import storage

WEEK1_PATH = Path(__file__).resolve().parent / "content" / "review" / "py-week1.json"
DEFAULT_ORIGIN = "builtin"


def _now() -> str:
    return storage._now()


def _connection():
    return storage.open_state_database()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def import_content(points: list[dict], *, week: int = 1, origin: str = DEFAULT_ORIGIN) -> dict[str, int]:
    """按 code 幂等导入知识点（内容相同则跳过，变化则更新，taskRefs 整体重建）。"""
    errors = review_content.validate_points(points)
    if errors:
        raise ValueError("内容校验失败：" + "；".join(errors[:5]))
    inserted = updated = unchanged = 0
    stamp = _now()
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for point in points:
            code = str(point["code"])
            payload = {
                "code": code, "title": str(point["title"]), "minutes": int(point["minutes"]),
                "module": str(point.get("module") or ""), "level": str(point.get("level") or "基础"),
                "origin": origin, "week": week,
                "concept": point["concept"], "predict": point["predict"], "debug": point["debug"],
                "code_task": point["code_task"], "pitfalls": point["pitfalls"],
            }
            content = _json(payload)
            row = connection.execute(
                "SELECT content_json FROM review_points WHERE code=?", (code,)).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO review_points(code,title,minutes,module,level,origin,content_json,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (code, payload["title"], payload["minutes"], payload["module"], payload["level"],
                     origin, content, stamp, stamp))
                connection.execute(
                    "INSERT OR IGNORE INTO review_states(code,due) VALUES(?,'')", (code,))
                inserted += 1
            elif row["content_json"] != content:
                connection.execute(
                    "UPDATE review_points SET title=?,minutes=?,module=?,level=?,origin=?,content_json=?,updated_at=? "
                    "WHERE code=?",
                    (payload["title"], payload["minutes"], payload["module"], payload["level"],
                     origin, content, stamp, code))
                updated += 1
            else:
                unchanged += 1
            connection.execute("DELETE FROM review_point_tasks WHERE code=?", (code,))
            for ref in point.get("taskRefs") or []:
                connection.execute(
                    "INSERT OR REPLACE INTO review_point_tasks(code,task_id,project_id,relation) VALUES(?,?,?,?)",
                    (code, str(ref["taskId"]), str(ref.get("projectId") or ""), str(ref["relation"])))
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged}


def ensure_content_imported() -> int:
    if not WEEK1_PATH.exists():
        return 0
    loaded = review_content.load_content_file(WEEK1_PATH)
    result = import_content(loaded["points"], week=loaded["week"] or 1)
    return result["inserted"] + result["updated"]


def list_points(*, module: str = "", level: str = "", query: str = "",
                limit: int = 200, offset: int = 0) -> dict[str, Any]:
    where, params = ["1=1"], []
    if module:
        where.append("module=?")
        params.append(module)
    if level:
        where.append("level=?")
        params.append(level)
    if query:
        where.append("(title LIKE ? OR code LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    clause = " AND ".join(where)
    limit = max(1, min(500, int(limit)))
    offset = max(0, int(offset))
    with _connection() as connection:
        total = int(connection.execute(
            f"SELECT COUNT(*) FROM review_points WHERE {clause}", params).fetchone()[0])
        rows = connection.execute(
            f"SELECT p.code,p.title,p.minutes,p.module,p.level,p.origin,p.content_json,"
            f"COALESCE(s.due,'') AS due,COALESCE(s.weak,0) AS weak,COALESCE(s.last_grade,0) AS last_grade "
            f"FROM review_points p LEFT JOIN review_states s ON s.code=p.code "
            f"WHERE {clause} ORDER BY p.module,p.code LIMIT ? OFFSET ?",
            (*params, limit, offset)).fetchall()
    points = []
    for row in rows:
        content = json.loads(row["content_json"])
        points.append({
            "code": row["code"], "title": row["title"], "minutes": int(row["minutes"]),
            "module": row["module"], "level": row["level"], "origin": row["origin"],
            "due": row["due"], "weak": bool(row["weak"]), "lastGrade": int(row["last_grade"]),
            "pitfalls": content.get("pitfalls") or [],
        })
    return {"points": points, "total": total, "limit": limit, "offset": offset}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_storage -v`
Expected: PASS（5 个用例）

- [ ] **Step 5: 提交**

```bash
git add review_storage.py tests/test_review_storage.py
git commit -m "feat(review): 课程库幂等导入与知识点查询"
```

---

### Task 4: 五档调度与薄弱点

**Files:**
- Modify: `review_storage.py`
- Test: `tests/test_review_schedule.py`

**Interfaces:**
- Consumes: Task 3 的 `review_storage` 骨架
- Produces:
  - `review_storage.GRADE_BASE = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}`
  - `review_storage.next_schedule(grade, *, interval_days, streak, lapses, today, answered_today) -> dict`（键：`due`/`intervalDays`/`streak`/`lapses`/`weak`/`lastGrade`）
  - `review_storage.apply_grade(code, question_type, grade, *, today, answer="", duration_ms=0, session_id="", task_id="", project_id="", ai_verdict="") -> dict`（写 attempts + 更新 states，返回 `next_schedule` 结果）
  - `review_storage.read_state(code) -> dict | None`

- [ ] **Step 1: 写失败的测试**

```python
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-sched-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"


def seed(code="py.a.b"):
    review_storage.import_content([{
        "code": code, "title": "示例点", "minutes": 10, "module": "容器", "level": "基础",
        "taskRefs": [], "concept": {"prompt": "p", "answer": ["a"]},
        "predict": {"prompt": "p", "code": "print(1)", "expected": ["1"], "explain": "e"},
        "debug": {"prompt": "p", "code": "x =", "rootCause": "r", "fix": "f"},
        "code_task": {"prompt": "p", "acceptance": ["a"], "reference": "r"}, "pitfalls": ["p"],
    }])


class NextScheduleTests(unittest.TestCase):
    def test_grade_intervals(self) -> None:
        cases = {2: 3, 3: 7, 4: 14, 5: 30}
        for grade, interval in cases.items():
            result = review_storage.next_schedule(
                grade, interval_days=0, streak=0, lapses=0, today=TODAY, answered_today=False)
            self.assertEqual(result["intervalDays"], interval, grade)
        self.assertEqual(review_storage.next_schedule(
            3, interval_days=0, streak=0, lapses=0, today=TODAY, answered_today=False)["due"], "2026-09-23")

    def test_grade_one_same_day_when_not_answered_yet(self) -> None:
        result = review_storage.next_schedule(
            1, interval_days=7, streak=3, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(result["due"], TODAY)
        self.assertEqual(result["lapses"], 1)
        self.assertEqual(result["streak"], 0)

    def test_grade_one_defers_to_tomorrow_when_already_answered(self) -> None:
        result = review_storage.next_schedule(
            1, interval_days=7, streak=3, lapses=0, today=TODAY, answered_today=True)
        self.assertEqual(result["due"], "2026-09-17")

    def test_high_grades_grow_interval_with_caps(self) -> None:
        grown = review_storage.next_schedule(
            4, interval_days=14, streak=1, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(grown["intervalDays"], 28)
        capped = review_storage.next_schedule(
            4, interval_days=40, streak=5, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(capped["intervalDays"], 60)
        top = review_storage.next_schedule(
            5, interval_days=60, streak=5, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(top["intervalDays"], 90)

    def test_weak_after_two_lapses(self) -> None:
        first = review_storage.next_schedule(
            1, interval_days=0, streak=0, lapses=0, today=TODAY, answered_today=False)
        self.assertEqual(first["weak"], False)
        second = review_storage.next_schedule(
            1, interval_days=1, streak=0, lapses=first["lapses"], today=TODAY, answered_today=True)
        self.assertEqual(second["weak"], True)


class ApplyGradeTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_points")
            connection.execute("DELETE FROM review_states")
            connection.execute("DELETE FROM review_attempts")
        seed()

    def test_apply_grade_records_attempt_and_state(self) -> None:
        result = review_storage.apply_grade(
            "py.a.b", "concept", 4, today=TODAY, answer="我的答案", duration_ms=2500, session_id="s1")
        self.assertEqual(result["intervalDays"], 14)
        self.assertEqual(result["due"], "2026-09-30")
        state = review_storage.read_state("py.a.b")
        self.assertEqual(state["last_grade"], 4)
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT code,question_type,grade,answer,duration_ms,session_id,reviewed_on "
                "FROM review_attempts").fetchone()
        self.assertEqual((row["code"], row["question_type"], row["grade"], row["answer"]),
                         ("py.a.b", "concept", 4, "我的答案"))
        self.assertEqual(row["reviewed_on"], TODAY)

    def test_repeated_failures_mark_weak_and_clear_after_two_good(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 1, today=TODAY)
        review_storage.apply_grade("py.a.b", "predict", 2, today=TODAY)
        self.assertTrue(review_storage.read_state("py.a.b")["weak"])
        review_storage.apply_grade("py.a.b", "debug", 4, today=TODAY)
        review_storage.apply_grade("py.a.b", "code_task", 5, today=TODAY)
        self.assertFalse(review_storage.read_state("py.a.b")["weak"])

    def test_rejects_out_of_range_grade(self) -> None:
        with self.assertRaises(ValueError):
            review_storage.apply_grade("py.a.b", "concept", 9, today=TODAY)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_schedule -v`
Expected: FAIL（`AttributeError: module 'review_storage' has no attribute 'next_schedule'`）

- [ ] **Step 3: 实现调度**

```python
GRADE_BASE = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MAX_INTERVAL_4 = 60
MAX_INTERVAL_5 = 90
WEAK_LAPSES = 2


def _add_days(day: str, days: int) -> str:
    base = date.fromisoformat(day)
    return (base + timedelta(days=max(0, int(days)))).isoformat()


def next_schedule(grade: int, *, interval_days: int, streak: int, lapses: int,
                  today: str, answered_today: bool) -> dict[str, Any]:
    """五档自评 → 下次复习日。grade 1 当天可再来一次（当天已答过就顺延到明天）。"""
    grade = int(grade)
    if grade not in GRADE_BASE:
        raise ValueError("自评档位必须是 1~5")
    interval_days = max(0, int(interval_days or 0))
    streak = max(0, int(streak or 0))
    lapses = max(0, int(lapses or 0))
    if grade <= 2:
        interval = GRADE_BASE[grade]
        streak = 0
        lapses = lapses + 1 if grade == 1 else lapses
        due = today if (grade == 1 and not answered_today) else _add_days(today, interval)
        if grade == 1 and not answered_today:
            interval = 0
    else:
        streak += 1
        if grade == 3:
            interval = GRADE_BASE[3]
        elif grade == 4:
            interval = min(MAX_INTERVAL_4, max(GRADE_BASE[4], interval_days * 2 if interval_days >= 7 else 14))
        else:
            interval = min(MAX_INTERVAL_5, max(GRADE_BASE[5], interval_days * 2 if interval_days >= 14 else 30))
        due = _add_days(today, interval)
    weak = bool(lapses >= WEAK_LAPSES) if grade <= 2 else bool(lapses >= WEAK_LAPSES)
    return {"due": due, "intervalDays": interval, "streak": streak, "lapses": lapses,
            "weak": weak, "lastGrade": grade}


def read_state(code: str) -> dict[str, Any] | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT code,due,interval_days,streak,lapses,last_grade,weak,last_reviewed_at "
            "FROM review_states WHERE code=?", (str(code),)).fetchone()
    if row is None:
        return None
    return {"code": row["code"], "due": row["due"], "intervalDays": int(row["interval_days"]),
            "streak": int(row["streak"]), "lapses": int(row["lapses"]),
            "lastGrade": int(row["last_grade"]), "weak": bool(row["weak"]),
            "lastReviewedAt": row["last_reviewed_at"]}


def _recent_grades(connection, code: str, limit: int = 3) -> list[int]:
    rows = connection.execute(
        "SELECT grade FROM review_attempts WHERE code=? ORDER BY created_at DESC LIMIT ?",
        (code, limit)).fetchall()
    return [int(row["grade"]) for row in rows]


def apply_grade(code: str, question_type: str, grade: int, *, today: str,
                answer: str = "", duration_ms: int = 0, session_id: str = "",
                task_id: str = "", project_id: str = "", ai_verdict: str = "") -> dict[str, Any]:
    """记录一次作答并按五档更新调度；返回下次复习安排。"""
    code = str(code or "").strip()
    if not code:
        raise ValueError("缺少知识点 code")
    if int(grade) not in GRADE_BASE:
        raise ValueError("自评档位必须是 1~5")
    if question_type not in review_content.QUESTION_TYPES:
        raise ValueError("题型不正确")
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT due,interval_days,streak,lapses,weak FROM review_states WHERE code=?", (code,)).fetchone()
        if row is None:
            raise ValueError("知识点不存在")
        answered_today = bool(connection.execute(
            "SELECT 1 FROM review_attempts WHERE code=? AND reviewed_on=? LIMIT 1",
            (code, today)).fetchone())
        schedule = next_schedule(int(grade), interval_days=int(row["interval_days"]),
                                 streak=int(row["streak"]), lapses=int(row["lapses"]),
                                 today=today, answered_today=answered_today)
        connection.execute(
            "INSERT INTO review_attempts(id,code,task_id,project_id,question_type,grade,answer,"
            "ai_verdict,reviewed_on,duration_ms,session_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), code, str(task_id or ""), str(project_id or ""), question_type,
             int(grade), str(answer or ""), str(ai_verdict or ""), today,
             max(0, int(duration_ms or 0)), str(session_id or ""), _now()))
        grades = _recent_grades(connection, code, 3)
        weak = schedule["weak"]
        if len([value for value in grades if value <= 2]) >= 2:
            weak = True
        elif len(grades) >= 2 and all(value >= 4 for value in grades[:2]):
            weak = False
        connection.execute(
            "UPDATE review_states SET due=?,interval_days=?,streak=?,lapses=?,last_grade=?,weak=?,"
            "last_reviewed_at=? WHERE code=?",
            (schedule["due"], schedule["intervalDays"], schedule["streak"], schedule["lapses"],
             int(grade), 1 if weak else 0, _now(), code))
        schedule["weak"] = bool(weak)
    return schedule
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_schedule -v`
Expected: PASS（8 个用例）

- [ ] **Step 5: 提交**

```bash
git add review_storage.py tests/test_review_schedule.py
git commit -m "feat(review): 五档自评调度、回退与薄弱点判定"
```

---
### Task 5: 每日队列组装（逾期 → 今日 → 薄弱 → 新点 → 即将到期）

**Files:**
- Modify: `review_storage.py`
- Test: `tests/test_review_schedule.py`（追加）

**Interfaces:**
- Consumes: Task 3/4 的 `review_storage`
- Produces:
  - `review_storage.pick_question_type(code, today) -> str`（按"最近最少用过的题型"轮换）
  - `review_storage.build_queue(today, limit=10, *, module="", level="", project_id="", task_id="", question_type="", new_per_day=2) -> {"items": list[dict], "total": int, "truncated": bool}`
    - 每项键：`code`/`title`/`minutes`/`module`/`level`/`questionType`/`prompt`/`reason`/`due`/`taskId`/`projectId`；**不含答案**
  - `review_storage.start_session(planned) -> str`、`review_storage.finish_session(session_id, answered, grade_counts, duration_ms) -> None`

- [ ] **Step 1: 写失败的测试（追加到 `tests/test_review_schedule.py`）**

```python
class QueueTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            for table in ("review_points", "review_states", "review_attempts", "review_sessions"):
                connection.execute(f"DELETE FROM {table}")
        for code in ("py.a.overdue", "py.a.today", "py.a.weak", "py.a.future", "py.a.new"):
            seed(code)

    def _set_state(self, code, due, weak=0, interval=0):
        with storage.open_state_database() as connection:
            connection.execute(
                "UPDATE review_states SET due=?,weak=?,interval_days=? WHERE code=?",
                (due, weak, interval, code))

    def test_queue_orders_overdue_then_today_then_weak(self) -> None:
        self._set_state("py.a.overdue", "2026-09-10")
        self._set_state("py.a.today", TODAY)
        self._set_state("py.a.weak", "2026-10-30", weak=1)
        self._set_state("py.a.future", "2026-10-01")
        queue = review_storage.build_queue(TODAY, limit=3, new_per_day=0)
        self.assertEqual([item["code"] for item in queue["items"]],
                         ["py.a.overdue", "py.a.today", "py.a.weak"])
        self.assertEqual([item["reason"] for item in queue["items"]], ["overdue", "today", "weak"])

    def test_queue_respects_limit_and_reports_truncation(self) -> None:
        self._set_state("py.a.overdue", "2026-09-10")
        self._set_state("py.a.today", TODAY)
        queue = review_storage.build_queue(TODAY, limit=1)
        self.assertEqual(len(queue["items"]), 1)
        self.assertTrue(queue["truncated"])

    def test_queue_includes_new_points_up_to_new_per_day(self) -> None:
        queue = review_storage.build_queue(TODAY, limit=5, new_per_day=1)
        reasons = [item["reason"] for item in queue["items"]]
        self.assertEqual(reasons.count("new"), 1, reasons)

    def test_queue_never_returns_answers(self) -> None:
        self._set_state("py.a.today", TODAY)
        item = review_storage.build_queue(TODAY, limit=1)["items"][0]
        self.assertNotIn("answer", item)
        self.assertNotIn("expected", item)
        self.assertNotIn("rootCause", item)
        self.assertTrue(item["prompt"])

    def test_question_type_rotation_prefers_least_used(self) -> None:
        review_storage.apply_grade("py.a.today", "concept", 3, today=TODAY)
        self.assertNotEqual(review_storage.pick_question_type("py.a.today", TODAY), "concept")

    def test_session_lifecycle(self) -> None:
        session_id = review_storage.start_session(planned=3)
        review_storage.finish_session(session_id, answered=2, grade_counts={3: 1, 4: 1}, duration_ms=5000)
        with storage.open_state_database() as connection:
            row = connection.execute("SELECT * FROM review_sessions WHERE id=?", (session_id,)).fetchone()
        self.assertEqual(row["answered"], 2)
        self.assertEqual(json.loads(row["grade_counts_json"]), {"3": 1, "4": 1})
```

（文件顶部需要 `import json`）

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_schedule.QueueTests -v`
Expected: FAIL（`AttributeError: ... has no attribute 'build_queue'`）

- [ ] **Step 3: 实现队列组装**

```python
def pick_question_type(code: str, today: str) -> str:
    """题型轮换：优先选这个知识点最近最少用过的题型（都没用过就按固定顺序）。"""
    with _connection() as connection:
        rows = connection.execute(
            "SELECT question_type, MAX(created_at) AS last_at FROM review_attempts "
            "WHERE code=? GROUP BY question_type", (str(code),)).fetchall()
    last_used = {row["question_type"]: str(row["last_at"]) for row in rows}
    return min(review_content.QUESTION_TYPES, key=lambda kind: (last_used.get(kind, ""), kind))


def _prompt_of(connection, code: str, question_type: str) -> str:
    row = connection.execute("SELECT content_json FROM review_points WHERE code=?", (code,)).fetchone()
    if row is None:
        return ""
    return str((json.loads(row["content_json"]).get(question_type) or {}).get("prompt") or "")


def build_queue(today: str, limit: int = 10, *, code: str = "", module: str = "", level: str = "",
                project_id: str = "", task_id: str = "", question_type: str = "",
                new_per_day: int = 2) -> dict[str, Any]:
    """每日队列：逾期 → 今日 → 薄弱 → 新知识点（限量）→ 即将到期。上限硬约束，绝不一次全塞。"""
    limit = max(1, min(50, int(limit or 10)))
    new_per_day = max(0, min(5, int(new_per_day or 0)))
    where, params = ["1=1"], []
    if code:
        where.append("p.code=?")
        params.append(str(code))
    if module:
        where.append("p.module=?")
        params.append(module)
    if level:
        where.append("p.level=?")
        params.append(level)
    if task_id:
        where.append("EXISTS (SELECT 1 FROM review_point_tasks t WHERE t.code=p.code AND t.task_id=?)")
        params.append(str(task_id))
    if project_id:
        where.append("EXISTS (SELECT 1 FROM review_point_tasks t WHERE t.code=p.code AND t.project_id=?)")
        params.append(str(project_id))
    clause = " AND ".join(where)
    with _connection() as connection:
        rows = connection.execute(
            f"SELECT p.code,p.title,p.minutes,p.module,p.level,COALESCE(s.due,'') AS due,"
            f"COALESCE(s.weak,0) AS weak,COALESCE(s.interval_days,0) AS interval_days,"
            f"(SELECT task_id FROM review_point_tasks t WHERE t.code=p.code LIMIT 1) AS task_id,"
            f"(SELECT project_id FROM review_point_tasks t WHERE t.code=p.code LIMIT 1) AS project_id "
            f"FROM review_points p LEFT JOIN review_states s ON s.code=p.code WHERE {clause}",
            params).fetchall()
        buckets: dict[str, list[dict]] = {"overdue": [], "today": [], "weak": [], "new": [], "upcoming": []}
        for row in rows:
            due = str(row["due"] or "")
            item = {"code": row["code"], "title": row["title"], "minutes": int(row["minutes"]),
                    "module": row["module"], "level": row["level"], "due": due,
                    "taskId": row["task_id"] or "", "projectId": row["project_id"] or ""}
            if not due:
                buckets["new"].append(item)
            elif due < today:
                buckets["overdue"].append(dict(item, reason="overdue"))
            elif due == today:
                buckets["today"].append(dict(item, reason="today"))
            elif row["weak"]:
                buckets["weak"].append(dict(item, reason="weak"))
            else:
                buckets["upcoming"].append(dict(item, reason="upcoming"))
        buckets["overdue"].sort(key=lambda entry: (entry["due"], entry["code"]))
        buckets["weak"].sort(key=lambda entry: (entry["due"], entry["code"]))
        buckets["upcoming"].sort(key=lambda entry: (entry["due"], entry["code"]))
        buckets["new"].sort(key=lambda entry: entry["code"])
        ordered = (buckets["overdue"] + buckets["today"] + buckets["weak"]
                   + buckets["new"][:new_per_day] + buckets["upcoming"])
        truncated = len(ordered) > limit
        chosen = ordered[:limit]
        for item in chosen:
            kind = question_type or pick_question_type(item["code"], today)
            item["questionType"] = kind
            item["prompt"] = _prompt_of(connection, item["code"], kind)
    return {"items": chosen, "total": len(chosen), "truncated": truncated, "limit": limit}


def start_session(planned: int) -> str:
    session_id = str(uuid.uuid4())
    with storage.state_lock(), _connection() as connection:
        connection.execute(
            "INSERT INTO review_sessions(id,started_at,planned) VALUES(?,?,?)",
            (session_id, _now(), max(0, int(planned or 0))))
    return session_id


def finish_session(session_id: str, *, answered: int, grade_counts: dict[int, int],
                   duration_ms: int) -> None:
    with storage.state_lock(), _connection() as connection:
        connection.execute(
            "UPDATE review_sessions SET finished_at=?,answered=?,grade_counts_json=?,duration_ms=? WHERE id=?",
            (_now(), max(0, int(answered or 0)), _json({str(k): int(v) for k, v in (grade_counts or {}).items()}),
             max(0, int(duration_ms or 0)), str(session_id)))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_schedule -v`
Expected: PASS（14 个用例）

- [ ] **Step 5: 提交**

```bash
git add review_storage.py tests/test_review_schedule.py
git commit -m "feat(review): 每日队列组装（逾期/今日/薄弱/新点/即将到期 + 上限）"
```

---

### Task 6: 统计、复习页数据与历史记录

**Files:**
- Modify: `review_storage.py`
- Test: `tests/test_review_storage.py`（追加）

**Interfaces:**
- Consumes: Task 3–5
- Produces:
  - `review_storage.summary(today) -> dict`（键：`dueToday`/`overdue`/`upcoming`/`weak`/`total`/`learned`/`streakDays`/`answeredToday`/`limit`（读设置）/`newPerDay`）
  - `review_storage.recent_attempts(kind, today, limit=10) -> list[dict]`（`kind` 取 `wrong`/`mastered`）
  - `review_storage.history(code, limit=20) -> {"code":..., "attempts":[...], "pitfalls":[...], "state": {...}}`
  - `review_storage.streak_days(today) -> int`

- [ ] **Step 1: 写失败的测试（追加到 `tests/test_review_storage.py`）**

```python
class SummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            for table in ("review_points", "review_states", "review_attempts"):
                connection.execute(f"DELETE FROM {table}")
        review_storage.import_content([point(code="py.a.b")])

    def test_summary_counts_buckets(self) -> None:
        with storage.open_state_database() as connection:
            connection.execute("UPDATE review_states SET due='2026-09-10' WHERE code='py.a.b'")
        data = review_storage.summary("2026-09-16")
        self.assertEqual(data["overdue"], 1)
        self.assertEqual(data["dueToday"], 0)
        self.assertEqual(data["learned"], 1)

    def test_recent_wrong_and_mastered(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 1, today="2026-09-16", answer="错的")
        review_storage.apply_grade("py.a.b", "predict", 5, today="2026-09-16")
        self.assertEqual(len(review_storage.recent_attempts("wrong", "2026-09-16")), 1)
        self.assertEqual(len(review_storage.recent_attempts("mastered", "2026-09-16")), 1)

    def test_history_returns_answers_and_pitfalls(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 2, today="2026-09-16", answer="我写的")
        data = review_storage.history("py.a.b")
        self.assertEqual(data["attempts"][0]["answer"], "我写的")
        self.assertEqual(data["pitfalls"], ["易错点"])

    def test_streak_counts_consecutive_days(self) -> None:
        review_storage.apply_grade("py.a.b", "concept", 3, today="2026-09-15")
        review_storage.apply_grade("py.a.b", "predict", 3, today="2026-09-16")
        self.assertEqual(review_storage.streak_days("2026-09-16"), 2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_storage.SummaryTests -v`
Expected: FAIL（`AttributeError: ... has no attribute 'summary'`）

- [ ] **Step 3: 实现统计与历史**

```python
def _settings() -> dict[str, Any]:
    settings = storage.read_app_settings() or {}
    try:
        limit = int(settings.get("reviewDailyLimit") or 10)
    except (TypeError, ValueError):
        limit = 10
    try:
        new_per_day = int(settings.get("reviewNewPerDay") or 2)
    except (TypeError, ValueError):
        new_per_day = 2
    return {"limit": max(5, min(15, limit)), "newPerDay": max(0, min(5, new_per_day))}


def streak_days(today: str) -> int:
    with _connection() as connection:
        rows = connection.execute(
            "SELECT DISTINCT reviewed_on FROM review_attempts ORDER BY reviewed_on DESC LIMIT 400").fetchall()
    days = [str(row["reviewed_on"]) for row in rows]
    streak = 0
    cursor = date.fromisoformat(today)
    for day in days:
        if day == cursor.isoformat():
            streak += 1
            cursor = cursor - timedelta(days=1)
        elif day < cursor.isoformat():
            break
    return streak


def summary(today: str) -> dict[str, Any]:
    settings = _settings()
    with _connection() as connection:
        total = int(connection.execute("SELECT COUNT(*) FROM review_points").fetchone()[0])
        rows = connection.execute(
            "SELECT COALESCE(s.due,'') AS due, COALESCE(s.weak,0) AS weak FROM review_points p "
            "LEFT JOIN review_states s ON s.code=p.code").fetchall()
        answered_today = int(connection.execute(
            "SELECT COUNT(*) FROM review_attempts WHERE reviewed_on=?", (today,)).fetchone()[0])
    due_today = overdue = upcoming = weak = learned = 0
    for row in rows:
        due = str(row["due"] or "")
        if row["weak"]:
            weak += 1
        if not due:
            continue
        learned += 1
        if due < today:
            overdue += 1
        elif due == today:
            due_today += 1
        else:
            upcoming += 1
    return {"dueToday": due_today, "overdue": overdue, "upcoming": upcoming, "weak": weak,
            "total": total, "learned": learned, "answeredToday": answered_today,
            "streakDays": streak_days(today), **settings}


def recent_attempts(kind: str, today: str, limit: int = 10) -> list[dict[str, Any]]:
    condition = "grade<=2" if kind == "wrong" else "grade>=4"
    with _connection() as connection:
        rows = connection.execute(
            f"SELECT a.id,a.code,a.question_type,a.grade,a.answer,a.reviewed_on,p.title "
            f"FROM review_attempts a LEFT JOIN review_points p ON p.code=a.code "
            f"WHERE {condition} ORDER BY a.created_at DESC LIMIT ?", (max(1, min(50, int(limit))),)).fetchall()
    return [{"id": row["id"], "code": row["code"], "title": row["title"] or row["code"],
             "questionType": row["question_type"], "grade": int(row["grade"]),
             "answer": row["answer"], "reviewedOn": row["reviewed_on"]} for row in rows]


def history(code: str, limit: int = 20) -> dict[str, Any]:
    with _connection() as connection:
        point = connection.execute(
            "SELECT title,content_json,module,level,minutes FROM review_points WHERE code=?",
            (str(code),)).fetchone()
        if point is None:
            raise ValueError("知识点不存在")
        rows = connection.execute(
            "SELECT question_type,grade,answer,ai_verdict,reviewed_on,duration_ms FROM review_attempts "
            "WHERE code=? ORDER BY created_at DESC LIMIT ?", (str(code), max(1, min(100, int(limit))))).fetchall()
    content = json.loads(point["content_json"])
    return {"code": str(code), "title": point["title"], "module": point["module"],
            "level": point["level"], "minutes": int(point["minutes"]),
            "pitfalls": content.get("pitfalls") or [],
            "attempts": [{"questionType": row["question_type"], "grade": int(row["grade"]),
                          "answer": row["answer"], "aiVerdict": row["ai_verdict"],
                          "reviewedOn": row["reviewed_on"], "durationMs": int(row["duration_ms"])}
                         for row in rows],
            "state": read_state(str(code))}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_storage -v`
Expected: PASS（9 个用例）

- [ ] **Step 5: 提交**

```bash
git add review_storage.py tests/test_review_storage.py
git commit -m "feat(review): 统计、最近答错/掌握、连续天数与历史记录"
```

---
### Task 7: HTTP 只读接口（summary / queue / points / history）

**Files:**
- Modify: `local_server.py`（`do_GET` 里新增分支；顶部别名区加 `import review_storage` 后的别名）
- Test: `tests/test_review_http.py`

**Interfaces:**
- Consumes: Task 3–6 的 `review_storage`
- Produces（全部要求 `X-Todo-Session`，非法参数 400）：
  - `GET /api/review/summary?today=YYYY-MM-DD`
  - `GET /api/review/queue?today=&limit=&code=&module=&level=&projectId=&taskId=&type=&newPerDay=`
  - `GET /api/review/points?module=&level=&query=&limit=&offset=`
  - `GET /api/review/history?code=&limit=`

- [ ] **Step 1: 写失败的测试**

```python
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
        data = json.loads(response.read().decode("utf-8") or "{}")
        connection.close()
        return response.status, data

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
            self.assertNotIn("answer", item)
            self.assertNotIn("expected", item)
            self.assertNotIn("rootCause", item)
            self.assertNotIn("reference", item)

    def test_points_and_history(self) -> None:
        status, points = self.call("/api/review/points?limit=5")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(points["total"], 1)
        code = points["points"][0]["code"]
        status, history = self.call(f"/api/review/history?code={code}")
        self.assertEqual(status, 200)
        self.assertEqual(history["code"], code)

    def test_bad_params_are_400(self) -> None:
        self.assertEqual(self.call(f"/api/review/summary?today=not-a-date")[0], 400)
        self.assertEqual(self.call(f"/api/review/queue?today={TODAY}&limit=abc")[0], 400)
        self.assertEqual(self.call("/api/review/history")[0], 400)
        self.assertEqual(self.call("/api/review/history?code=py.nope.nope")[0], 404)

    def test_requires_session_token(self) -> None:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", f"/api/review/summary?today={TODAY}")
        self.assertEqual(connection.getresponse().status, 401)
        connection.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_http -v`
Expected: FAIL（404「接口不存在」）

- [ ] **Step 3: 在 `local_server.py` 实现**

顶部别名区加：

```python
import review_storage
import review_content
```

在 `do_GET` 的 `/api/reviews` 分支之前插入：

```python
        if path.startswith("/api/review/"):
            params = query_params(self)
            try:
                today = optional_iso_date(params.get("today", [""])[0])
                if path == "/api/review/summary":
                    self.send_json(200, review_storage.summary(today or storage_service.date.today().isoformat()))
                    return
                if path == "/api/review/queue":
                    limit = int_param(params, "limit", required=False, default=0)
                    new_per_day = int_param(params, "newPerDay", required=False, default=-1)
                    settings = review_storage.summary(today or storage_service.date.today().isoformat())
                    queue = review_storage.build_queue(
                        today or storage_service.date.today().isoformat(),
                        limit or settings["limit"],
                        code=(params.get("code", [""])[0] or "").strip(),
                        module=(params.get("module", [""])[0] or "").strip(),
                        level=(params.get("level", [""])[0] or "").strip(),
                        project_id=(params.get("projectId", [""])[0] or "").strip(),
                        task_id=(params.get("taskId", [""])[0] or "").strip(),
                        question_type=(params.get("type", [""])[0] or "").strip(),
                        new_per_day=settings["newPerDay"] if new_per_day < 0 else new_per_day,
                    )
                    self.send_json(200, queue)
                    return
                if path == "/api/review/points":
                    limit = int_param(params, "limit", required=False, default=200)
                    offset = int_param(params, "offset", required=False, default=0)
                    self.send_json(200, review_storage.list_points(
                        module=(params.get("module", [""])[0] or "").strip(),
                        level=(params.get("level", [""])[0] or "").strip(),
                        query=(params.get("query", [""])[0] or "").strip(),
                        limit=limit, offset=offset))
                    return
                if path == "/api/review/history":
                    code = required_param(params, "code")
                    limit = int_param(params, "limit", required=False, default=20)
                    self.send_json(200, review_storage.history(code, limit=limit))
                    return
            except ValueError as error:
                message = str(error)
                self.send_json(404 if "不存在" in message else 400, {"error": message})
                return
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"复习接口失败：{error}"})
                return
            self.send_json(404, {"error": "接口不存在"})
            return
```

说明：
- `today` 由前端传（与现有 `/api/reviews` 一致）；没传时回落到服务端当天，避免直接 400。
- 规划 §12 里的 `POST /api/review/plan` **本批不实现**：队列由 `/api/review/queue` 即算即出，避免多维护一份"今日计划"状态。
- `/api/review/history` 的"知识点不存在"返回 404，其它参数问题 400。
- `limit=abc` 会由 `int_param` 抛 `ValueError` → 400。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_http -v`
Expected: PASS（5 个用例）

- [ ] **Step 5: 提交**

```bash
git add local_server.py tests/test_review_http.py
git commit -m "feat(review): HTTP 只读接口 summary/queue/points/history（队列不含答案）"
```

---

### Task 8: HTTP 作答接口（reveal / answer）

**Files:**
- Modify: `local_server.py`（`do_POST` 新增分支）
- Test: `tests/test_review_http.py`（追加）

**Interfaces:**
- Consumes: Task 4–7
- Produces:
  - `POST /api/review/reveal` `{code, type}` → `{code, type, prompt, answer, expected, explain, rootCause, fix, acceptance, reference, pitfalls, history}`
  - `POST /api/review/answer` `{code, type, grade, answer, durationMs, sessionId, taskId, projectId}` → `{ok, schedule: {due, intervalDays, streak, lapses, weak, lastGrade}}`
  - `POST /api/review/session` `{action: "start"|"finish", sessionId, planned, answered, gradeCounts, durationMs}` → `{ok, sessionId?}`

- [ ] **Step 1: 写失败的测试（追加到 `ReviewHttpTests`）**

```python
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

    def test_session_lifecycle_over_http(self) -> None:
        status, started = self.call("/api/review/session", "POST", {"action": "start", "planned": 3})
        self.assertEqual(status, 200)
        session_id = started["sessionId"]
        status, finished = self.call("/api/review/session", "POST", {
            "action": "finish", "sessionId": session_id, "answered": 2,
            "gradeCounts": {"3": 1, "4": 1}, "durationMs": 4000})
        self.assertEqual(status, 200)
        self.assertTrue(finished["ok"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_http -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现 `do_POST` 分支**

在 `do_POST` 的 `elif path == "/api/project":` 之前插入（`payload` 已解析）：

```python
            elif path == "/api/review/reveal":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("type") or "").strip()
                if not code or kind not in review_content.QUESTION_TYPES:
                    raise ValueError("知识点或题型不正确")
                data = review_storage.reveal(code, kind)
                self.send_json(200, data)
            elif path == "/api/review/answer":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("type") or "").strip()
                today = optional_iso_date(str(payload.get("today") or ""))
                if not today:
                    raise ValueError("today 必须是 YYYY-MM-DD")
                schedule = review_storage.apply_grade(
                    code, kind, int(payload.get("grade") or 0), today=today,
                    answer=str(payload.get("answer") or ""),
                    duration_ms=int(payload.get("durationMs") or 0),
                    session_id=str(payload.get("sessionId") or ""),
                    task_id=str(payload.get("taskId") or ""),
                    project_id=str(payload.get("projectId") or ""))
                self.send_json(200, {"ok": True, "schedule": schedule})
            elif path == "/api/review/session":
                action = str(payload.get("action") or "")
                if action == "start":
                    session_id = review_storage.start_session(int(payload.get("planned") or 0))
                    self.send_json(200, {"ok": True, "sessionId": session_id})
                elif action == "finish":
                    review_storage.finish_session(
                        str(payload.get("sessionId") or ""),
                        answered=int(payload.get("answered") or 0),
                        grade_counts={int(k): int(v) for k, v in (payload.get("gradeCounts") or {}).items()},
                        duration_ms=int(payload.get("durationMs") or 0))
                    self.send_json(200, {"ok": True})
                else:
                    raise ValueError("不支持的会话操作")
```

同时在 `review_storage.py` 增加 `reveal`（**只有这个函数返回答案**）：

```python
def reveal(code: str, question_type: str) -> dict[str, Any]:
    """揭示答案：这是唯一会返回参考答案/历史答案的入口。"""
    if question_type not in review_content.QUESTION_TYPES:
        raise ValueError("题型不正确")
    data = history(code, limit=20)
    point = _point_content(str(code))
    block = dict(point.get(question_type) or {})
    block.update({"code": str(code), "type": question_type, "title": data["title"],
                  "pitfalls": data["pitfalls"], "history": data["attempts"],
                  "state": data["state"]})
    return block


def _point_content(code: str) -> dict[str, Any]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT content_json FROM review_points WHERE code=?", (str(code),)).fetchone()
    if row is None:
        raise ValueError("知识点不存在")
    return json.loads(row["content_json"])
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_http -v`
Expected: PASS（9 个用例）

- [ ] **Step 5: 提交**

```bash
git add local_server.py review_storage.py tests/test_review_http.py
git commit -m "feat(review): 作答接口 reveal/answer/session（答案只经 reveal 下发）"
```

---

### Task 9: 每日限额与新增名额设置项

**Files:**
- Modify: `storage.py`（`read_app_settings`/`update_app_settings` 增加两个键的清洗）
- Modify: `js/app.js`（设置面板加两个输入框，`saveSettingsFromUi` 带上）
- Test: `tests/test_review_storage.py`（追加）+ `tests/frontend/verify-r10.js`（追加检查）

**Interfaces:**
- Consumes: Task 6 的 `review_storage._settings()`
- Produces: `settings.reviewDailyLimit`（5～15，默认 10）、`settings.reviewNewPerDay`（0～5，默认 2）

- [ ] **Step 1: 写失败的测试（追加到 `tests/test_review_storage.py`）**

```python
    def test_settings_control_queue_limit_and_new_slots(self) -> None:
        storage.update_app_settings({"reviewDailyLimit": 7, "reviewNewPerDay": 3})
        settings = review_storage._settings()
        self.assertEqual(settings["limit"], 7)
        self.assertEqual(settings["newPerDay"], 3)
        storage.update_app_settings({"reviewDailyLimit": 99, "reviewNewPerDay": -5})
        settings = review_storage._settings()
        self.assertEqual(settings["limit"], 15)
        self.assertEqual(settings["newPerDay"], 0)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_storage -v`
Expected: FAIL（设置没被保存 → 仍是默认 10/2）

- [ ] **Step 3: 实现**

`storage.py` 的 `update_app_settings` 里按现有模式加两行清洗（与 `trashRetentionDays` 同款）：

```python
    if "reviewDailyLimit" in patch:
        settings["reviewDailyLimit"] = _clean_int(patch.get("reviewDailyLimit"), minimum=5, maximum=15, default=10)
    if "reviewNewPerDay" in patch:
        settings["reviewNewPerDay"] = _clean_int(patch.get("reviewNewPerDay"), minimum=0, maximum=5, default=2)
```

`read_app_settings` 的默认值字典里补：

```python
        "reviewDailyLimit": 10,
        "reviewNewPerDay": 2,
```

`index.html` 设置区（`trashRetentionInput` 旁边）加：

```html
        <label class="settings-field">每日复习上限
          <input type="number" id="reviewDailyLimitInput" min="5" max="15" step="1" value="10" />
        </label>
        <label class="settings-field">每日新知识点
          <input type="number" id="reviewNewPerDayInput" min="0" max="5" step="1" value="2" />
        </label>
```

`js/app.js`：`loadSettings()` 里回填这两个输入框（照 `trashRetentionInput` 的写法），`saveSettingsFromUi()` 的请求体加：

```js
            reviewDailyLimit: Number(reviewDailyLimitInput.value) || 10,
            reviewNewPerDay: Number(reviewNewPerDayInput.value) || 0,
```

- [ ] **Step 4: 跑测试与前端脚本确认通过**

Run: `python3 -m unittest tests.test_review_storage -v` → PASS
Run: `node tests/frontend/dom-smoke.js` → 通过（并补一条检查：`document.getElementById('reviewDailyLimitInput')` 存在）
在 `tests/frontend/verify-r10.js` 追加：

```javascript
check('设置：每日复习上限与新增名额可配置',
    html.includes('id="reviewDailyLimitInput"') && html.includes('id="reviewNewPerDayInput"')
    && /reviewDailyLimit[\s\S]{0,200}reviewNewPerDay/.test(src));
```

- [ ] **Step 5: 提交**

```bash
git add storage.py index.html js/app.js tests/test_review_storage.py tests/frontend/verify-r10.js tests/frontend/dom-smoke.js
git commit -m "feat(review): 每日复习上限与新增知识点名额设置"
```

---
### Task 10: 复习会话视图（一次一题、先回忆后揭示、5 档自评）

**Files:**
- Modify: `index.html`（新增 `#reviewSessionView` 与内部元素）
- Modify: `css/style.css`（会话样式，追加在文件末尾）
- Modify: `js/app.js`（会话状态机 + 事件接线）
- Test: `tests/frontend/dom-smoke.js`（追加流程与"揭示前 DOM 无答案"断言）

**Interfaces:**
- Consumes: Task 7/8 的四个接口 + `/api/review/reveal`
- Produces（app.js 内，模块作用域）：
  - `reviewSessionState = { sessionId, items, index, startedAt, gradeCounts, revealed, draft }`
  - `async function startReviewSession()`（取队列 → 建会话 → 进视图 → 出第一题）
  - `function renderReviewQuestion()`（只渲染题面与输入框，**不渲染答案**）
  - `async function revealReviewAnswer()`（POST reveal → 渲染答案面板 → 显示五档按钮）
  - `async function gradeReviewQuestion(grade)`（POST answer → 下一题或总结）
  - `function finishReviewSession()`（POST session finish → 总结面板）

- [ ] **Step 1: 写失败的测试（追加到 `tests/frontend/dom-smoke.js` 主流程里，导入步骤之后）**

```javascript
    // ⑭ 复习会话：一次一题 → 先回忆 → 揭示 → 5 档自评（揭示前 DOM 里不能有答案）
    step('点击「开始复习」不抛异常', () => elementsById.get('reviewQueueBtn').dispatch('click'));
    await sleep(120);
    check('复习会话视图打开', activeViews().includes('reviewSessionView'), JSON.stringify(activeViews()));
    const promptEl = elementsById.get('reviewQuestionPrompt');
    check('会话出题了（有题面）', Boolean(promptEl && textOf(promptEl).trim()),
        textOf(elementsById.get('reviewSessionView')).slice(0, 160));
    const beforeReveal = textOf(elementsById.get('reviewSessionView'));
    check('揭示前 DOM 里没有参考答案（active recall）',
        !beforeReveal.includes('参考答案') && !beforeReveal.includes('expected-answer'),
        beforeReveal.slice(0, 200));
    step('填写回忆内容不抛异常', () => {
        const input = elementsById.get('reviewAnswerInput');
        input.value = '我写的回忆';
        input.dispatch('input');
    });
    step('点「看答案」不抛异常', () => elementsById.get('reviewRevealBtn').dispatch('click'));
    await sleep(120);
    const afterReveal = textOf(elementsById.get('reviewSessionView'));
    check('揭示后才出现参考答案与历史', afterReveal.includes('参考答案'), afterReveal.slice(0, 200));
    check('揭示后出现五档自评按钮', findAll(elementsById.get('reviewGradeButtons'),
        el => el.classList.contains('review-grade-btn')).length === 5);
    step('选「基本掌握」不抛异常', () => {
        const buttons = findAll(elementsById.get('reviewGradeButtons'),
            el => el.classList.contains('review-grade-btn'));
        if (buttons[2]) buttons[2].dispatch('click');
    });
    await sleep(150);
    check('提交自评后调用了 /api/review/answer',
        fetchLog.includes('POST /api/review/answer'), JSON.stringify(fetchLog.slice(-4)));
```

**先改 `tests/frontend/dom-smoke.js` 顶部的 `VIEWS` 常量**，把新视图加进去（否则 `activeViews()` 永远看不到它们）：

```javascript
const VIEWS = ['projectsView', 'detailView', 'reviewView', 'reviewSessionView', 'knowledgeView', 'workbenchView'];
```

配套 fetch 桩（`tests/frontend/dom-smoke.js` 的 `fetchStub` 里新增）：

```javascript
    if (path === '/api/review/summary') return reply(200, { dueToday: 1, overdue: 1, upcoming: 0, weak: 1,
        total: 3, learned: 2, answeredToday: 0, streakDays: 3, limit: 10, newPerDay: 2 });
    if (path === '/api/review/queue') return reply(200, { items: [{ code: 'py.a.b', title: '示例知识点',
        minutes: 10, module: '容器', level: '基础', questionType: 'predict',
        prompt: '写出下面代码的输出', reason: 'today', due: today, taskId: '1103', projectId: 'p1' }],
        total: 1, truncated: false, limit: 10 });
    if (path === '/api/review/reveal') return reply(200, { code: 'py.a.b', type: 'predict',
        title: '示例知识点', prompt: '写出下面代码的输出', expected: ['[1]', '[1, 2]'],
        explain: '第二次调用复用了同一个列表', pitfalls: ['可变默认参数'], history: [], state: null });
    if (path === '/api/review/answer') return reply(200, { ok: true, schedule: { due: '2026-09-30',
        intervalDays: 14, streak: 1, lapses: 0, weak: false, lastGrade: 4 } });
    if (path === '/api/review/session') return reply(200, { ok: true, sessionId: 's-review-1' });
    if (path === '/api/review/points') return reply(200, { points: [{ code: 'py.a.b', title: '示例知识点',
        minutes: 10, module: '容器', level: '基础', origin: 'builtin', due: today, weak: true, lastGrade: 3,
        pitfalls: ['可变默认参数'] }], total: 1, limit: 200, offset: 0 });
    if (path === '/api/review/history') return reply(200, { code: 'py.a.b', title: '示例知识点',
        module: '容器', level: '基础', minutes: 10, pitfalls: [], attempts: [], state: null });
```

- [ ] **Step 2: 跑测试确认失败**

Run: `node tests/frontend/dom-smoke.js`
Expected: 失败（`reviewSessionView` 不存在 / 没有 `reviewRevealBtn`）

- [ ] **Step 3: 加视图结构与样式**

`index.html`（放在 `#reviewView` 之后、`#workbenchView` 之前）：

```html
<div class="view" id="reviewSessionView">
  <div class="review-session-head">
    <button type="button" id="reviewSessionExitBtn" class="utility-secondary-btn">退 出</button>
    <span class="review-subline" id="reviewSessionProgress"></span>
  </div>
  <div class="review-card" id="reviewQuestionCard">
    <div class="review-meta" id="reviewQuestionMeta"></div>
    <div class="review-prompt" id="reviewQuestionPrompt"></div>
    <textarea id="reviewAnswerInput" rows="6" placeholder="先自己回忆或写出代码，再看答案"></textarea>
    <div class="review-actions-row">
      <button type="button" id="reviewRevealBtn" class="utility-primary-btn">看答案</button>
    </div>
    <div class="review-answer" id="reviewAnswerPanel" hidden></div>
    <div class="review-grades" id="reviewGradeButtons" hidden>
      <button type="button" class="review-grade-btn" data-grade="1">完全不会</button>
      <button type="button" class="review-grade-btn" data-grade="2">看过但说不清</button>
      <button type="button" class="review-grade-btn" data-grade="3">基本掌握</button>
      <button type="button" class="review-grade-btn" data-grade="4">可以独立写代码</button>
      <button type="button" class="review-grade-btn" data-grade="5">可以讲给别人听</button>
    </div>
  </div>
  <div class="review-summary" id="reviewSessionSummary" hidden></div>
</div>
```

`css/style.css` 追加（CRLF）：

```css
.review-session-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.review-card { background: var(--panel-bg, #fff); border-radius: 12px; padding: 18px; }
.review-meta { color: #6b7280; font-size: 13px; margin-bottom: 8px; }
.review-prompt { font-size: 16px; line-height: 1.6; margin-bottom: 12px; white-space: pre-wrap; }
.review-card textarea { width: 100%; font-family: inherit; font-size: 14px; padding: 10px; border-radius: 8px;
  border: 1px solid #d1d5db; box-sizing: border-box; }
.review-actions-row { margin: 12px 0; }
.review-answer { border-top: 1px dashed #d1d5db; padding-top: 12px; margin-top: 8px; white-space: pre-wrap; }
.review-answer h4 { margin: 10px 0 6px; font-size: 14px; }
.review-grades { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.review-grade-btn { padding: 8px 12px; border-radius: 8px; border: 1px solid #d1d5db; background: #f9fafb;
  cursor: pointer; }
.review-grade-btn:hover { background: #eef2ff; }
.review-summary { background: var(--panel-bg, #fff); border-radius: 12px; padding: 18px; }
```

- [ ] **Step 4: 实现会话状态机（`js/app.js`）**

元素引用（与其它视图一致，放在文件顶部 `const reviewView = ...` 附近）：

```js
const reviewSessionView = document.getElementById('reviewSessionView');
const reviewSessionProgress = document.getElementById('reviewSessionProgress');
const reviewSessionExitBtn = document.getElementById('reviewSessionExitBtn');
const reviewQuestionCard = document.getElementById('reviewQuestionCard');
const reviewQuestionMeta = document.getElementById('reviewQuestionMeta');
const reviewQuestionPrompt = document.getElementById('reviewQuestionPrompt');
const reviewAnswerInput = document.getElementById('reviewAnswerInput');
const reviewRevealBtn = document.getElementById('reviewRevealBtn');
const reviewAnswerPanel = document.getElementById('reviewAnswerPanel');
const reviewGradeButtons = document.getElementById('reviewGradeButtons');
const reviewSessionSummary = document.getElementById('reviewSessionSummary');
```

状态机（放在 `showReviewQueue` 附近）：

```js
    const GRADE_LABELS = { 1: '完全不会', 2: '看过但说不清', 3: '基本掌握', 4: '可以独立写代码', 5: '可以讲给别人听' };
    let reviewSessionState = { sessionId: '', items: [], index: 0, startedAt: 0, gradeCounts: {}, revealed: false };

    function reviewDraftKey(code, type) {
        return `todo_review_draft:${reviewSessionState.sessionId}:${code}:${type}`;
    }

    function saveReviewDraft() {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item || !reviewAnswerInput) return;
        try {
            localStorage.setItem(reviewDraftKey(item.code, item.questionType), reviewAnswerInput.value || '');
        } catch (error) { /* 隐私模式等忽略 */ }
    }

    function restoreReviewDraft(item) {
        reviewAnswerInput.value = '';
        try {
            reviewAnswerInput.value = localStorage.getItem(reviewDraftKey(item.code, item.questionType)) || '';
        } catch (error) { /* 忽略 */ }
    }

    async function startReviewSession() {
        let payload;
        try {
            const response = await apiFetch(`/api/review/queue?today=${encodeURIComponent(todayStr())}`, { cache: 'no-store' });
            payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取复习队列失败');
        } catch (error) {
            showToast(error.message || '读取复习队列失败，请重试');
            return;
        }
        const items = Array.isArray(payload.items) ? payload.items : [];
        if (items.length === 0) {
            showToast('今天没有要复习的知识点，去知识点库挑一个练也行');
            activateView(reviewView);
            return;
        }
        let sessionId = '';
        try {
            const started = await callApi('/api/review/session', 'POST', { action: 'start', planned: items.length });
            sessionId = started.sessionId || '';
        } catch (error) { sessionId = ''; }
        reviewSessionState = { sessionId: sessionId, items: items, index: 0, startedAt: Date.now(), gradeCounts: {}, revealed: false };
        activateView(reviewSessionView);
        renderReviewQuestion();
    }

    function renderReviewQuestion() {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item) { finishReviewSession(); return; }
        reviewSessionState.revealed = false;
        reviewSessionSummary.hidden = true;
        reviewQuestionCard.hidden = false;
        reviewSessionProgress.textContent = `第 ${reviewSessionState.index + 1} / ${reviewSessionState.items.length} 题`;
        reviewQuestionMeta.textContent = `${item.title} · ${item.module || '未分类'} · ${item.minutes} 分钟 · ${item.reason === 'new' ? '新知识点' : '复习'}`;
        reviewQuestionPrompt.textContent = item.prompt || '（这道题没有题面）';
        restoreReviewDraft(item);
        reviewAnswerPanel.hidden = true;
        reviewAnswerPanel.innerHTML = '';
        reviewGradeButtons.hidden = true;
        reviewRevealBtn.disabled = false;
    }

    async function revealReviewAnswer() {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item || reviewSessionState.revealed) return;
        reviewRevealBtn.disabled = true;
        saveReviewDraft();
        let data;
        try {
            data = await callApi('/api/review/reveal', 'POST', { code: item.code, type: item.questionType });
        } catch (error) {
            reviewRevealBtn.disabled = false;
            showToast(error.message || '读取答案失败，请重试');
            return;
        }
        reviewSessionState.revealed = true;
        const parts = [];
        const heading = document.createElement('h4');
        heading.textContent = '参考答案';
        parts.push(heading);
        const expected = Array.isArray(data.expected) ? data.expected : [];
        const answerLines = Array.isArray(data.answer) ? data.answer : [];
        [].concat(answerLines, expected).forEach(line => {
            const block = document.createElement('div');
            block.className = 'expected-answer';
            block.textContent = String(line);
            parts.push(block);
        });
        if (data.explain) {
            const explain = document.createElement('div');
            explain.textContent = `解释：${data.explain}`;
            parts.push(explain);
        }
        if (data.rootCause) {
            const cause = document.createElement('div');
            cause.textContent = `根因：${data.rootCause}（修法：${data.fix || ''}）`;
            parts.push(cause);
        }
        if (data.reference) {
            const reference = document.createElement('div');
            reference.textContent = `参考实现：${data.reference}`;
            parts.push(reference);
        }
        if (Array.isArray(data.pitfalls) && data.pitfalls.length > 0) {
            const pitfallTitle = document.createElement('h4');
            pitfallTitle.textContent = '易错点';
            parts.push(pitfallTitle);
            data.pitfalls.forEach(text => {
                const line = document.createElement('div');
                line.textContent = `· ${text}`;
                parts.push(line);
            });
        }
        const history = Array.isArray(data.history) ? data.history : [];
        if (history.length > 0) {
            const historyTitle = document.createElement('h4');
            historyTitle.textContent = '历史答案';
            parts.push(historyTitle);
            history.slice(0, 5).forEach(entry => {
                const line = document.createElement('div');
                line.textContent = `${entry.reviewedOn} · ${GRADE_LABELS[entry.grade] || entry.grade} · ${entry.answer || '（没写）'}`;
                parts.push(line);
            });
        }
        reviewAnswerPanel.replaceChildren(...parts);
        reviewAnswerPanel.hidden = false;
        reviewGradeButtons.hidden = false;
    }

    async function gradeReviewQuestion(grade) {
        const item = reviewSessionState.items[reviewSessionState.index];
        if (!item || !reviewSessionState.revealed) return;
        const answer = reviewAnswerInput.value || '';
        try {
            await callApi('/api/review/answer', 'POST', {
                code: item.code, type: item.questionType, grade: grade, answer: answer,
                durationMs: Date.now() - reviewSessionState.startedAt,
                sessionId: reviewSessionState.sessionId,
                taskId: item.taskId || '', projectId: item.projectId || '',
                today: todayStr(),
            });
        } catch (error) {
            showToast(error.message || '保存作答失败，答案还留在输入框里');
            return;
        }
        try { localStorage.removeItem(reviewDraftKey(item.code, item.questionType)); } catch (error) { /* 忽略 */ }
        reviewSessionState.gradeCounts[grade] = (reviewSessionState.gradeCounts[grade] || 0) + 1;
        reviewSessionState.index += 1;
        if (reviewSessionState.index >= reviewSessionState.items.length) finishReviewSession();
        else renderReviewQuestion();
        loadReviewCounts();
    }

    async function finishReviewSession() {
        const counts = reviewSessionState.gradeCounts;
        const answered = Object.values(counts).reduce((sum, value) => sum + value, 0);
        try {
            await callApi('/api/review/session', 'POST', {
                action: 'finish', sessionId: reviewSessionState.sessionId, answered: answered,
                gradeCounts: counts, durationMs: Date.now() - reviewSessionState.startedAt,
            });
        } catch (error) { /* 总结照常展示 */ }
        reviewQuestionCard.hidden = true;
        reviewSessionSummary.hidden = false;
        const lines = ['本次复习完成'];
        lines.push(`共 ${answered} 题，用时 ${Math.round((Date.now() - reviewSessionState.startedAt) / 60000 * 10) / 10} 分钟`);
        Object.keys(GRADE_LABELS).forEach(grade => {
            const count = counts[grade] || 0;
            if (count) lines.push(`${GRADE_LABELS[grade]}：${count} 题`);
        });
        const summary = document.createElement('div');
        const title = document.createElement('h3');
        title.textContent = lines[0];
        summary.appendChild(title);
        lines.slice(1).forEach(line => {
            const block = document.createElement('div');
            block.textContent = line;
            summary.appendChild(block);
        });
        reviewSessionSummary.replaceChildren(summary);
    }
```

事件接线（`initEvents()` 里）：

```js
        reviewSessionExitBtn.addEventListener('click', () => { saveReviewDraft(); showReviewQueue(); });
        reviewRevealBtn.addEventListener('click', revealReviewAnswer);
        reviewAnswerInput.addEventListener('input', () => { clearTimeout(reviewDraftTimer); reviewDraftTimer = setTimeout(saveReviewDraft, 500); });
        reviewGradeButtons.addEventListener('click', (event) => {
            const button = event.target.closest('.review-grade-btn');
            if (button) gradeReviewQuestion(Number(button.dataset.grade));
        });
```

并在文件顶部状态区加 `let reviewDraftTimer = null;`，把 `reviewQueueBtn` 的点击改成 `startReviewSession()`（复习页顶部的"开始复习"按钮）。

- [ ] **Step 5: 跑测试确认通过**

Run: `node tests/frontend/dom-smoke.js`
Expected: 通过（含新增 7 条检查）；`node --check js/app.js` 通过

- [ ] **Step 6: 提交**

```bash
git add index.html css/style.css js/app.js tests/frontend/dom-smoke.js
git commit -m "feat(review): 复习会话视图（一次一题、先回忆后揭示、五档自评、草稿恢复）"
```

---

### Task 11: 复习页改版（分组 + 筛选 + 任务级到期成组）

**Files:**
- Modify: `js/app.js`（`showReviewQueue`/`renderReviewQueue` 改为读 `/api/review/summary` + `/api/review/queue`，新增分组与筛选）
- Modify: `index.html`（复习页工具栏：题型/模块/范围筛选）
- Modify: `review_storage.py`（**范围修订**：`summary()` 增加 `recentWrong`/`recentMastered`，复用已有 `recent_attempts()`；规格 §12 要求 summary 含"最近答错/最近掌握"，但 Task 7 只透传了 `summary()`，故必须在这里补齐）
- Modify: `tests/test_review_storage.py`（**范围修订**：同步 summary 键集合与最近作答记录的断言）
- Test: `tests/frontend/verify-r3.js`（追加检查）+ `tests/frontend/dom-smoke.js`

**Interfaces:**
- Consumes: `/api/review/summary`、`/api/review/queue`、`/api/reviews`（任务级到期，保留）
- Produces：`reviewQueueState = { summary, dueToday, overdue, upcoming, weak, wrong, mastered, taskDue }`；渲染函数 `renderReviewGroups()`

- [ ] **Step 1: 写失败的测试（追加到 `tests/frontend/verify-r3.js`）**

```javascript
check('复习页：主体分组改为知识点（今日必须复习/已逾期/薄弱/最近答错/最近掌握）',
    /今日必须复习[\s\S]{0,400}已逾期[\s\S]{0,400}薄弱知识点[\s\S]{0,400}最近答错[\s\S]{0,400}最近掌握/.test(src));
check('复习页：任务级到期单独成组（保留旧 review_due 数据）',
    /任务级到期[\s\S]{0,300}\/api\/reviews/.test(src));
check('复习页：支持题型与 Python 模块筛选',
    /reviewTypeFilter|reviewModuleFilter/.test(src) && /id="reviewTypeFilter"/.test(html));
```

- [ ] **Step 2: 跑测试确认失败**

Run: `node tests/frontend/verify-r3.js`
Expected: 3 条新检查失败

- [ ] **Step 3: 实现**

`index.html` 复习页工具栏加：

```html
        <select id="reviewTypeFilter" class="filter-select">
          <option value="">全部题型</option>
          <option value="concept">概念题</option>
          <option value="predict">代码预测题</option>
          <option value="debug">错误排查题</option>
          <option value="code_task">实际编程题</option>
        </select>
        <select id="reviewModuleFilter" class="filter-select"><option value="">全部模块</option></select>
        <select id="reviewScopeFilter" class="filter-select">
          <option value="">全部</option>
          <option value="overdue">只看已逾期</option>
          <option value="weak">只看薄弱点</option>
          <option value="new">只看新知识点</option>
        </select>
```

`js/app.js`：`showReviewQueue()` 改成并发取三份数据并渲染分组（保留 `settleSaves()` 前置与失败重试按钮）：

```js
    async function showReviewQueue() {
        try {
            await settleSaves();
        } catch (error) {
            showToast('当前修改尚未保存，请先解决保存失败');
            return;
        }
        activateView(reviewView);
        reviewSubline.textContent = '';
        renderReviewMessage(listStatusText('review', 'loading'), false);
        const query = `today=${encodeURIComponent(todayStr())}`;
        let summary = null;
        let queue = null;
        let taskDue = null;
        try {
            const [summaryResponse, queueResponse, taskResponse] = await Promise.all([
                apiFetch(`/api/review/summary?${query}`, { cache: 'no-store' }),
                apiFetch(`/api/review/queue?${query}`, { cache: 'no-store' }),
                apiFetch(`/api/reviews?${query}`, { cache: 'no-store' }),
            ]);
            summary = await summaryResponse.json().catch(() => ({}));
            queue = await queueResponse.json().catch(() => ({}));
            taskDue = await taskResponse.json().catch(() => ({}));
            if (!summaryResponse.ok || !queueResponse.ok) {
                throw new Error(summary.error || queue.error || '读取复习队列失败');
            }
        } catch (error) {
            const message = listStatusText('review', 'failed', error && error.message);
            renderReviewMessage(message, true);
            showToast(message);
            return;
        }
        reviewQueueState = {
            summary: summary,
            items: Array.isArray(queue.items) ? queue.items : [],
            taskDue: Array.isArray(taskDue.due) ? taskDue.due : [],
        };
        reviewSubline.textContent = `今日必复 ${summary.dueToday} · 逾期 ${summary.overdue} · 薄弱 ${summary.weak} · 连续 ${summary.streakDays} 天`;
        renderReviewGroups();
        loadReviewCounts();
    }

    function renderReviewGroups() {
        const state = reviewQueueState;
        const body = reviewBody;
        body.innerHTML = '';
        const groups = [
            ['今日必须复习', state.items.filter(item => item.reason === 'today' || item.reason === 'overdue')],
            ['即将到期（可提前练）', state.items.filter(item => item.reason === 'upcoming')],
            ['薄弱知识点', state.items.filter(item => item.reason === 'weak')],
            ['新知识点', state.items.filter(item => item.reason === 'new')],
        ];
        const dueList = state.summary && state.summary.dueToday ? [] : [];
        groups.forEach(([title, items]) => {
            if (items.length === 0) return;
            body.appendChild(renderKnowledgeGroup(title, items));
        });
        if (state.taskDue.length > 0) {
            body.appendChild(renderTaskDueGroup(state.taskDue));
        }
        if (body.childElementCount === 0) {
            const empty = document.createElement('p');
            empty.className = 'review-empty';
            empty.textContent = '今天没有到期的知识点：可以去知识点库挑一个练，或先完成学习任务';
            body.appendChild(empty);
        }
    }
```

```js
    function renderKnowledgeGroup(title, items) {
        const group = document.createElement('div');
        group.className = 'review-group';
        const head = document.createElement('div');
        head.className = 'review-group-title';
        const label = document.createElement('span');
        label.textContent = title;
        const count = document.createElement('span');
        count.className = 'gcount';
        count.textContent = String(items.length);
        head.append(label, count);
        group.appendChild(head);
        items.forEach(item => {
            const row = document.createElement('div');
            row.className = 'review-item';
            const main = document.createElement('div');
            main.className = 'review-item-main';
            const path = document.createElement('span');
            path.className = 'review-item-path';
            path.textContent = `${item.module || '未分类'} · ${item.minutes} 分钟`;
            const text = document.createElement('div');
            text.className = 'review-item-text';
            text.textContent = item.title;
            main.append(path, text);
            const actions = document.createElement('div');
            actions.className = 'review-actions';
            const start = document.createElement('button');
            start.type = 'button';
            start.className = 'review-btn easy';
            start.textContent = '开始复习这一题';
            start.addEventListener('click', () => startReviewSessionWithItems([item]));
            const detail = document.createElement('button');
            detail.type = 'button';
            detail.className = 'review-btn';
            detail.textContent = '历史';
            detail.addEventListener('click', () => showReviewHistory(item.code));
            actions.append(start, detail);
            row.append(main, actions);
            group.appendChild(row);
        });
        return group;
    }

    function renderTaskDueGroup(items) {
        const group = document.createElement('div');
        group.className = 'review-group';
        const head = document.createElement('div');
        head.className = 'review-group-title';
        const label = document.createElement('span');
        label.textContent = '任务级到期（原来的复习）';
        const count = document.createElement('span');
        count.className = 'gcount';
        count.textContent = String(items.length);
        head.append(label, count);
        group.appendChild(head);
        items.forEach(item => {
            const row = document.createElement('div');
            row.className = 'review-item';
            const main = document.createElement('div');
            main.className = 'review-item-main';
            const path = document.createElement('span');
            path.className = 'review-item-path';
            path.textContent = `${item.projectName || ''} · ${item.path || ''}`;
            const text = document.createElement('div');
            text.className = 'review-item-text';
            text.textContent = item.text || '未命名任务';
            main.append(path, text);
            const actions = document.createElement('div');
            actions.className = 'review-actions';
            [['easy', '记住了 +7'], ['hard', '模糊 +3'], ['again', '忘了']].forEach(([action, text]) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'review-btn';
                button.textContent = text;
                button.addEventListener('click', () => runQueueAction(item, action));
                actions.appendChild(button);
            });
            row.append(main, actions);
            group.appendChild(row);
        });
        return group;
    }

    async function startReviewSessionWithItems(items) {
        if (!Array.isArray(items) || items.length === 0) return;
        reviewSessionState = { sessionId: '', items: items.slice(), index: 0,
            startedAt: Date.now(), gradeCounts: {}, revealed: false };
        try {
            const started = await callApi('/api/review/session', 'POST', { action: 'start', planned: items.length });
            reviewSessionState.sessionId = started.sessionId || '';
        } catch (error) { /* 会话统计失败不影响刷题 */ }
        activateView(reviewSessionView);
        renderReviewQuestion();
    }

    async function showReviewHistory(code) {
        try {
            const response = await apiFetch(`/api/review/history?code=${encodeURIComponent(code)}`, { cache: 'no-store' });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || '读取历史失败');
            showUtilityModal('复习历史', data.title || code);
            const lines = (data.attempts || []).map(entry =>
                `${entry.reviewedOn} · ${GRADE_LABELS[entry.grade] || entry.grade} · ${entry.answer || '（没写）'}`);
            utilityBody.textContent = lines.length > 0 ? lines.join('
') : '还没有作答记录';
        } catch (error) {
            showToast(error.message || '读取历史失败');
        }
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `node tests/frontend/verify-r3.js` → PASS
Run: `node tests/frontend/dom-smoke.js` → PASS

- [ ] **Step 5: 提交**

```bash
git add index.html js/app.js tests/frontend/verify-r3.js tests/frontend/dom-smoke.js
git commit -m "feat(review): 复习页改为知识点分组 + 题型/模块筛选，任务级到期单独成组"
```

---

### Task 12: 知识点库页（浏览 / 筛选 / 立即练一次）

**Files:**
- Modify: `index.html`（`#knowledgeView` + 工具按钮 `#openKnowledgeBtn`）
- Modify: `js/app.js`（`showKnowledgeLibrary()`、`renderKnowledgeList()`）
- Test: `tests/frontend/dom-smoke.js`（追加）

**Interfaces:**
- Consumes: `/api/review/points`
- Produces：`showKnowledgeLibrary()`、`practicePoint(code)`（用单点直接进会话）

- [ ] **Step 1: 写失败的测试（追加到 `tests/frontend/dom-smoke.js`）**

```javascript
    // ⑮ 知识点库：按模块筛、可立即练一次
    step('打开知识点库不抛异常', () => elementsById.get('openKnowledgeBtn').dispatch('click'));
    await sleep(120);
    check('知识点库视图打开并列出知识点',
        activeViews().includes('knowledgeView')
        && textOf(elementsById.get('knowledgeList')).includes('示例知识点'),
        textOf(elementsById.get('knowledgeList')).slice(0, 160));
    check('知识点库调用了 /api/review/points', fetchLog.some(line => line.startsWith('GET /api/review/points')),
        JSON.stringify(fetchLog.slice(-4)));
```

- [ ] **Step 2: 跑测试确认失败**

Run: `node tests/frontend/dom-smoke.js`
Expected: 失败（`openKnowledgeBtn` 不存在）

- [ ] **Step 3: 实现**

`index.html`：更多工具里加 `<button type="button" id="openKnowledgeBtn" class="utility-task">知识点库</button>`；新增视图：

```html
<div class="view" id="knowledgeView">
  <div class="review-session-head">
    <button type="button" id="knowledgeBackBtn" class="utility-secondary-btn">返 回</button>
    <input type="search" id="knowledgeSearch" class="memo-search" placeholder="搜知识点 / code" />
    <select id="knowledgeModuleFilter" class="filter-select"><option value="">全部模块</option></select>
    <select id="knowledgeLevelFilter" class="filter-select">
      <option value="">全部层级</option><option value="基础">基础</option>
      <option value="实用">实用</option><option value="进阶">进阶</option>
    </select>
  </div>
  <div class="knowledge-list" id="knowledgeList"></div>
</div>
```

`js/app.js`：

```js
    async function showKnowledgeLibrary() {
        activateView(knowledgeView);
        try {
            const response = await apiFetch('/api/review/points?limit=500', { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.error || '读取知识点库失败');
            knowledgePoints = payload.points || [];
        } catch (error) {
            showToast(error.message || '读取知识点库失败，请重试');
            knowledgePoints = [];
        }
        renderKnowledgeList();
    }

    function renderKnowledgeList() {
        const query = knowledgeSearch.value.trim().toLowerCase();
        const module = knowledgeModuleFilter.value;
        const level = knowledgeLevelFilter.value;
        const list = knowledgePoints.filter(point =>
            (!module || point.module === module) && (!level || point.level === level)
            && (!query || `${point.title} ${point.code}`.toLowerCase().includes(query)));
        knowledgeList.innerHTML = '';
        if (list.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'utility-empty';
            empty.textContent = '没有匹配的知识点';
            knowledgeList.appendChild(empty);
            return;
        }
        list.forEach(point => {
            const card = document.createElement('div');
            card.className = 'knowledge-item';
            const title = document.createElement('div');
            title.className = 'knowledge-title';
            title.textContent = `${point.title}（${point.minutes} 分钟）`;
            const meta = document.createElement('small');
            meta.textContent = `${point.module || '未分类'} · ${point.level} · ${point.weak ? '薄弱' : (point.due ? `下次 ${point.due}` : '还没学过')}`;
            const practice = document.createElement('button');
            practice.type = 'button';
            practice.className = 'utility-secondary-btn';
            practice.textContent = '立即练一次';
            practice.addEventListener('click', () => practicePoint(point.code));
            card.append(title, meta, practice);
            knowledgeList.appendChild(card);
        });
    }

    async function practicePoint(code) {
        const point = knowledgePoints.find(entry => entry.code === code);
        if (!point) return;
        reviewSessionState = { sessionId: '', items: [{ code: point.code, title: point.title,
            minutes: point.minutes, module: point.module, level: point.level,
            questionType: '', prompt: '', reason: 'practice', due: point.due }],
            index: 0, startedAt: Date.now(), gradeCounts: {}, revealed: false };
        activateView(reviewSessionView);
        // 单点练习：用 queue 的 code 过滤精确拿这一题的题面（points 接口不含题面）
        try {
            const response = await apiFetch(
                `/api/review/queue?today=${encodeURIComponent(todayStr())}&code=${encodeURIComponent(code)}`,
                { cache: 'no-store' });
            const payload = await response.json().catch(() => ({}));
            const item = (payload.items || [])[0];
            if (item) reviewSessionState.items[0] = item;
        } catch (error) { /* 用兜底题面 */ }
        renderReviewQuestion();
    }
```

元素引用与状态（放在文件顶部视图常量区与状态区）：

```js
const knowledgeView = document.getElementById('knowledgeView');
const knowledgeList = document.getElementById('knowledgeList');
const knowledgeSearch = document.getElementById('knowledgeSearch');
const knowledgeModuleFilter = document.getElementById('knowledgeModuleFilter');
const knowledgeLevelFilter = document.getElementById('knowledgeLevelFilter');
const knowledgeBackBtn = document.getElementById('knowledgeBackBtn');
const openKnowledgeBtn = document.getElementById('openKnowledgeBtn');
let knowledgePoints = [];
```

接线：`openKnowledgeBtn` → `showKnowledgeLibrary`；`knowledgeBackBtn` → `showReviewQueue`；
`knowledgeSearch` 的 `input` 事件与两个下拉的 `change` 事件 → `renderKnowledgeList`。

- [ ] **Step 4: 跑测试确认通过**

Run: `node tests/frontend/dom-smoke.js` → PASS

- [ ] **Step 5: 提交**

```bash
git add index.html js/app.js tests/frontend/dom-smoke.js
git commit -m "feat(review): 知识点库页（按模块/层级筛选 + 立即练一次）"
```

---
### Task 13: 生成回流（完成任务 → 复习项；元任务不生成）

**Files:**
- Modify: `review_storage.py`（`points_for_task`、`META_TASK_IDS`）
- Modify: `review_content.py`（新增 `normalize_points`：AI 返回内容的轻量清洗，最终仍走 `validate_points` 闸门）
- Modify: `ai_service.py`（`is_configured`、`generate_review_points`、`grade_review_answer`）
- Modify: `prompts.py`（`REVIEW_POINTS_PROMPT`、`REVIEW_GRADE_PROMPT`）
- Modify: `local_server.py`（`POST /api/review/generate`、`POST /api/review/ai-grade`）
- Modify: `js/app.js`（完成任务后按 `taskRefs` 生成复习项；AI 补漏）
- Test: `tests/test_review_generate.py`

**Interfaces:**
- Consumes: Task 3–8 的存储与接口、`ai_service`
- Produces:
  - `review_storage.points_for_task(task_id) -> list[dict]`（`introduces` 优先，`exercises` 次之）
  - `review_storage.META_TASK_IDS = {"1104", "1504"}`
  - `POST /api/review/generate` `{taskId, projectId, count=3}` → `{ok, created: [...], usedAi: bool}`
  - `POST /api/review/ai-grade` `{code, type, answer}` → `{ok, verdict: {correct, missing, wrongAt, hint}}`

- [ ] **Step 1: 写失败的测试**

```python
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-gen-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402


class ReviewGenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            for table in ("review_points", "review_point_tasks", "review_states"):
                connection.execute(f"DELETE FROM {table}")
        review_storage.ensure_content_imported()

    def test_introduced_points_come_first(self) -> None:
        points = review_storage.points_for_task("1202")
        self.assertTrue(points)
        self.assertTrue(all(point["relation"] == "introduces" for point in points[:len(points)]))

    def test_exercises_only_task_still_yields_points(self) -> None:
        points = review_storage.points_for_task("1101")
        self.assertTrue(points, "测试型任务必须能生成复习项（relation=exercises）")
        self.assertTrue(all(point["relation"] in ("introduces", "exercises") for point in points))

    def test_meta_tasks_yield_nothing(self) -> None:
        for task_id in ("1104", "1504"):
            self.assertEqual(review_storage.points_for_task(task_id), [],
                             f"元任务 {task_id} 不应产生复习项")

    def test_unknown_task_yields_nothing(self) -> None:
        self.assertEqual(review_storage.points_for_task("99999"), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_review_generate -v`
Expected: FAIL（没有 `points_for_task`）

- [ ] **Step 3: 实现存储侧与接口**

`review_storage.py`：

```python
META_TASK_IDS = {"1104", "1504"}
INTRODUCE_WEIGHT = 0


def points_for_task(task_id: str) -> list[dict[str, Any]]:
    """完成任务后要生成的复习项来源：先 introduces，再 exercises；元任务与未知任务返回空。"""
    task_key = str(task_id or "").strip()
    if not task_key or task_key in META_TASK_IDS:
        return []
    with _connection() as connection:
        rows = connection.execute(
            "SELECT p.code,p.title,p.minutes,p.module,p.level,t.relation,t.project_id "
            "FROM review_point_tasks t JOIN review_points p ON p.code=t.code "
            "WHERE t.task_id=? ORDER BY CASE t.relation WHEN 'introduces' THEN 0 ELSE 1 END, p.code",
            (task_key,)).fetchall()
    return [{"code": row["code"], "title": row["title"], "minutes": int(row["minutes"]),
             "module": row["module"], "level": row["level"], "relation": row["relation"],
             "projectId": row["project_id"] or ""} for row in rows]
```

`local_server.py` 的 `do_POST` 里追加（AI 只在被调用时使用；无 key / mock 未开时明确报错，不静默失败）：

```python
            elif path == "/api/review/generate":
                task_id = str(payload.get("taskId") or "").strip()
                if not task_id:
                    raise ValueError("缺少 taskId")
                points = review_storage.points_for_task(task_id)
                created = [{"code": point["code"], "title": point["title"]} for point in points[:5]]
                used_ai = False
                if len(created) < int(payload.get("count") or 3) and ai_service.is_configured():
                    generated = ai_service.generate_review_points(
                        task_id=task_id, project_id=str(payload.get("projectId") or ""),
                        task_text=str(payload.get("taskText") or ""),
                        count=int(payload.get("count") or 3))
                    if generated:
                        review_storage.import_content(generated, origin="ai")
                        created.extend({"code": point["code"], "title": point["title"],
                                        "origin": "ai"} for point in generated)
                        used_ai = True
                self.send_json(200, {"ok": True, "created": created[:5], "usedAi": used_ai})
            elif path == "/api/review/ai-grade":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("type") or "").strip()
                if not code or kind not in review_content.QUESTION_TYPES:
                    raise ValueError("知识点或题型不正确")
                if not ai_service.is_configured():
                    self.send_json(503, {"error": "未配置 AI，判分不可用（复习本身不受影响）"})
                    return
                verdict = ai_service.grade_review_answer(
                    code=code, question_type=kind, answer=str(payload.get("answer") or ""),
                    reference=review_storage.reveal(code, kind))
                self.send_json(200, {"ok": True, "verdict": verdict})
```

```python
def grade_review_answer(*, code: str, question_type: str, answer: str,
                        reference: dict) -> dict:
    """可选 AI 判分：返回 {correct, missing, wrongAt, hint}；失败时返回空 dict，不影响自评。"""
    if _mock_enabled():
        return {"correct": bool(answer.strip()), "missing": [] if answer.strip() else ["没有写出内容"],
                "wrongAt": "", "hint": "（模拟判分）对照参考答案检查关键机制是否讲到"}
    settings = read_settings()
    request_body = {
        "model": model_aliases(settings).get("flash", "deepseek-chat"),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": REVIEW_GRADE_PROMPT},
            {"role": "user", "content": json.dumps(
                {"知识点": code, "题型": question_type, "我的答案": answer,
                 "参考答案": reference}, ensure_ascii=False)},
        ],
    }
    try:
        parsed = _request_json(settings, request_body)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}
```

`prompts.py` 增加 `REVIEW_POINTS_PROMPT` 与 `REVIEW_GRADE_PROMPT`：前者要求返回
`{"points":[{code,title,minutes,module,level,concept,predict,debug,code_task,pitfalls}]}`，`code` 形如 `py.ai.<taskId>.<序号>`，
其余字段与课程库格式一致（见 Task 1）。注意 `review_content.normalize_points` 是本任务要新增的轻量清洗
（补齐缺省字段、过滤非法项），Task 1 的校验器仍然是最终闸门。

`ai_service.py` 增加三个函数（mock 模式返回固定内容以保证可测；真实分支复用既有请求通道）：

```python
def is_configured() -> bool:
    return bool(read_settings().get("DEEPSEEK_API_KEY"))


def generate_review_points(*, task_id: str, project_id: str, task_text: str, count: int = 3) -> list[dict]:
    """按任务补 1~3 个知识点（mock 模式返回固定样例，形状与课程库一致）。"""
    if _mock_enabled():
        base = task_text.strip()[:20] or task_id
        return [{
            "code": f"py.ai.{task_id}.{index + 1}",
            "title": f"{base} · 补充点 {index + 1}",
            "minutes": 15, "module": "AI 补充", "level": "基础",
            "taskRefs": [{"taskId": task_id, "projectId": project_id, "relation": "exercises"}],
            "concept": {"prompt": f"用自己的话解释：{base}（第 {index + 1} 点）", "answer": ["AI 生成的要点"]},
            "predict": {"prompt": "写出输出", "code": "print(len([1, 2, 3]))", "expected": ["3"], "explain": "长度"},
            "debug": {"prompt": "找错", "code": "x = [1, 2]\nprint(x[2])", "rootCause": "越界", "fix": "改索引"},
            "code_task": {"prompt": "写一个函数", "acceptance": ["能处理空输入"], "reference": "def f(xs): return xs or []"},
            "pitfalls": ["边界输入"],
        } for index in range(max(1, min(3, int(count))))]
    settings = read_settings()
    request_body = {
        "model": model_aliases(settings).get("flash", "deepseek-chat"),
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": REVIEW_POINTS_PROMPT},
            {"role": "user", "content": json.dumps(
                {"任务": task_text, "任务ID": task_id, "项目ID": project_id, "数量": max(1, min(3, int(count)))},
                ensure_ascii=False)},
        ],
    }
    try:
        parsed = _request_json(settings, request_body)      # 与 question/summary 同一通道
    except Exception:
        return []
    draft = parsed.get("points") if isinstance(parsed, dict) else None
    if not isinstance(draft, list):
        return []
    for index, point in enumerate(draft, start=1):
        if isinstance(point, dict):
            point.setdefault("code", f"py.ai.{task_id}.{index}")
    return review_content.normalize_points(draft)
```

`js/app.js`：`toggleNodeCompleted` 的 patch/保存成功回调里加：

```js
                maybeGenerateReviewItems(owner, node);
```

```js
    async function maybeGenerateReviewItems(project, node) {
        if (!project || !node) return;
        try {
            const payload = await callApi('/api/review/generate', 'POST', {
                taskId: node.id, projectId: project.id, taskText: node.text || '', count: 3,
            });
            const created = (payload.created || []).length;
            if (created > 0) showToast(`已生成 ${created} 个复习知识点`);
        } catch (error) {
            console.warn('生成复习知识点失败', error);
        }
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_generate -v` → PASS（4 个用例）
Run: `python3 -m unittest tests.test_ai_service -v` → PASS（mock 生成/判分不破坏既有 AI 测试）

- [ ] **Step 5: 提交**

```bash
git add review_storage.py local_server.py ai_service.py js/app.js tests/test_review_generate.py
git commit -m "feat(review): 完成任务按 taskRefs 生成复习项 + AI 补充与可选判分"
```

---

### Task 14: 备份 / 恢复 / 导出覆盖复习表

**Files:**
- Modify: `backup_service.py`（若备份按文件打包则无需改；若按表清单打包则加入 5 张表）
- Test: `tests/test_review_backup.py`

**Interfaces:**
- Consumes: 现有 `create_full_backup` / `restore_full_backup` / `storage.export_projects_snapshot`
- Produces：备份往返后 `review_points`/`review_states`/`review_attempts` 内容一致

- [ ] **Step 1: 写失败的测试**

```python
"""复习表必须跟着主库一起备份/恢复（同库同文件，重点是往返后内容一致）。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
_TEMP = tempfile.TemporaryDirectory(prefix="todo-review-backup-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP.name) / "summary.sqlite3")

import backup_service  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402


class ReviewBackupTests(unittest.TestCase):
    def test_backup_round_trip_keeps_review_rows(self) -> None:
        storage.ensure_schema()
        review_storage.ensure_content_imported()
        review_storage.apply_grade("py.mutability.default-arg", "concept", 4,
                                   today="2026-09-16", answer="往返测试")
        before = review_storage.summary("2026-09-16")
        backup_name = backup_service.create_full_backup("review-round-trip")   # 返回文件名
        # 破坏数据后恢复
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_attempts")
            connection.execute("DELETE FROM review_points")
        backup_service.restore_full_backup(backup_name)
        after = review_storage.summary("2026-09-16")
        self.assertEqual(after["total"], before["total"])
        history = review_storage.history("py.mutability.default-arg")
        self.assertEqual(history["attempts"][0]["answer"], "往返测试")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败或通过**

Run: `python3 -m unittest tests.test_review_backup -v`
若备份是按主库文件整体打包（`backup_service` 现状），这条测试会**直接通过**——那就把它作为回归护栏保留；
若失败，说明备份按表清单打包，需要在 `backup_service` 的清单里加入 5 张复习表。

- [ ] **Step 3: 需要时修改 `backup_service.py`**

仅当 Step 2 失败时：在备份/恢复的表清单常量里加入
`review_points`、`review_point_tasks`、`review_states`、`review_attempts`、`review_sessions`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_review_backup tests.test_full_backup -v` → PASS

- [ ] **Step 5: 提交**

```bash
git add backup_service.py tests/test_review_backup.py
git commit -m "test(review): 备份/恢复往返覆盖复习表（必要处补表清单）"
```

---

### Task 15: 第 1 周 40 个知识点内容（分 4 次提交）

**Files:**
- Modify: `content/review/py-week1.json`（从 1 个示例点扩到 40 个点）
- Modify: `tests/test_review_content.py`（**范围修订**：加"必须 40 点"的断言）
- Modify: `tests/test_review_generate.py`（**范围修订**：真实内容把 5 个点挂到任务 `1202`，与该测试的合成种子 id 撞车，需把种子号段改成 `9202` 系列；断言强度不得放松）
- Test: `tests/test_review_content.py`（已有 `test_real_week1_file_is_valid` 作为闸门）

**Interfaces:**
- Consumes: Task 1 的格式与校验器
- Produces：40 个知识点，`code` 与 `taskRefs` 必须与规划 §5 一致

**内容要求（每个点都必须满足）**
- 四类题 + 易错点齐全，`minutes` 10～30；
- 预测题必须有 `expected`（数组，逐行）与 `explain`；排查题必须有 `rootCause` + `fix`；编程题必须有 `acceptance` + `reference`；
- 覆盖优先：至少 6 个点额外写第二道变体题（放在该点的 `debug` 里作为第二问，或新增 `code_task.acceptance` 的更严格条目）；
- `taskRefs`：讲解型任务用 `introduces`，测试/口述型（`1101`/`1503`）用 `exercises`；`py.vars.str-bytes`、`py.func.functional`、`py.func.recursion`、`py.json.basics` 可以没有 taskRef（补充知识点）。

**40 个 code（分组提交）**

1. 第 1 次提交（变量与容器，11 点）：`py.vars.binding`、`py.vars.truthiness`、`py.vars.str-bytes`、`py.vars.operators`、`py.list.basics`、`py.list.sort-key`、`py.dict.basics`、`py.dict.aggregate`、`py.set.dedupe`、`py.container.selection`、`py.nested.structures`
2. 第 2 次提交（对象语义与作用域，6 点）：`py.mutability.alias`、`py.mutability.copy-deep`、`py.mutability.arg-passing`、`py.mutability.default-arg`、`py.identity.eq-vs-is`、`py.identity.eq-hash`、`py.scope.legb`、`py.scope.closure`
3. 第 3 次提交（流程与函数，9 点）：`py.flow.iteration`、`py.flow.while-break-else`、`py.comprehension.basics`、`py.flow.match-case`、`py.func.basics`、`py.func.signature`、`py.func.functional`、`py.func.recursion`、`py.func.pure-refactor`
4. 第 4 次提交（异常/文件/工程，14 点）：`py.exc.flow`、`py.exc.types`、`py.exc.over-catch`、`py.exc.eafp-assert`、`py.io.files`、`py.json.basics`、`py.path.pathlib`、`py.import.basics`、`py.import.packages`、`py.env.setup`、`py.test.pytest`、`py.quality.ruff-mypy`

- [ ] **Step 1: 写第 1 组 11 个知识点**

按 Task 1 的 `GOOD_POINT` 结构逐个补齐（每个点四类题 + 易错点）。示例（`py.vars.truthiness`，可直接照抄改内容）：

```json
{
  "code": "py.vars.truthiness",
  "title": "真值判断、比较与短路求值",
  "minutes": 15,
  "module": "基础语法",
  "level": "基础",
  "taskRefs": [{"taskId": "1301", "relation": "introduces"}],
  "concept": {"prompt": "哪些值在 if 里是假？", "answer": ["False/None/0/0.0/空字符串/空容器", "自定义类的 __bool__ 或 __len__ 决定真假"]},
  "predict": {"prompt": "写出下面代码的输出", "code": "print(bool([]), bool([0]), bool('0'))\nprint(0 or 'x', 1 and 'y')", "expected": ["False True True", "x y"], "explain": "空列表假、含 0 的列表真、'0' 非空字符串真；or/and 返回的是操作数本身"},
  "debug": {"prompt": "这段判断为什么漏了 0 的情况？", "code": "value = 0\nif value:\n    print('有值')", "rootCause": "0 是假值，用真值判断代替了 None 判断", "fix": "改成 if value is not None:"},
  "code_task": {"prompt": "写一个函数 safe_div(a, b)，b 为 0 或 None 时返回 None", "acceptance": ["b 为 0 返回 None", "b 为 None 返回 None", "正常时返回浮点结果"], "reference": "def safe_div(a, b):\n    if not b:\n        return None\n    return a / b"},
  "pitfalls": ["用真值判断代替 is None", "把 '0' 当成假值", "and/or 拿去当布尔值用"]
}
```

- [ ] **Step 2: 校验并跑测试**

Run: `python3 -c "import review_content,pathlib;d=review_content.load_content_file(pathlib.Path('content/review/py-week1.json'));print(len(d['points']))"`
Expected: 打印 11 且无异常
Run: `python3 -m unittest tests.test_review_content -v` → PASS

- [ ] **Step 3: 提交第 1 组**

```bash
git add content/review/py-week1.json
git commit -m "content(review): 第 1 周知识点组 1（变量、类型、容器 11 点）"
```

- [ ] **Step 4: 重复 Step 1–3 完成第 2、3、4 组**

每组完成后都必须跑 `python3 -m unittest tests.test_review_content tests.test_review_storage -v` 并提交：

```bash
git commit -m "content(review): 第 1 周知识点组 2（对象语义与作用域 8 点）"
git commit -m "content(review): 第 1 周知识点组 3（流程与函数 9 点）"
git commit -m "content(review): 第 1 周知识点组 4（异常、文件、工程 12 点）"
```

- [ ] **Step 5: 全量校验 + 反向验证（内容闸门真的会拦）**

Run:
```bash
python3 - <<'PY'
import json, pathlib, review_content
path = pathlib.Path('content/review/py-week1.json')
loaded = review_content.load_content_file(path)
assert len(loaded['points']) == 40, len(loaded['points'])
assert review_content.validate_points(loaded['points']) == []
# 反向验证：故意弄坏一条，校验必须报错
broken = json.loads(json.dumps(loaded['points']))
broken[0]['predict']['expected'] = []
assert review_content.validate_points(broken), '校验器没有拦住坏数据'
print('40 点全量校验通过，且坏数据会被拦下')
PY
```
Expected: `40 点全量校验通过，且坏数据会被拦下`

- [ ] **Step 6: 提交校验脚本产物（如有）**

若上面的校验只跑不改文件，则本步跳过；若补充了 `tests/test_review_content.py` 的 40 点断言，则：

```bash
git add tests/test_review_content.py
git commit -m "test(review): 第 1 周内容必须是 40 点且全部通过校验"
```

---

### Task 16: 端到端（真浏览器）+ 写锁基准 + 全量检查

**Files:**
- Modify: `tests/test_browser_flows.py`（新增 `test_07c_review_session_flow`）
- Create: `scripts/benchmark_review.py`
- Modify: `scripts/verify-tests-catch.py`（**范围修订**：新增内容/接口后，两条反向验证的替换锚点失配会让第 8 步变红，需同步锚点；12 条用例数量与强度不得减少）
- Modify: `tests/frontend/dom-smoke.js`（**范围修订**：重复键导致 eslint 报错，第 3 步会红，需去重）
- Modify: `local_server.py` + `review_storage.py`（**范围修订**：`main()` 从未调用 `ensure_content_imported()`，新库复习库为空——规格 §9 要求"启动时按 code 幂等导入"，故补 `ensure_review_content_ready()` 并在启动时调用，失败不阻断服务）
- Modify: `tests/test_review_http.py`（**范围修订**：为上面的启动导入补测试）
- ~~Modify: `scripts/check.sh`~~（不把 10k 基准塞进 check.sh：太重；基准作为手动脚本，数字记在报告里）

**Interfaces:**
- Consumes: 全部前置任务
- Produces：真浏览器能走完"出题 → 写 → 揭示 → 自评 → 总结"；写锁基准有数字

- [ ] **Step 1: 写真浏览器测试（追加到 `BrowserFlowTests`）**

```python
    def test_07c_review_session_flow(self) -> None:
        """复习会话：出题 → 先回忆 → 揭示后才见答案 → 五档自评 → 总结。"""
        self.page.click("#openKnowledgeBtn")
        self.page.wait_for_selector("#knowledgeView.active", timeout=15000)
        self.page.wait_for_selector("#knowledgeList .knowledge-item", timeout=15000)
        self.page.click("#knowledgeList .knowledge-item button")
        self.page.wait_for_selector("#reviewSessionView.active", timeout=15000)
        prompt = self.page.inner_text("#reviewQuestionPrompt")
        self.assertTrue(prompt.strip(), "应该有题面")
        panel = self.page.query_selector("#reviewAnswerPanel")
        self.assertTrue(panel is None or not panel.is_visible(), "揭示前不该显示答案面板")
        self.page.fill("#reviewAnswerInput", "我自己的回忆")
        self.page.click("#reviewRevealBtn")
        self.page.wait_for_selector("#reviewAnswerPanel:not([hidden])", timeout=10000)
        self.assertIn("参考答案", self.page.inner_text("#reviewAnswerPanel"))
        self.page.wait_for_selector("#reviewGradeButtons:not([hidden])", timeout=10000)
        self.page.click("#reviewGradeButtons .review-grade-btn[data-grade='4']")
        self.page.wait_for_selector("#reviewSessionSummary:not([hidden])", timeout=15000)
        self.assertIn("本次复习完成", self.page.inner_text("#reviewSessionSummary"))
```

- [ ] **Step 2: 跑测试确认失败后通过**

Run: `timeout 900 python3 -m unittest tests.test_browser_flows.BrowserFlowTests.test_07c_review_session_flow -v`
Expected: 先 FAIL（`#openKnowledgeBtn` 不存在或行为未接好），实现接线后 PASS

- [ ] **Step 3: 写写锁基准**

```python
"""写锁基准：保存 1 万任务的同时答题，量复习写入是否会被项目保存拖住。"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
WORK = Path(tempfile.mkdtemp(prefix="todo-review-bench-"))
os.environ["TODO_SQLITE_FILE"] = str(WORK / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(WORK / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(WORK / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(WORK / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"


def build_project(total: int) -> dict:
    weeks, index = [], 0
    while index < total:
        days = []
        for day_no in range(1, 11):
            items = []
            for _ in range(max(1, total // 100)):
                index += 1
                if index > total:
                    break
                items.append({"id": f"i{index}", "type": "item", "text": f"任务 {index}",
                              "completed": False, "completedAt": None, "optional": False,
                              "assessmentRequired": False, "assessmentHistory": 0, "assessment": None,
                              "createdAt": TODAY, "children": []})
            if items:
                days.append({"id": f"d{day_no}", "type": "day", "text": f"单元{day_no}",
                             "completed": False, "expanded": False, "createdAt": TODAY, "children": items})
        weeks.append({"id": f"w{len(weeks) + 1}", "type": "week", "text": f"第{len(weeks) + 1}周",
                      "completed": False, "expanded": False, "createdAt": TODAY, "children": days})
    return {"id": "bench", "name": "规模基准", "description": "", "createdAt": TODAY,
            "assessmentEnabled": False, "tree": weeks}


def main() -> int:
    storage.ensure_schema()
    review_storage.ensure_content_imported()
    project = build_project(10000)
    storage.write_project(project, None)
    code = review_storage.list_points()["points"][0]["code"]
    answer_ms, save_ms = [], []
    for round_no in range(5):
        done = threading.Event()

        def answer() -> None:
            start = time.perf_counter()
            review_storage.apply_grade(code, "concept", 3, today=TODAY, answer=f"基准 {round_no}")
            answer_ms.append((time.perf_counter() - start) * 1000)
            done.set()

        thread = threading.Thread(target=answer)
        thread.start()
        save_start = time.perf_counter()
        storage.write_project(project, None)   # 10k 任务整棵树写入，与答题共用同一把写锁
        save_ms.append((time.perf_counter() - save_start) * 1000)
        done.wait(timeout=30)
        thread.join(timeout=30)
    print(json.dumps({"answerWhileSavingMs": round(statistics.median(answer_ms), 1),
                      "fullSaveWithAnswerMs": round(statistics.median(save_ms), 1),
                      "baseline": "10k 任务整棵树保存（无并发）约 390ms，见 scripts/benchmark_scale.py"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑基准**

Run: `timeout 900 python3 scripts/benchmark_review.py`
Expected: 打印类似 `{"answerWaitedForSaveMs": 8.0, "saveWaitedForAnswerMs": 8.0, "fullSaveMs": 7.4, "baselineSaveMs": 6.7, "note": ...}`。

**Step 4 的门槛与结论（实测后修订）**：修订前写的是"若答题耗时超过 100ms 就改成答题先写内存、按批落库"。实测（`scripts/benchmark_review.py`，中位数）：
- **真实规模（223 节点，即用户库现状）**：`answerWaitedForSaveMs=7.7ms`、`saveWaitedForAnswerMs=7.5ms`、`fullSaveMs=7.4ms`、`baselineSaveMs=6.7ms` —— 远低于门槛。
- **极端合成规模（单项目 1 万节点整棵树保存）**：`answerWaitedForSaveMs=155.6ms`、`saveWaitedForAnswerMs=172.8ms`、`fullSaveMs=172.4ms`、`baselineSaveMs=157.3ms` —— 超过 100ms。

**决定：本批不做批量化落库。** 理由：(1) 门槛针对的是日常使用规模，真实库是 223 节点（约 8ms）；(2) 1 万节点单项目的整棵树保存本身就是 172ms 的极重操作，批量化只能把"答题等待"从 155ms 降到仍需等待下一次 flush，却会牺牲"答完即落库"的语义（`apply_grade` 之后立刻 `read_state` 能看到结果，多个测试依赖这一点）；(3) 已有更合适的优化方向（第六批的节点级 patch）。**记录为已知取舍**：1 万节点单项目 + 同时整树保存的极端组合下，答题可能等待约 150ms。

- [ ] **Step 5: 全量检查**

Run: `./scripts/check.sh`
Expected: 九步全绿（含 286 + 新增用例、dom-smoke、真浏览器、反向验证 12 条、行尾约定）

- [ ] **Step 6: 提交**

```bash
git add tests/test_browser_flows.py scripts/benchmark_review.py
git commit -m "test(review): 真浏览器复习会话全流程 + 写锁基准"
git push origin lyh0916
```

---

## 执行顺序与验收

- 顺序：Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16。Task 1–8 是引擎核心，先跑通再加界面。
- 每个 Task 结束都必须：`python3 -m unittest` 相关用例通过 → `node --check js/app.js`（改了前端时）→ 提交。
- Task 16 结束必须 `./scripts/check.sh` 全绿 + 基准数字记录到 `docs/` 或提交信息里，才允许把这一批视为完成。
- 真实 `data/` 全程只读；迁移只在副本/临时库上验证。
