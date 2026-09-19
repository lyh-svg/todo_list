# AI 现场出题（复习加练）· 第二批 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「收进题库」的 AI 题真正进入复习体系：`review_attempts` 记住这次问的是哪道题（`question_ref`），轮换在「固定题 + 已收藏 AI 题」里挑最近最少用过的一道；`reveal` / 五档自评 / AI 判分都按题身份走；同时补上「AI 题没进 JSON 导出快照」这个数据丢失缺口。

**Architecture:** schema v10→v11 只加一列（`ALTER TABLE review_attempts ADD COLUMN question_ref TEXT NOT NULL DEFAULT ''`，历史行语义天然是"固定题"）；`review_storage` 把原来的"按题型 LRU"升级成两段式 `pick_questions()`（先选题型，再在候选里选题）；HTTP 层给 `reveal`/`answer`/`ai-grade` 加一个可选 `questionRef` 透传；前端把队列里的 `questionRef` 原样带回，并在卡片上标出「AI 题库」。

**Tech Stack:** 同第一批（Python 标准库 + 原生前端 + unittest/DOM 桩/e2e）。

**Spec:** `docs/superpowers/specs/2026-09-19-ai-review-practice-design.md` §4.2 / §4.4 / §5.2 / §7；第一批计划：`docs/superpowers/plans/2026-09-19-ai-review-practice-batch1.md`

## Global Constraints

与第一批完全一致（见第一批计划同名章节）：CRLF/LF 行尾、零第三方运行时依赖、测试只在临时库、状态码口径（400/404/503/502）、新路径要登记白名单、改 js/css 要提升 `?v=`、迁移只做增量 DDL、提交前 `./scripts/check.sh` 9/9、反向验证条数与 `check.sh` 标签同步（本批 **68 → 70**）、不提交 `data/`。

---

## 文件结构（本批）

| 文件 | 责任 | 本批动作 |
| --- | --- | --- |
| `storage.py` | 建表 DDL / 迁移阶梯 / 复习表导出导入 | 改：v11 版本 + 新列（新建表也带上）+ `REVIEW_EXPORT_TABLES` / `REVIEW_IMPORT_COLUMNS` |
| `review_storage.py` | 复习数据读写与轮换 | 改：`pick_questions()`、`build_queue` 出题身份、`reveal(question_ref=)`、`apply_grade(question_ref=)`、修 `read_ai_question` 的键冲突 |
| `local_server.py` | HTTP 路由 | 改：`reveal` / `answer` / `ai-grade` 接 `questionRef` |
| `js/app.js` | 前端 | 改：队列 `questionRef` 透传 + 「AI 题库」徽标 |
| `tests/test_review_migration.py` | 迁移回归 | 改：版本断言 + v10→v11 用例 |
| `tests/test_review_rotation_ai.py` | 轮换回归 | 建 |
| `tests/test_review_ai_questions.py` | AI 题存储层 | 改：`read_ai_question` 的 `pointCode` 断言 |
| `tests/test_review_http.py` | HTTP 层 | 改：`questionRef` 透传、导出快照键、ai-grade 用对参考解 |
| `tests/frontend/dom-smoke.js` | 前端冒烟 | 改：`questionRef` 透传与徽标断言 |
| `tests/e2e-verify.sh` | 端到端 | 改：收藏 → 队列带身份 → 揭示/作答落 `question_ref` |
| `scripts/verify-tests-catch.py`、`scripts/check.sh` | 反向验证 | 改：+2 条、标签 70 |
| `README.md` | 文档 | 改：一句说明 AI 题会参与轮换 |

---

### Task 11: schema v10 → v11（`review_attempts.question_ref`）

**Files:**
- Modify: `storage.py`（`SCHEMA_VERSION`、`review_attempts` 建表语句、`_bootstrap_state_database` 的补列段、`ensure_schema` 阶梯注释）
- Test: `tests/test_review_migration.py`

**Interfaces:**
- Produces: `review_attempts.question_ref TEXT NOT NULL DEFAULT ''`（`''`=固定题，非空=`review_ai_questions.question_id`）；`storage.SCHEMA_VERSION == 11`

- [ ] **Step 1: 写失败的测试**

`tests/test_review_migration.py` 里版本断言改成 11（`test_schema_version_is_10` 改名 `test_schema_version_is_11`），并追加：

```python
    def test_v10_database_gains_question_ref_column(self) -> None:
        """v10 -> v11：给 review_attempts 加"题身份"列；历史行默认 ''（=固定题），数据不动。"""
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            connection.execute(
                "INSERT INTO review_attempts(id,code,task_id,project_id,question_type,grade,answer,"
                "ai_verdict,reviewed_on,duration_ms,session_id,created_at) "
                "VALUES('old-attempt','py.old.point','','','concept',4,'旧作答','','2026-09-19',0,'','2026-09-19T10:00:00')")
        # 伪装成"升级前的 v10 库"：把列删掉再退版本号
        with storage.open_state_database() as connection:
            connection.execute("ALTER TABLE review_attempts DROP COLUMN question_ref")
            connection.execute("PRAGMA user_version=10")
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            columns = {row[1] for row in connection.execute("PRAGMA table_info(review_attempts)")}
            row = connection.execute(
                "SELECT answer,question_ref FROM review_attempts WHERE id='old-attempt'").fetchone()
        self.assertEqual(version, storage.SCHEMA_VERSION)
        self.assertIn("question_ref", columns)
        self.assertEqual(row["answer"], "旧作答", "迁移不得丢历史作答")
        self.assertEqual(row["question_ref"], "", "历史行的题身份必须是固定题（''）")
        self.assertTrue(storage.check_database_integrity())
```

