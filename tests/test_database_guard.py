"""护栏：测试进程绝不能绑定真实 data/ 库（2026-09-17 事故后补）。

真实事故：一次手工验证没设 TODO_SQLITE_FILE，对着用户的 data/todo.sqlite3 起了服务，
把测试夹具写进了真实库。这个用例把"测试只能用临时库"变成会被 CI 拦下的硬约束。
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import storage  # noqa: E402


class DatabaseIsolationGuardTests(unittest.TestCase):
    def test_test_process_never_binds_real_database(self) -> None:
        real = (APP_DIR / "data" / "todo.sqlite3").resolve()
        bound = Path(storage.DATABASE_FILE).resolve()
        self.assertNotEqual(bound, real, f"测试进程绑定了真实库：{bound}（真实库必须只读）")

    def test_bound_database_lives_under_tempdir(self) -> None:
        bound = Path(storage.DATABASE_FILE).resolve()
        self.assertTrue(str(bound).startswith(str(Path(tempfile.gettempdir()).resolve())),
                        f"测试库必须位于临时目录，实际：{bound}")

    def test_environment_pins_a_temp_database(self) -> None:
        pinned = os.environ.get("TODO_SQLITE_FILE", "")
        self.assertTrue(pinned, "TODO_SQLITE_FILE 必须由测试包入口/用例显式指定")
        self.assertNotIn(str(APP_DIR / "data"), pinned, f"不能把测试库指向仓库 data/：{pinned}")


if __name__ == "__main__":
    unittest.main()
