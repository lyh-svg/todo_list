"""B10 回归：恢复备份必须"结构化"地拿到三个库的锁，而不是靠 getattr 猜锁名。

`_all_database_locks()` 以前是：

    getattr(module, "_database_lock", None) or getattr(module, "_memo_lock", None) or ...

三个模块恰好各只有一个锁名能被链到，所以"碰巧正确"。任何一个模块改名或新增内部锁，
这里就会静默拿到 None（`if lock is not None` 直接跳过）或拿错别人的锁：恢复期间进来的
memo/summary 写会提交到被 os.replace 换掉的旧 inode 上，静默丢数据，而且**没有任何告警**。

这里断言四件事：
1. 两把锁分别来自 storage.state_lock / memo_storage.memo_lock；
2. 某个模块拿不到锁时必须当场报错，而不是"少挡一把锁"继续跑；
3. 三把锁互不相同（不能被别名成一把）；
4. 真并发：持有这三把锁时，另一个线程写备忘录必须被挡住，释放后立刻完成。
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-backup-locks-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import backup_service  # noqa: E402
import memo_storage  # noqa: E402
import storage  # noqa: E402


class _RecordingLock:
    """只记录进入/退出，不真的加锁（用来断言"确实去拿了这几把锁"）。"""

    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    def __enter__(self) -> "_RecordingLock":
        self.log.append(f"enter:{self.name}")
        return self

    def __exit__(self, *exc_info) -> bool:
        self.log.append(f"exit:{self.name}")
        return False


class BackupDatabaseLockTests(unittest.TestCase):
    def setUp(self) -> None:
        # tests/__init__.py 把三个库钉在共享临时目录上：先清掉备忘录库，计数断言才确定。
        for suffix in ("", "-wal", "-shm"):
            Path(f"{memo_storage.MEMO_DATABASE_FILE}{suffix}").unlink(missing_ok=True)

    def tearDown(self) -> None:
        # 共享临时目录：本模块写过的备忘录库不能留给后面的用例。
        for storage_file in (memo_storage.MEMO_DATABASE_FILE,):
            for suffix in ("", "-wal", "-shm"):
                Path(f"{storage_file}{suffix}").unlink(missing_ok=True)

    def test_acquires_the_two_public_locks(self) -> None:
        log: list[str] = []
        with mock.patch.object(storage, "state_lock", lambda: _RecordingLock("state", log)), \
                mock.patch.object(memo_storage, "memo_lock", lambda: _RecordingLock("memo", log)):
            with backup_service._all_database_locks():
                self.assertEqual(log, ["enter:state", "enter:memo"])
            self.assertEqual(log, ["enter:state", "enter:memo", "exit:memo", "exit:state"])

    def test_missing_lock_fails_loudly_instead_of_skipping(self) -> None:
        """拿不到锁必须炸：少挡一把锁继续恢复 = 静默丢数据。"""
        stripped = types.SimpleNamespace()          # 既没有 _database_lock 也没有 memo_lock
        with mock.patch.object(backup_service, "memo_storage", stripped):
            with self.assertRaises(AttributeError):
                with backup_service._all_database_locks():
                    pass

    def test_the_two_locks_are_distinct(self) -> None:
        locks = (storage.state_lock(), memo_storage.memo_lock())
        self.assertEqual(len({id(lock) for lock in locks}), 2, "两个库不能共用同一把锁")
        self.assertTrue(all(hasattr(lock, "acquire") for lock in locks))

    def test_holding_locks_blocks_concurrent_memo_write(self) -> None:
        """护栏真的挡得住：持锁期间另一个线程的备忘录写入必须卡住。"""
        memo_storage.initialize()
        started = threading.Event()
        finished = threading.Event()

        def writer() -> None:
            started.set()
            memo_storage.write_memo({"title": "并发写入", "content": "内容"})
            finished.set()

        with backup_service._all_database_locks():
            thread = threading.Thread(target=writer, daemon=True)
            thread.start()
            self.assertTrue(started.wait(5), "写入线程没能起来")
            self.assertFalse(finished.wait(0.3), "持锁期间备忘录写入不该完成（护栏失效了）")
        self.assertTrue(finished.wait(5), "锁释放后写入必须立刻完成")
        thread.join(5)
        # initialize() 会在空库上种一条默认备忘录，所以只断言"我们写的那条确实进去了"。
        titles = [entry["title"] for entry in memo_storage.list_memo_summaries()]
        self.assertIn("并发写入", titles)


if __name__ == "__main__":
    unittest.main()