- [ ] **Step 2: 跑红**

```bash
python3 -m unittest tests.test_review_migration -v
```

Expected: 版本断言 FAIL（`10 != 11`）；新用例 FAIL（`question_ref` 不在列里）

- [ ] **Step 3: 实现（`storage.py`）**

1. `SCHEMA_VERSION = 11`
2. `CREATE TABLE IF NOT EXISTS review_attempts (...)` 里 `question_type TEXT NOT NULL,` 之后加一行：

```sql
            question_ref TEXT NOT NULL DEFAULT '',
```

3. `_bootstrap_state_database()` 末尾那段补列逻辑（`node_columns = {...}` 那批）之后追加：

```python
    attempt_columns = {row[1] for row in connection.execute("PRAGMA table_info(review_attempts)")}
    if "question_ref" not in attempt_columns:
        # v10 -> v11：题身份。默认 '' = 固定题，历史行语义天然正确，不需要回填。
        connection.execute(
            "ALTER TABLE review_attempts ADD COLUMN question_ref TEXT NOT NULL DEFAULT ''")
```

4. `ensure_schema()` 阶梯注释里 `_drop_removed_tables()` 之前补：

```python
            # v10 -> v11：给 review_attempts 加 question_ref（''=固定题，非空=收藏的 AI 题）。
            # 纯增量 ADD COLUMN + 默认值，无回填；老库由 bootstrap 的补列段补齐。
```

- [ ] **Step 4: 跑绿**

```bash
python3 -m unittest tests.test_review_migration tests.test_schema_and_import -v
```

Expected: 全 `ok`

- [ ] **Step 5: 提交**

```bash
git add storage.py tests/test_review_migration.py
git commit -m "feat(review): schema v11 —— review_attempts 记住题身份 question_ref"
```

---

### Task 12: 两段式挑题（题型 → 题）

**Files:**
- Modify: `review_storage.py`（`_question_types_by_code`、`pick_question_type`、`build_queue`）
- Test: Create `tests/test_review_rotation_ai.py`

**Interfaces:**
- Consumes: Task 11 的 `question_ref` 列、第一批的 `list_ai_questions` / `read_ai_question`
- Produces:
  - `review_storage.pick_questions(connection, codes, forced_type="") -> dict[code, {"questionType": str, "questionRef": str}]`
  - 删除旧的 `_question_types_by_code()`：除本模块外没有调用方（测试只用公开的 `pick_question_type`），
    留着就是一份重复实现
  - `build_queue` 的每个 item 增加 `questionRef`（`''`=固定题），且 prompt/body 来自被挑中的那道题

- [ ] **Step 1: 写失败测试**

新建 `tests/test_review_rotation_ai.py`：

```python
"""第二批：轮换必须在「固定题 + 已收藏 AI 题」里挑最近最少用过的一道。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP = tempfile.TemporaryDirectory(prefix="todo-rotation-ai-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP.name) / "memo.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

POINT = {
    "code": "py.rotation.point", "title": "轮换用知识点", "minutes": 15, "module": "函数",
    "level": "基础", "taskRefs": [{"taskId": "9001", "relation": "introduces"}],
    "concept": {"prompt": "固定概念题", "answer": ["固定答案"]},
    "predict": {"prompt": "固定预测题", "code": "print(1)", "expected": ["1"], "explain": "常量"},
    "debug": {"prompt": "固定找错题", "code": "x = 1", "rootCause": "无", "fix": "无"},
    "code_task": {"prompt": "固定写实现题", "acceptance": ["能跑"], "reference": "def f(): return 1"},
    "pitfalls": ["易错点"],
}
AI_REFERENCE = {"answer": ["AI 要点"], "expected": ["[1]"], "explain": "AI 解释",
                "reference": "def f(items=None):\n    return items"}


class RotationWithAiQuestionTests(unittest.TestCase):
    def setUp(self) -> None:
        storage.ensure_schema()
        with storage.open_state_database() as connection:
            for table in ("review_points", "review_point_tasks", "review_attempts",
                          "review_states", "review_ai_questions"):
                connection.execute(f"DELETE FROM {table}")
        review_storage.import_content([POINT], week=1)
        # 让这个点进入"今天到期"，build_queue 才会带上它
        review_storage.apply_grade(POINT["code"], "concept", 4, today="2026-09-15",
                                   answer="先答一次概念题")

    def _collect(self, prompt: str, kind: str = "concept") -> str:
        return review_storage.collect_ai_question(
            POINT["code"], kind, prompt, "", "考察点", dict(AI_REFERENCE))["id"]

    def _queue_item(self, **kwargs) -> dict:
        with storage.open_state_database() as connection:
            picked = review_storage.pick_questions(
                connection, [POINT["code"]], forced_type=kwargs.get("forced_type", ""))
        return picked[POINT["code"]]

    def test_pick_is_deterministic_and_uses_ai_question_when_never_used(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        picked = self._queue_item(forced_type="concept")
        # 固定概念题已经用过一次（setUp 那次），AI 题从未用过 → 必须先挑 AI 题
        self.assertEqual(picked["questionType"], "concept")
        self.assertEqual(picked["questionRef"], ai_id)

    def test_fixed_question_wins_when_it_is_the_least_recently_used(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        review_storage.apply_grade(POINT["code"], "concept", 4, today="2026-09-16",
                                   answer="先做 AI 题", question_ref=ai_id)
        picked = self._queue_item(forced_type="concept")
        # 固定题上次是 09-15，AI 题是 09-16 → 固定题更久没用，必须挑固定题
        self.assertEqual(picked["questionRef"], "")

    def test_deleted_question_is_not_a_candidate_but_history_survives(self) -> None:
        ai_id = self._collect("会被删掉的 AI 题")
        review_storage.apply_grade(POINT["code"], "concept", 3, today="2026-09-16",
                                   answer="做过再删", question_ref=ai_id)
        review_storage.delete_ai_question(ai_id)
        picked = self._queue_item(forced_type="concept")
        self.assertEqual(picked["questionRef"], "", "已删除的题不能再被抽中")
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT question_ref FROM review_attempts WHERE question_ref=?", (ai_id,)).fetchone()
        self.assertIsNotNone(row, "删除题库条目不能连带删掉历史作答")

    def test_queue_item_carries_question_ref_and_ai_prompt(self) -> None:
        ai_id = self._collect("AI 现场概念题：说说定义时求值")
        queue = review_storage.build_queue("2026-09-19", limit=10, code=POINT["code"])
        item = next(entry for entry in queue["items"] if entry["code"] == POINT["code"])
        self.assertEqual(item["questionRef"], ai_id)
        self.assertEqual(item["prompt"], "AI 现场概念题：说说定义时求值")
        self.assertEqual(item["questionType"], "concept")

    def test_type_selection_still_prefers_never_used_type(self) -> None:
        self._collect("AI 概念题")
        picked = self._queue_item()
        # 概念题已用过（固定+AI 都算这个题型用过），predict/debug/code_task 全没用过 →
        # 先选题型仍是"从未用过"的那几种之一（按声明顺序 = predict），与旧行为一致
        self.assertEqual(picked["questionType"], "predict")
        self.assertEqual(picked["questionRef"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    _TEMP.cleanup()
```

