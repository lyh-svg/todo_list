"""P6 回归：复习计数一条 GROUP BY 出结果，且与旧的逐行 Python 分桶逐字段一致。

旧的 review_counts() 把"已完成 + 排了复习"的每一行都取回 Python 再逐行分桶：
30 个项目 × 1 万任务（306,823 节点 / 75,000 条待复习）实测 94.75 ms，而它只是给
项目卡片上的徽标算两个数字。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-review-counts-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import storage  # noqa: E402

TODAY = "2026-09-19"


def reference_review_counts(today: str) -> dict[str, dict[str, int]]:
    """旧实现的逐行拷贝：取回所有符合条件的行，在 Python 里分桶。

    用它当"标准答案"，保证 GROUP BY 版本没有偷偷改掉口径
    （包括"只有未来复习的项目也要出现，且两个计数都是 0"这种边角）。
    """
    with storage.open_state_database() as connection:
        rows = connection.execute(
            "SELECT project_id,review_due FROM nodes "
            "WHERE type='item' AND completed=1 AND review_due<>''"
        ).fetchall()
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        due = str(row["review_due"])
        bucket = result.setdefault(str(row["project_id"]), {"today": 0, "overdue": 0})
        if due < today:
            bucket["overdue"] += 1
        elif due == today:
            bucket["today"] += 1
    return result


class CountingConnection(storage._ManagedConnection):
    statements: list[str] = []

    def execute(self, sql, *args, **kwargs):
        CountingConnection.statements.append(" ".join(str(sql).split()))
        return super().execute(sql, *args, **kwargs)


def item(node_id: str, *, completed: bool = True, review_due: str = "", optional: bool = False) -> dict:
    node = {"id": node_id, "type": "item", "text": f"任务 {node_id}", "completed": completed,
            "completedAt": f"{TODAY}T09:00:00" if completed else None, "optional": optional,
            "assessmentRequired": False, "assessmentHistory": 0, "createdAt": TODAY, "children": []}
    if review_due:
        node["review"] = {"due": review_due, "learning": False, "log": []}
    return node


def project(project_id: str, items: list, *, archived: bool = False) -> dict:
    return {
        "id": project_id, "name": f"项目 {project_id}", "description": "", "createdAt": TODAY,
        "assessmentEnabled": False, "reviewEnabled": True, "archived": archived,
        "tree": [{"id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
                  "expanded": False, "createdAt": TODAY, "children": [
                      {"id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                       "expanded": False, "createdAt": TODAY, "children": items}]}],
    }


class ReviewCountsTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        storage.ensure_schema()
        storage.write_project(project("p1", [
            item("a", review_due="2026-09-01"),   # 逾期
            item("b", review_due=TODAY),          # 今天
            item("c", review_due="2026-12-31"),   # 未来：这个项目会有 {0,0}
            item("d", completed=False, review_due=TODAY),   # 未完成：不计
            item("e", review_due=""),                        # 没排复习：不计
        ]), None)
        storage.write_project(project("p2", [
            item("f", review_due="2026-01-01"),
            item("g", review_due="2026-01-02"),
        ], archived=True), None)
        storage.write_project(project("p3", [
            item("h", completed=False),          # 一条都不符合：这个项目**不该出现**在结果里
        ]), None)
        storage.write_project(project("p4", [
            item("i", review_due="2027-06-01"),  # 只有未来复习：出现，但两个计数都是 0
        ]), None)

    def test_matches_reference_implementation(self) -> None:
        expected = reference_review_counts(TODAY)
        actual = storage.review_counts(TODAY)
        self.assertEqual(set(actual), set(expected), "返回的项目集合必须与旧实现一致")
        for project_id, bucket in expected.items():
            self.assertEqual(actual[project_id], bucket, project_id)
        self.assertEqual(actual["p1"], {"today": 1, "overdue": 1})
        self.assertEqual(actual["p2"], {"today": 0, "overdue": 2})
        self.assertNotIn("p3", actual, "一条都不符合的项目不该出现在计数里")
        self.assertEqual(actual["p4"], {"today": 0, "overdue": 0}, "有行但只落在未来也要出现（旧口径）")

    def test_reference_and_actual_agree_across_dates(self) -> None:
        for today in ("2026-01-01", "2026-01-02", "2026-09-01", TODAY, "2026-12-31", "2027-01-01"):
            self.assertEqual(storage.review_counts(today), reference_review_counts(today), today)

    def test_uses_one_group_by_query(self) -> None:
        original = storage._ManagedConnection
        storage._ManagedConnection = CountingConnection
        CountingConnection.statements = []
        try:
            counts = storage.review_counts(TODAY)
        finally:
            storage._ManagedConnection = original
        selects = [sql for sql in CountingConnection.statements if sql.upper().startswith("SELECT")]
        self.assertEqual(len(selects), 1, f"应该只查一次，实际：{selects}")
        self.assertIn("GROUP BY PROJECT_ID", selects[0].upper(), selects[0])
        self.assertEqual(counts["p1"], {"today": 1, "overdue": 1})

    def test_many_review_rows_stay_cheap(self) -> None:
        """2000 条待复习行：GROUP BY 版本只回"每个项目一行"。"""
        items = [item(f"bulk{i}", review_due="2026-09-01" if i % 2 else TODAY) for i in range(2000)]
        storage.write_project(project("bulk", items), None)
        original = storage._ManagedConnection
        storage._ManagedConnection = CountingConnection
        CountingConnection.statements = []
        try:
            counts = storage.review_counts(TODAY)
        finally:
            storage._ManagedConnection = original
        self.assertEqual(counts["bulk"], {"today": 1000, "overdue": 1000})
        self.assertEqual(len([sql for sql in CountingConnection.statements
                              if sql.upper().startswith("SELECT")]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
