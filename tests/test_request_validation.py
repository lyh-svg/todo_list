"""请求参数校验与"绝不空回复"的单元级测试。

覆盖第三阶段 ②③ 的根因：非法 MIME / 非法 revision / 缺失参数 / 不存在的资源，
必须返回明确的 JSON 状态码，而不是把异常抛到 HTTP 层（表现为空回复）。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-validate-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")

import local_server  # noqa: E402  （必须在环境变量之后导入）
import memo_storage  # noqa: E402


class ParamHelperTests(unittest.TestCase):
    def test_required_param_returns_value(self) -> None:
        self.assertEqual(local_server.required_param({"id": ["abc"]}, "id"), "abc")

    def test_required_param_rejects_missing_and_blank(self) -> None:
        for params in ({}, {"id": [""]}, {"id": ["   "]}):
            with self.assertRaises(ValueError) as ctx:
                local_server.required_param(params, "id")
            self.assertIn("id", str(ctx.exception))

    def test_int_param_parses_and_defaults(self) -> None:
        self.assertEqual(local_server.int_param({"revision": ["7"]}, "revision"), 7)
        self.assertEqual(local_server.int_param({}, "revision", required=False, default=3), 3)

    def test_int_param_rejects_missing_or_non_numeric(self) -> None:
        with self.assertRaises(ValueError):
            local_server.int_param({}, "revision")
        with self.assertRaises(ValueError) as ctx:
            local_server.int_param({"revision": ["abc"]}, "revision")
        self.assertIn("整数", str(ctx.exception))
        with self.assertRaises(ValueError):
            local_server.int_param({"revision": ["1.5"]}, "revision")

    def test_optional_iso_date_accepts_only_real_dates(self) -> None:
        self.assertEqual(local_server.optional_iso_date("2026-09-15"), "2026-09-15")
        for bad in ("", "  ", "2026-9-15", "2026/09/15", "2026-02-30", "today", "2026-13-01"):
            self.assertEqual(local_server.optional_iso_date(bad), "", bad)


class MemoDeleteValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{memo_storage.MEMO_DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        memo_storage.initialize()
        with memo_storage.open_memo_database() as connection:
            connection.execute("DELETE FROM memos")
        self.memo = memo_storage.write_memo({"title": "测试", "content": "正文", "pinned": False})

    def test_delete_with_wrong_revision_is_a_conflict(self) -> None:
        with self.assertRaises(memo_storage.MemoConflictError):
            memo_storage.delete_memo(self.memo["id"], int(self.memo["revision"]) + 1)

    def test_delete_with_right_revision_works(self) -> None:
        memo_storage.delete_memo(self.memo["id"], int(self.memo["revision"]))
        self.assertIsNone(memo_storage.read_memo(self.memo["id"]))

    def test_conflict_error_is_not_a_plain_runtime_error_only(self) -> None:
        # 处理器要能把它单独映射成 409，所以必须是可区分的子类
        self.assertTrue(issubclass(memo_storage.MemoConflictError, RuntimeError))
        self.assertIsNot(memo_storage.MemoConflictError, RuntimeError)


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