- [ ] **Step 2: 跑红**

```bash
python3 -m unittest tests.test_review_rotation_ai -v
```

Expected: `AttributeError: module 'review_storage' has no attribute 'pick_questions'` / `apply_grade() got an unexpected keyword argument 'question_ref'`（Task 13 才加参数，这里先红是预期的；若想按顺序更顺，可先做 Task 13 的 `apply_grade` 改动再回来，见 Task 13 Step 3）

- [ ] **Step 3: 实现（`review_storage.py`）**

把 `_question_types_by_code` 整段替换为下面两个函数（保留旧名字做兼容薄壳）：

```python
def pick_questions(connection, codes: list[str], forced_type: str = "") -> dict[str, dict[str, str]]:
    """批量挑题：两段式。

    ① 选题型：仍是"这个知识点最近最少用过的题型"（从未用过优先，并列按声明顺序）——
       没有收藏 AI 题时结果与旧版逐字节一致；
    ② 选题：在该题型的候选（固定题 `''` + 该题型下已收藏的 AI 题）里挑最近最少用过的一道；
       都没用过时固定题优先，其次 question_id 升序 → 结果确定、可复现。
    """
    wanted = [str(code) for code in codes]
    if not wanted:
        return {}
    last_used: dict[tuple[str, str, str], str] = {}
    type_last: dict[tuple[str, str], str] = {}
    variants: dict[tuple[str, str], list[str]] = {}
    for start in range(0, len(wanted), storage.SQL_PARAM_CHUNK):
        chunk = wanted[start:start + storage.SQL_PARAM_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        for row in connection.execute(
                "SELECT code,question_type,question_ref,MAX(created_at) AS last_at FROM review_attempts "
                f"WHERE code IN ({placeholders}) GROUP BY code,question_type,question_ref", chunk):
            code = str(row["code"])
            kind = str(row["question_type"])
            ref = str(row["question_ref"] or "")
            last_at = str(row["last_at"])
            last_used[(code, kind, ref)] = last_at
            if last_at > type_last.get((code, kind), ""):
                type_last[(code, kind)] = last_at
        for row in connection.execute(
                "SELECT question_id,code,question_type FROM review_ai_questions "
                f"WHERE code IN ({placeholders}) ORDER BY created_at,question_id", chunk):
            variants.setdefault((str(row["code"]), str(row["question_type"])), []).append(
                str(row["question_id"]))
    kinds = review_content.QUESTION_TYPES
    picked: dict[str, dict[str, str]] = {}
    for code in wanted:
        kind = forced_type or min(
            kinds, key=lambda candidate: (type_last.get((code, candidate), ""), kinds.index(candidate)))
        candidates = [""] + variants.get((code, kind), [])
        question_ref = min(
            candidates,
            key=lambda ref: (last_used.get((code, kind, ref), ""), 0 if ref == "" else 1, ref))
        picked[code] = {"questionType": kind, "questionRef": question_ref}
    return picked


（`_question_types_by_code()` 连同它批量查 attempts 的那段逻辑一起删掉：题型、候选与题身份现在统一由
`pick_questions()` 计算，保留旧函数等于留下第二份实现。）

```
`pick_question_type(code, today)` 内部改成：

```python
    with _connection() as connection:
        picked = pick_questions(connection, [str(code)]).get(str(code), {})
    return picked.get("questionType", review_content.QUESTION_TYPES[0])
```

`build_queue()` 里"题型与题面一次查完"那一段整体替换为：

