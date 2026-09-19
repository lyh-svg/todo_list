"""P2 回归：每次开库都重放全部 DDL + 同一请求内反复开连接。

实测（修复前）：一次 open_state_database() 要执行 39 条语句（29 条 CREATE + 2 次
PRAGMA table_info）、3 次 chmod/mkdir，耗时约 494 µs；而 GET /api/trash 一条请求
内部会开 4 次连接（purge → read_app_settings → purge 自身 → list 自身 + read_app_settings）。

这里断言的都是**语句条数 / 调用次数**（确定性），不是耗时——耗时随机器波动。
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-open-overhead-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import memo_storage  # noqa: E402
import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"

# 审计钩子只能加不能删，所以装一次、用开关控制是否计数。
_AUDIT = {"on": False, "chmod": 0, "mkdir": 0}


def _audit_hook(event: str, _args: tuple) -> None:
    if not _AUDIT["on"]:
        return
    if event == "os.chmod":
        _AUDIT["chmod"] += 1
    elif event == "os.mkdir":
        _AUDIT["mkdir"] += 1


sys.addaudithook(_audit_hook)


@contextmanager
def counted_audit():
    _AUDIT.update(on=True, chmod=0, mkdir=0)
    try:
        yield _AUDIT
    finally:
        _AUDIT["on"] = False


@contextmanager
def counted_statements(module):
    """把某个存储模块的连接工厂换成会记录语句的子类。"""
    sink: list[str] = []
    base = module._ManagedConnection

    class CountingConnection(base):
        def execute(self, sql, *args, **kwargs):
            sink.append(" ".join(str(sql).split())[:32].upper())
            return super().execute(sql, *args, **kwargs)

        def executescript(self, script, *args, **kwargs):
            for piece in str(script).split(";"):
                piece = piece.strip()
                if piece:
                    sink.append(" ".join(piece.split())[:32].upper())
            return super().executescript(script, *args, **kwargs)

    module._ManagedConnection = CountingConnection
    try:
        yield sink
    finally:
        module._ManagedConnection = base


@contextmanager
def counted_opens():
    """数 storage.open_state_database() 被调用了几次（review_storage 也走它）。"""
    original = storage.open_state_database
    counter = [0]

    def counted():
        counter[0] += 1
        return original()

    storage.open_state_database = counted
    try:
        yield counter
    finally:
        storage.open_state_database = original


def ddl_count(statements: list[str]) -> int:
    return sum(1 for statement in statements
               if statement.startswith(("CREATE", "ALTER", "PRAGMA TABLE_INFO")))


def reset_storage_database() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
    storage.ensure_schema()


def scalar(query: str) -> object:
    # closing() 只负责关连接，第二个 connection 上下文负责提交（原来的 with sqlite3.connect(X) 只提交、不关闭）
    with closing(sqlite3.connect(storage.DATABASE_FILE)) as connection, connection:
        return connection.execute(query).fetchone()[0]


def table_names() -> set[str]:
    with closing(sqlite3.connect(storage.DATABASE_FILE)) as connection, connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


class BootstrapCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_storage_database()

    def test_repeated_opens_do_not_replay_ddl(self) -> None:
        """第一次开过库之后，后续每次 open 都不该再重放 CREATE/table_info。"""
        storage.open_state_database().close()          # 预热（这一次允许 bootstrap）
        with counted_statements(storage) as statements:
            for _ in range(5):
                storage.open_state_database().close()
        replay = [s for s in statements if ddl_count([s])]
        self.assertEqual(
            replay, [],
            f"5 次 open 里重放了 {len(replay)} 条 DDL：{replay[:5]}",
        )
        # 版本守卫每次都要跑（这是安全底线，不能省）
        self.assertEqual(sum(1 for s in statements if s.startswith("PRAGMA USER_VERSION")), 5)

    def test_repeated_opens_do_not_chmod(self) -> None:
        """chmod 只在真正 bootstrap 时做，不再每个请求 2 次。"""
        storage.open_state_database().close()
        with counted_audit() as audit:
            for _ in range(5):
                storage.open_state_database().close()
        self.assertEqual(audit["chmod"], 0, "热路径不该再 chmod")
        with counted_audit() as audit:
            reset_storage_database()
        self.assertGreaterEqual(audit["chmod"], 1, "bootstrap 时必须把权限收紧")

    def test_fast_path_keeps_per_connection_pragmas(self) -> None:
        """省掉的只能是持久化/一次性的东西；连接级 PRAGMA 一个都不能少。"""
        storage.open_state_database().close()
        with storage.open_state_database() as connection:
            self.assertEqual(int(connection.execute("PRAGMA foreign_keys").fetchone()[0]), 1)
            self.assertEqual(int(connection.execute("PRAGMA busy_timeout").fetchone()[0]), 10000)
            self.assertEqual(int(connection.execute("PRAGMA synchronous").fetchone()[0]), 1)
            self.assertEqual(int(connection.execute("PRAGMA wal_autocheckpoint").fetchone()[0]), 1000)
            self.assertEqual(str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(), "wal")

    def test_deleted_and_recreated_file_is_bootstrapped_again(self) -> None:
        """测试/运维都会删库重建：新文件必须重新建表，不能因为缓存跳过。"""
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        with counted_statements(storage) as statements:
            storage.open_state_database().close()
        self.assertGreaterEqual(ddl_count(statements), 15, "新建的空库必须重放 DDL")
        self.assertIn("projects", table_names())
        self.assertIn("nodes", table_names())

    def test_replaced_file_is_bootstrapped_again(self) -> None:
        """恢复/导入是 os.replace 换文件：inode 变了就必须重新 bootstrap。"""
        storage.open_state_database().close()          # 预热缓存
        replacement = Path(_TEMP_DIR.name) / "replacement.sqlite3"
        for suffix in ("", "-wal", "-shm"):
            Path(f"{replacement}{suffix}").unlink(missing_ok=True)
        sqlite3.connect(replacement).close()           # 一个没有 schema 的空库
        os.replace(replacement, storage.DATABASE_FILE)
        with counted_statements(storage) as statements:
            storage.open_state_database().close()
        self.assertGreaterEqual(ddl_count(statements), 15)
        self.assertIn("projects", table_names())

    def test_replaced_non_wal_file_gets_wal_back(self) -> None:
        """持久化的 journal_mode 也只在 bootstrap 时设置，所以换文件后必须补上。"""
        storage.open_state_database().close()
        replacement = Path(_TEMP_DIR.name) / "rollback.sqlite3"
        for suffix in ("", "-wal", "-shm"):
            Path(f"{replacement}{suffix}").unlink(missing_ok=True)
        connection = sqlite3.connect(replacement)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.close()
        os.replace(replacement, storage.DATABASE_FILE)
        with storage.open_state_database() as connection:
            self.assertEqual(str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(), "wal")

    def test_version_guard_still_rejects_future_database_with_warm_cache(self) -> None:
        """缓存不能把版本守卫短路掉：更高版本的库照旧拒绝，且不许改它的文件头。"""
        storage.open_state_database().close()
        future = storage.SCHEMA_VERSION + 1
        connection = sqlite3.connect(storage.DATABASE_FILE)
        connection.execute(f"PRAGMA user_version={future}")
        connection.close()
        with self.assertRaises(storage.SchemaVersionError):
            storage.open_state_database()
        self.assertEqual(scalar("PRAGMA user_version"), future, "拒绝打开时不能降级写版本号")

    def test_ensure_schema_and_writes_still_work_after_fast_path(self) -> None:
        """热路径开出来的连接必须能正常读写（外键级联也要还在）。"""
        storage.ensure_schema()
        storage.open_state_database().close()
        project = {
            "id": "p1", "name": "热路径", "description": "", "createdAt": TODAY,
            "assessmentEnabled": False, "reviewEnabled": False, "tree": [{
                "id": "p1-w", "type": "week", "text": "第1周", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": [],
            }],
        }
        revision, _summary = storage.write_project(project, None)
        self.assertEqual(revision, 1)
        self.assertEqual(storage.read_project("p1")[0]["name"], "热路径")


class ConnectionReuseTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_storage_database()
        storage.store_trash_item("node", "p1", "被删的任务", {"id": "gone", "type": "item", "text": "x"})

    def test_list_trash_items_opens_one_connection(self) -> None:
        """回收站接口以前一条请求开 4 次连接（每开一次都重放一遍 DDL）。"""
        with counted_opens() as opens:
            items = storage.list_trash_items()
        self.assertEqual(opens[0], 1, f"list_trash_items 开了 {opens[0]} 次连接")
        self.assertEqual(len(items), 1)

    def test_review_summary_opens_one_connection(self) -> None:
        with counted_opens() as opens:
            review_storage.summary(TODAY)
        self.assertEqual(opens[0], 1, f"review_storage.summary 开了 {opens[0]} 次连接")


class MemoBootstrapTests(unittest.TestCase):
    def test_memo_repeated_opens_do_not_replay_ddl(self) -> None:
        memo_storage.initialize()
        with counted_statements(memo_storage) as statements:
            for _ in range(5):
                memo_storage.open_memo_database().close()
        replay = [s for s in statements if ddl_count([s])]
        self.assertEqual(replay, [], f"memo 库重放了 DDL：{replay[:5]}")

    def test_memo_recreated_file_is_bootstrapped_again(self) -> None:
        memo_storage.initialize()
        for suffix in ("", "-wal", "-shm"):
            Path(f"{memo_storage.MEMO_DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        with counted_statements(memo_storage) as statements:
            memo_storage.open_memo_database().close()
        self.assertGreaterEqual(ddl_count(statements), 1, "删库重建后要重新建表")


class ConnectionCleanupTests(unittest.TestCase):
    """建好连接之后、返回之前抛异常时，open_*_database() 必须自己把连接关掉。

    恢复一个"非 SQLite 文件"的坏备份会走这条路：调用方根本拿不到连接对象，
    句柄只能留到 GC（发 ResourceWarning；Windows 上还会挡住随后的文件替换）。
    """

    def _track_connections(self, module) -> list:
        created = []
        managed = module._ManagedConnection

        class Tracked(managed):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.closed = False
                created.append(self)

            def close(self):
                self.closed = True
                super().close()

        self.addCleanup(lambda: setattr(module, "_ManagedConnection", managed))
        module._ManagedConnection = Tracked
        return created

    def test_bad_state_database_file_closes_the_connection(self) -> None:
        created = self._track_connections(storage)
        broken = Path(_TEMP_DIR.name) / "broken-todo.sqlite3"
        broken.write_bytes(b"this-is-not-a-sqlite-file")
        with mock.patch.object(storage, "DATABASE_FILE", broken):
            with self.assertRaises(sqlite3.DatabaseError):
                storage.open_state_database()
        self.assertTrue(created, "这个用例必须真的建立过连接")
        self.assertTrue(all(connection.closed for connection in created),
                        "异常路径把连接留着没关，句柄一直要等到 GC")

    def test_bad_memo_database_file_closes_the_connection(self) -> None:
        created = self._track_connections(memo_storage)
        broken = Path(_TEMP_DIR.name) / "broken-memo.sqlite3"
        broken.write_bytes(b"this-is-not-a-sqlite-file")
        with mock.patch.object(memo_storage, "MEMO_DATABASE_FILE", broken):
            with self.assertRaises(sqlite3.DatabaseError):
                memo_storage.open_memo_database()
        self.assertTrue(created, "这个用例必须真的建立过连接")
        self.assertTrue(all(connection.closed for connection in created),
                        "异常路径把连接留着没关，句柄一直要等到 GC")


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