```python
        chosen_codes = [str(item["code"]) for item in chosen]
        picked = pick_questions(connection, chosen_codes, forced_type=question_type)
        content_by_code: dict[str, Any] = {}
        for start in range(0, len(chosen_codes), storage.SQL_PARAM_CHUNK):
            chunk = chosen_codes[start:start + storage.SQL_PARAM_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            for row in connection.execute(
                    f"SELECT code,content_json FROM review_points WHERE code IN ({placeholders})", chunk):
                content_by_code[str(row["code"])] = json.loads(row["content_json"])
        ai_content: dict[str, Any] = {}
        ai_refs = sorted({plan["questionRef"] for plan in picked.values() if plan["questionRef"]})
        for start in range(0, len(ai_refs), storage.SQL_PARAM_CHUNK):
            chunk = ai_refs[start:start + storage.SQL_PARAM_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            for row in connection.execute(
                    f"SELECT question_id,content_json FROM review_ai_questions "
                    f"WHERE question_id IN ({placeholders})", chunk):
                ai_content[str(row["question_id"])] = json.loads(row["content_json"])
        for item in chosen:
            plan = picked.get(str(item["code"]), {})
            kind = plan.get("questionType", review_content.QUESTION_TYPES[0])
            question_ref = plan.get("questionRef", "")
            item["questionType"] = kind
            item["questionRef"] = question_ref
            # prompt 与 body（predict/debug 要预测或排查的代码片段）都是**题面**的一部分：
            # 用户必须看到才能作答；参考答案只在 reveal() 里给。
            if question_ref:
                block = ai_content.get(question_ref) or {}
            else:
                block = (content_by_code.get(str(item["code"])) or {}).get(kind) or {}
            item["prompt"] = str(block.get("prompt") or "")
            item["body"] = str(block.get("code") or "")
```

- [ ] **Step 4: 跑绿**

```bash
python3 -m unittest tests.test_review_rotation_ai tests.test_review_queue_batch tests.test_review_schedule -v
```

Expected: 全 `ok`（旧轮换用例不回归）

- [ ] **Step 5: 提交**

```bash
git add review_storage.py tests/test_review_rotation_ai.py
git commit -m "feat(review): 轮换两段式选题（题型 → 固定题/已收藏 AI 题）并给队列带上 questionRef"
```

---

### Task 13: `reveal` / `apply_grade` 按题身份走（含已删题回退）

**Files:**
- Modify: `review_storage.py`（`read_ai_question` 键冲突修复、`reveal`、`apply_grade`）
- Test: `tests/test_review_rotation_ai.py`（Task 12 已含 `apply_grade(question_ref=)` 用法）、`tests/test_review_ai_questions.py`（`pointCode` 断言）

**Interfaces:**
- Produces:
  - `review_storage.read_ai_question(id)` 改为返回 `{"id", "pointCode", "questionType", "prompt", "code", "focus", "reference", "createdAt"}`（`code`=题面代码，`pointCode`=知识点）
  - `review_storage.reveal(code, question_type, question_ref="")`：指定 AI 题则返回它存下的参考解（键与固定题一致，额外带 `questionRef` 与 `source="ai"`）；题已删/不匹配则回退固定题并带 `questionRefFallback: True`
  - `review_storage.apply_grade(..., question_ref="")`：写进 `review_attempts.question_ref`

- [ ] **Step 1: 写失败测试**

在 `tests/test_review_ai_questions.py` 的 `test_read_and_delete_question` 里补两行断言（`read_ai_question` 的键冲突修复）：

```python
        self.assertEqual(stored["pointCode"], POINT["code"])
        self.assertEqual(stored["code"], "def f(items=[]):\n    items.append(1)\n    return items",
                         "题面代码与知识点 code 不能互相覆盖")
```

在 `tests/test_review_rotation_ai.py` 追加：

```python
    def test_reveal_ai_question_returns_its_own_reference(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        revealed = review_storage.reveal(POINT["code"], "concept", ai_id)
        self.assertEqual(revealed["source"], "ai")
        self.assertEqual(revealed["questionRef"], ai_id)
        self.assertEqual(revealed["reference"], "def f(items=None):\n    return items")
        self.assertIn("AI 要点", revealed["answer"])
        self.assertEqual(revealed["pointCode"], POINT["code"])
        self.assertEqual(revealed["type"], "concept")

    def test_reveal_falls_back_when_ai_question_is_gone(self) -> None:
        ai_id = self._collect("会被删掉的 AI 题")
        review_storage.delete_ai_question(ai_id)
        revealed = review_storage.reveal(POINT["code"], "concept", ai_id)
        self.assertTrue(revealed.get("questionRefFallback"), "已删题必须回退固定题并标记")
        self.assertEqual(revealed.get("answer"), ["固定答案"], "回退后给的是固定题参考答案")

    def test_apply_grade_records_question_ref(self) -> None:
        ai_id = self._collect("AI 现场概念题")
        review_storage.apply_grade(POINT["code"], "concept", 5, today="2026-09-20",
                                   answer="这次会了", question_ref=ai_id)
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT question_ref FROM review_attempts WHERE answer='这次会了'").fetchone()
        self.assertEqual(row["question_ref"], ai_id)
```

- [ ] **Step 2: 跑红**

```bash
python3 -m unittest tests.test_review_ai_questions tests.test_review_rotation_ai -v
```

Expected: `pointCode` KeyError / `reveal() takes 2 positional arguments but 3 were given` / `apply_grade() got an unexpected keyword argument 'question_ref'`

- [ ] **Step 3: 实现（`review_storage.py`）**

(a) `read_ai_question` 的返回改成（列里的 code 是**知识点**，content 里的 code 是**题面代码**，不能同名）：

```python
    return {"id": str(row["question_id"]), "pointCode": str(row["code"]),
            "questionType": str(row["question_type"]), "createdAt": str(row["created_at"]),
            **content}
```

(b) `apply_grade` 签名加 `question_ref: str = ""`，INSERT 语句与参数补上该列：

```python
            "INSERT INTO review_attempts(id,code,task_id,project_id,question_type,question_ref,grade,answer,"
            "ai_verdict,reviewed_on,duration_ms,session_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), code, str(task_id or ""), str(project_id or ""), question_type,
             str(question_ref or ""), int(grade), str(answer or ""), str(ai_verdict or ""), today,
             max(0, int(duration_ms or 0)), str(session_id or ""), _now()))
```

并在函数 docstring 后加一句约束：`question_ref` 为空表示固定题；非空时不校验存在性（题可能已被删，历史仍要留）。

(c) `reveal` 改成：

```python
def reveal(code: str, question_type: str, question_ref: str = "") -> dict[str, Any]:
    """揭示答案：这是唯一会返回参考答案/历史答案的入口。

    题型自带字段（含 predict/debug 要预测或排查的 `code` 题面片段）原样保留；
    知识点 code 改用 `pointCode` 单独暴露，避免覆盖题面片段。
    `question_ref` 非空时给的是收藏的 AI 题自己的参考解；题已删/不匹配则回退固定题并标记。
    """
    if question_type not in review_content.QUESTION_TYPES:
        raise ValueError("题型不正确")
    ref = str(question_ref or "")
    if ref:
        stored = read_ai_question(ref)
        if stored and stored["pointCode"] == str(code) and stored["questionType"] == question_type:
            content, detail = _history_detail(str(code), 20)
            block = dict(stored.get("reference") or {})
            block.update({"code": str(stored.get("code") or ""), "pointCode": str(code),
                          "type": question_type, "title": detail["title"],
                          "pitfalls": detail["pitfalls"], "history": detail["attempts"],
                          "state": detail["state"], "questionRef": ref, "source": "ai",
                          "prompt": str(stored.get("prompt") or ""),
                          "focus": str(stored.get("focus") or "")})
            return block
        fallback = reveal(str(code), question_type)
        fallback["questionRefFallback"] = True
        return fallback
    content, detail = _history_detail(str(code), 20)
    block = dict(content.get(question_type) or {})
    block.update({"pointCode": str(code), "type": question_type, "title": detail["title"],
                  "pitfalls": detail["pitfalls"], "history": detail["attempts"],
                  "state": detail["state"], "questionRef": ""})
    return block
```

- [ ] **Step 4: 跑绿**

```bash
python3 -m unittest tests.test_review_ai_questions tests.test_review_rotation_ai tests.test_review_schedule -v
```

Expected: 全 `ok`

- [ ] **Step 5: 提交**

```bash
git add review_storage.py tests/test_review_ai_questions.py tests/test_review_rotation_ai.py
git commit -m "feat(review): 揭示答案与作答记录按题身份走（已删 AI 题回退固定题）"
```

---

### Task 14: HTTP 层透传 `questionRef`

**Files:**
- Modify: `local_server.py`（`/api/review/reveal`、`/api/review/answer`、`/api/review/ai-grade`）
- Test: `tests/test_review_http.py`

**Interfaces:**
- Consumes: Task 12/13 的 `build_queue` item（含 `questionRef`）、`reveal(code, type, ref)`、`apply_grade(..., question_ref=)`
- Produces: 三个端点接受可选 `questionRef`（缺省 `''`，行为与旧请求完全一致）

- [ ] **Step 1: 写失败测试**

在 `tests/test_review_http.py` 的 `ReviewHttpTests` 里追加（该类的 `call` 返回 `(status, payload)`）：

```python
    def test_review_reveal_and_answer_carry_question_ref(self) -> None:
        saved = review_storage.collect_ai_question(
            MUTABLE_DEFAULT, "concept", "AI 现场概念题", "", "考察点",
            {"answer": ["要点"], "explain": "解释", "reference": "def f(): return 1"})
        status, payload = self.call("/api/review/reveal", "POST", {
            "code": MUTABLE_DEFAULT, "type": "concept", "questionRef": saved["id"]})
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["source"], "ai")
        self.assertEqual(payload["questionRef"], saved["id"])
        status, payload = self.call("/api/review/answer", "POST", {
            "code": MUTABLE_DEFAULT, "type": "concept", "grade": 4, "today": TODAY,
            "answer": "我的答案", "questionRef": saved["id"]})
        self.assertEqual(status, 200, payload)
        with storage.open_state_database() as connection:
            row = connection.execute(
                "SELECT question_ref FROM review_attempts WHERE answer='我的答案'").fetchone()
        self.assertEqual(row["question_ref"], saved["id"])
        review_storage.delete_ai_question(saved["id"])

    def test_ai_grade_uses_the_ai_question_reference(self) -> None:
        saved = review_storage.collect_ai_question(
            MUTABLE_DEFAULT, "concept", "AI 现场概念题", "", "考察点",
            {"explain": "AI 解释", "reference": "def f(): return 1"})
        captured = {}

        def fake_grade(*, code, question_type, answer, reference):
            captured["reference"] = reference
            return {"correct": True, "missing": [], "wrongAt": "", "hint": ""}

        with mock.patch.object(ai_service, "is_configured", return_value=True), \
                mock.patch.object(ai_service, "grade_review_answer", side_effect=fake_grade):
            status, payload = self.call("/api/review/ai-grade", "POST", {
                "code": MUTABLE_DEFAULT, "type": "concept", "answer": "我的答案",
                "questionRef": saved["id"]})
        self.assertEqual(status, 200, payload)
        self.assertEqual(captured["reference"]["reference"], "def f(): return 1",
                         "AI 题必须拿它自己的参考解去判分，不能拿固定题的")
        review_storage.delete_ai_question(saved["id"])
```

- [ ] **Step 2: 跑红**

```bash
python3 -m unittest tests.test_review_http.ReviewHttpTests.test_review_reveal_and_answer_carry_question_ref tests.test_review_http.ReviewHttpTests.test_ai_grade_uses_the_ai_question_reference -v
```

Expected: 两条 FAIL（`questionRef` 被忽略：`source`/`question_ref` 拿不到；ai-grade 用的是固定题参考解）

- [ ] **Step 3: 实现（`local_server.py`）**

`/api/review/reveal` 分支：

```python
            elif path == "/api/review/reveal":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("type") or "").strip()
                question_ref = str(payload.get("questionRef") or "").strip()
                if not code or kind not in review_content.QUESTION_TYPES:
                    raise ValueError("知识点或题型不正确")
                data = review_storage.reveal(code, kind, question_ref)
                self.send_json(200, data)
```

`/api/review/answer` 分支：读出 `question_ref = str(payload.get("questionRef") or "").strip()`，并在 `apply_grade(...)` 调用里加 `question_ref=question_ref`。

`/api/review/ai-grade` 分支：读出 `question_ref`，把 `reference=review_storage.reveal(code, kind)` 改成 `reference=review_storage.reveal(code, kind, question_ref)`。

- [ ] **Step 4: 跑绿**

```bash
python3 -m unittest tests.test_review_http -v
```

Expected: 全 `ok`

- [ ] **Step 5: 提交**

```bash
git add local_server.py tests/test_review_http.py
git commit -m "feat(review): reveal/answer/ai-grade 支持 questionRef 透传"
```

---

### Task 15: 前端透传 `questionRef` 并标出「AI 题库」

**Files:**
- Modify: `js/app.js`（`reviewEntryToItem`、`practicePoint` 的兜底 item、`revealReviewAnswer`、五档自评提交、`requestAiGrade`、复习卡片 meta）
- Test: `tests/frontend/dom-smoke.js`

**Interfaces:**
- Consumes: Task 12/14 的队列 item 字段 `questionRef`、端点参数 `questionRef`
- Produces: 会话 item 带 `questionRef`；reveal/answer/ai-grade 的请求体带 `questionRef`；卡片 meta 出现 `AI 题库`

- [ ] **Step 1: 写失败测试**

在 `tests/frontend/dom-smoke.js` 的 `/api/review/queue` 桩里给第一题加 `questionRef: 'ai-q-1'`（`py.a.b` 那条），并新增一个记录请求体的数组（与既有 `reviewAnswerBodies` 同风格）：

```js
const reviewRevealBodies = [];
```

在 `/api/review/reveal` 桩里记录 `reviewRevealBodies.push(revealRequest)`（紧跟解析 body 之后）。

在主流程 ⑰ 之前追加：

```js
    // ⑲ 队列里的 AI 题：卡片要标出来，reveal / 自评 / AI 判分都要把题身份带回去
    elementsById.get('reviewQueueBtn').dispatch('click');
    await sleep(80);
    const aiRow = findAll(elementsById.get('reviewBody'), el => textOf(el).includes('示例知识点'))[0];
    if (aiRow) step('点击 AI 题库来源的题不抛异常', () => aiRow.dispatch('click'));
    await sleep(120);
    check('AI 题在卡片上被标成「AI 题库」',
        textOf(elementsById.get('reviewQuestionMeta')).includes('AI 题库'),
        textOf(elementsById.get('reviewQuestionMeta')));
    elementsById.get('reviewRevealBtn').dispatch('click');
    await sleep(120);
    check('揭示答案时带上了 questionRef',
        reviewRevealBodies.slice(-1)[0]?.questionRef === 'ai-q-1',
        JSON.stringify(reviewRevealBodies.slice(-1)[0]));
    const gradeBtn = findAll(elementsById.get('reviewGradeButtons'), el => el.textContent === '基本掌握')[0];
    if (gradeBtn) step('提交自评不抛异常', () => gradeBtn.dispatch('click'));
    await sleep(120);
    check('自评提交也带上 questionRef',
        reviewAnswerBodies.slice(-1)[0]?.questionRef === 'ai-q-1',
        JSON.stringify(reviewAnswerBodies.slice(-1)[0]));
```

- [ ] **Step 2: 跑红**

```bash
node tests/frontend/dom-smoke.js 2>&1 | tail -12
```

Expected: 三条新断言失败（meta 没有 `AI 题库`；请求体没有 `questionRef`）

- [ ] **Step 3: 实现（`js/app.js`）**

1. `reviewEntryToItem(entry)` 返回的对象里加一行：

```js
        questionRef: String(entry.questionRef || ''),
```

2. `practicePoint()` 的兜底 item 里加 `questionRef: ''`（与其它字段并列）。

3. `revealReviewAnswer()` 的请求体：

```js
            data = await callApi('/api/review/reveal', 'POST', {
                code: item.code, type: item.questionType, questionRef: item.questionRef || '' });
```

4. 五档自评提交（`/api/review/answer` 的那次 `callApi`）与可选 AI 判分（`/api/review/ai-grade` 的那次）的请求体里各加：

```js
                questionRef: item.questionRef || '',
```

5. 复习卡片 meta（`renderReviewQuestion` 里设置 `reviewQuestionMeta.textContent` 的那行）末尾追加：

```js
            + (item.questionRef ? ' · AI 题库' : '')
```

- [ ] **Step 4: 跑绿**

```bash
node tests/frontend/dom-smoke.js 2>&1 | tail -6
```

Expected: `失败 0 项`

- [ ] **Step 5: 提交**

```bash
git add js/app.js tests/frontend/dom-smoke.js
git commit -m "feat(review): 前端透传 questionRef 并在卡片上标出「AI 题库」"
```

---

### Task 16: 修数据丢失缺口 —— AI 题纳入 JSON 导出/导入快照

**背景（这是第一批遗留的真缺口）：** `review_ai_questions` 是用户数据，但 `_read_review_export()` 只导出 5 张表、`import_review_snapshot()` 只认 `REVIEW_IMPORT_COLUMNS` 里的列 —— 于是「导出 JSON → 在新库导入」会静默丢掉收藏的 AI 题（整库 zip 备份不受影响）。

**Files:**
- Modify: `storage.py`（`REVIEW_EXPORT_TABLES`、`REVIEW_IMPORT_COLUMNS`）
- Test: `tests/test_review_http.py`（`REVIEW_EXPORT_KEYS`）、`tests/test_review_backup.py`（若有整表计数断言）

**Interfaces:**
- Produces: 复习快照新增 `aiQuestions` 键；`attempts` 的导入列新增 `questionRef`

- [ ] **Step 1: 写失败测试**

`tests/test_review_http.py` 顶部：

```python
REVIEW_EXPORT_KEYS = ("points", "pointTasks", "states", "attempts", "sessions", "aiQuestions")
```

并追加：

```python
    def test_export_and_import_round_trip_keeps_ai_questions(self) -> None:
        saved = review_storage.collect_ai_question(
            MUTABLE_DEFAULT, "predict", "导出往返要留住我", "print(1)", "考察点",
            {"expected": ["1"], "explain": "常量", "reference": "print(1)"})
        snapshot = storage.export_projects_snapshot()
        exported = snapshot["review"]["aiQuestions"]
        self.assertEqual([item["id"] for item in exported], [saved["id"]])
        review_storage.delete_ai_question(saved["id"])
        self.assertEqual(review_storage.list_ai_questions(MUTABLE_DEFAULT), [])
        storage.import_review_snapshot(snapshot["review"])
        restored = review_storage.list_ai_questions(MUTABLE_DEFAULT)
        self.assertEqual([item["id"] for item in restored], [saved["id"]],
                         "导入快照必须把收藏的 AI 题带回来")
        self.assertEqual(review_storage.read_ai_question(saved["id"])["reference"]["expected"], ["1"])
        review_storage.delete_ai_question(saved["id"])
```

- [ ] **Step 2: 跑红**

```bash
python3 -m unittest tests.test_review_http.ReviewHttpTests.test_export_and_import_round_trip_keeps_ai_questions -v
```

Expected: FAIL（`review.export` 里没有 `aiQuestions` 键 → KeyError）

- [ ] **Step 3: 实现（`storage.py`）**

`REVIEW_EXPORT_TABLES` 增加一行：

```python
    "aiQuestions": ("review_ai_questions", "question_id"),
```

`REVIEW_IMPORT_COLUMNS` 的 `attempts` 元组里加 `("questionRef", "question_ref")`（放在 `("questionType", "question_type")` 之后），并新增：

```python
    "aiQuestions": (
        ("id", "question_id"), ("code", "code"), ("questionType", "question_type"),
        ("content", "content_json"), ("createdAt", "created_at"), ("updatedAt", "updated_at"),
    ),
```

（`_read_review_export` 会把 `content_json` 解析成对象、`_review_import_value` 会写回 JSON 文本，与 `points.content` 同一套机制，无需额外代码。）

- [ ] **Step 4: 跑绿**

```bash
python3 -m unittest tests.test_review_http tests.test_review_backup tests.test_export_snapshot tests.test_import_export_templates -v
```

Expected: 全 `ok`（若 `tests/test_review_backup.py` 里有整表计数/键集合断言，按同样口径把 `aiQuestions` 补上，并在报告里说明）

- [ ] **Step 5: 提交**

```bash
git add storage.py tests/test_review_http.py
git commit -m "fix(review): AI 题纳入 JSON 导出/导入快照，修掉收藏题在导出往返中丢失"
```

---

### Task 17: e2e + 反向验证 +2 + 全量门禁

**Files:**
- Modify: `tests/e2e-verify.sh`、`scripts/verify-tests-catch.py`、`scripts/check.sh`、`README.md`

**Interfaces:**
- Consumes: 前六个任务的全部产物
- Produces: e2e 的"收藏 → 队列带身份 → 揭示/作答落库"证据；68 → 70 条反向验证；门禁 9/9

- [ ] **Step 1: e2e 断言**

在 `tests/e2e-verify.sh` 的 python 块里、第一批新增的 AI 段落**之后**追加：

```python
# --- 第二批：收藏的 AI 题要能被队列抽中，并按题身份揭示/作答 ---
status, _, data = call("/api/review/ai-collect", method="POST", body={
    "code": target_code, "questionType": "concept", "prompt": "第二批：AI 题进轮换",
    "questionCode": "", "focus": "题身份", "reference": {
        "answer": ["要点"], "explain": "解释", "reference": "def f(): return 1"}})
second_id = (json.loads(data).get("question") or {}).get("id") if status == 200 else ""
status, _, data = call("/api/review/queue?today=" + TODAY_STR + "&code=" + urllib.parse.quote(target_code)
                       + "&newPerDay=1")
item = next((entry for entry in json.loads(data).get("items", []) if entry["code"] == target_code), {})
check("第二批 队列带上 questionRef（未用过的 AI 题优先被抽中）",
      status == 200 and item.get("questionRef") == second_id, f"item={str(item)[:200]}")
check("第二批 队列题面来自被抽中的 AI 题",
      item.get("prompt") == "第二批：AI 题进轮换", str(item.get("prompt"))[:120])
status, _, data = call("/api/review/reveal", method="POST", body={
    "code": target_code, "type": "concept", "questionRef": second_id})
revealed = json.loads(data)
check("第二批 揭示的是该 AI 题自己的参考解",
      status == 200 and revealed.get("source") == "ai"
      and revealed.get("reference") == "def f(): return 1", f"status={status} body={data[:200]}")
status, _, data = call("/api/review/answer", method="POST", body={
    "code": target_code, "type": "concept", "grade": 4, "today": TODAY_STR,
    "answer": "第二批作答", "questionRef": second_id})
check("第二批 作答按题身份落库", status == 200, f"status={status}")
connection = _sqlite3.connect(_os.environ["TODO_SQLITE_FILE"])
try:
    row = connection.execute(
        "SELECT question_ref FROM review_attempts WHERE answer='第二批作答'").fetchone()
finally:
    connection.close()
check("第二批 review_attempts.question_ref 记的是这道 AI 题",
      bool(row) and row[0] == second_id, str(row))
status, _, data = call("/api/review/ai-question?id=" + urllib.parse.quote(second_id), method="DELETE")
check("第二批 清理收藏题", status == 200, f"status={status}")
```

- [ ] **Step 2: 跑一遍确认红→绿**

```bash
bash tests/e2e-verify.sh 2>&1 | tail -16
```

Expected: 若 Task 12-14 已落地则直接全 ✔；任何 ✘ 先判断是实现问题还是断言问题，修完再跑

- [ ] **Step 3: 反向验证 +2 条**

在 `scripts/verify-tests-catch.py` 的 `CASES` 末尾追加：

```python
    (
        "轮换候选必须包含已收藏的 AI 题（否则收藏了也永远抽不到）",
        "review_storage.py",
        crlf('        candidates = [""] + variants.get((code, kind), [])\n'),
        crlf('        candidates = [""]\n'),
        [sys.executable, "-m", "unittest",
         "tests.test_review_rotation_ai.RotationWithAiQuestionTests"
         ".test_pick_is_deterministic_and_uses_ai_question_when_never_used"],
    ),
    (
        "题型内必须挑最近最少用过的一道（不能永远固定题优先）",
        "review_storage.py",
        crlf('        question_ref = min(\n'
             '            candidates,\n'
             '            key=lambda ref: (last_used.get((code, kind, ref), ""), 0 if ref == "" else 1, ref))\n'),
        crlf('        question_ref = ""\n'),
        [sys.executable, "-m", "unittest",
         "tests.test_review_rotation_ai.RotationWithAiQuestionTests"
         ".test_fixed_question_wins_when_it_is_the_least_recently_used"],
    ),
```

`scripts/check.sh` 标签改 70：

```bash
    run "verify-tests-catch.py（70 条）" python3 scripts/verify-tests-catch.py
```

- [ ] **Step 4: README**

功能清单里 AI 加练那一条后面补一句：

```markdown
  收藏的 AI 题会参与轮换（卡片上标「AI 题库」），每道题各自记录作答与排期
```

- [ ] **Step 5: 全量门禁 + 性能**

```bash
python3 scripts/verify-tests-catch.py 2>&1 | tail -5
./scripts/check.sh 2>&1 | tail -30
python3 scripts/benchmark_scale.py 2>&1 | tail -18
```

Expected: 反向验证 70 条全 ✔；门禁 9/9；基准无回归（10000 任务：读取 ≈140 ms、复习队列 ≈8 ms 量级）

- [ ] **Step 6: 提交**

```bash
git add tests/e2e-verify.sh scripts/verify-tests-catch.py scripts/check.sh README.md
git commit -m "test(review): 第二批 e2e 与反向验证；README 说明 AI 题参与轮换"
```

---

## Self-Review

**1. Spec 覆盖**

| Spec | 任务 |
| --- | --- |
| §4.2 `question_ref` 列（v10→v11） | Task 11 |
| §4.4 轮换候选含 AI 题、从未用过优先、确定性并列、删除后不再抽中、历史保留 | Task 12（候选与挑选）、Task 13（历史保留由 attempts 保证） |
| §4.5 `reveal` 已删题回退固定题 + 提示 | Task 13 |
| §5.2 reveal/answer 支持 `questionRef`、queue 返回 questionRef | Task 12/14 |
| §7 单元/HTTP/前端/e2e/反向/性能 | Task 11-14、16、17 |
| 需求 6「收藏的题与固定题一起参与轮换」 | Task 12 + Task 17 的 e2e 断言 |

**2. 计划外但有必要的修复（本批一并做，已在报告里说明）**
- `read_ai_question` 的 `code` 键冲突（第一批引入，`**content` 覆盖了知识点 code）→ Task 13 Step 3(a)
- AI 题没进 JSON 导出/导入快照（第一批引入的数据丢失缺口）→ Task 16

**3. 占位符扫描**：无 TBD；每个 Step 都有可执行代码或命令。

**4. 命名一致性**：`pick_questions` / `reveal(code, type, ref)` / `apply_grade(..., question_ref=)` / `read_ai_question` 的 `pointCode` / 队列 item 的 `questionRef` —— 在 Task 11-17 之间逐处核对过。
