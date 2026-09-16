"""复习表必须跟着主库一起备份/恢复（复习表在主库 todo.sqlite3 内，同库同文件）。

本文件把"备份 → 破坏 → 恢复 → 内容一致"钉死，覆盖 5 张复习表：
`review_points` / `review_point_tasks` / `review_states` / `review_attempts` / `review_sessions`。

一旦有人把 `create_full_backup` 从"按库文件整体打包"改成"按表清单挑选"而漏掉复习表，
或者把复习表搬到别的库里却没加进 `backup_service.DATABASE_FILES`，下面的用例就会失败。

只用标准库（unittest + zipfile + sqlite3）；所有路径在 import storage 之前指向临时目录，
不触碰 data/ 下的真实数据库。
运行：python3 -m unittest tests.test_review_backup -v
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-review-backup-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "summary.sqlite3")

import backup_service  # noqa: E402  （必须在上面的环境变量之后导入）
import review_storage  # noqa: E402
import storage  # noqa: E402

BACKUP_DIR = Path(backup_service.BACKUP_DIR)
REVIEW_TABLES = ("review_points", "review_point_tasks", "review_states",
                 "review_attempts", "review_sessions")
# 每张表的稳定排序键（即主键）：行序不定会让"内容一致"变成随机假阴性。
ORDER_BY = {
    "review_points": "code",
    "review_point_tasks": "code,task_id,project_id",
    "review_states": "code",
    "review_attempts": "id",
    "review_sessions": "id",
}
CODE = "py.mutability.default-arg"
TODAY = "2026-09-16"


def dump_review_tables() -> dict[str, list[tuple]]:
    """把 5 张复习表按主键排序后原样取出，用于恢复前后的逐行比对。"""
    with storage.open_state_database() as connection:
        return {
            table: [tuple(row) for row in
                    connection.execute(f"SELECT * FROM {table} ORDER BY {ORDER_BY[table]}")]
            for table in REVIEW_TABLES
        }


class ReviewBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertNotEqual(Path(storage.DATABASE_FILE), APP_DIR / "data" / "todo.sqlite3",
                            "测试必须使用临时数据库")
        for path in sorted(Path(_TEMP_DIR.name).glob("todo.sqlite3*")):
            path.unlink(missing_ok=True)
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)

        storage.ensure_schema()
        # 不依赖进程级临时库隔离：同进程 discover 时其他测试模块可能先 import storage、
        # 共用同一个 DATABASE_FILE（仓库既有的测试隔离缺陷），所以这里显式清空 5 张复习表。
        with storage.open_state_database() as connection:
            for table in REVIEW_TABLES:
                connection.execute(f"DELETE FROM {table}")
        review_storage.ensure_content_imported()
        session_id = review_storage.start_session(planned=2)
        review_storage.apply_grade(CODE, "concept", 4, today=TODAY,
                                   answer="往返测试", session_id=session_id)
        review_storage.apply_grade(CODE, "predict", 2, today=TODAY,
                                   answer="第二次作答", session_id=session_id)
        review_storage.finish_session(session_id, answered=2, grade_counts={4: 1, 2: 1},
                                      duration_ms=1234)

        self.before = dump_review_tables()
        # 前置条件：5 张表都得真的有数据，否则"往返后一致"可能只是空表对空表。
        for table in REVIEW_TABLES:
            self.assertTrue(self.before[table], f"{table} 在备份前应当有数据")
        self.before_summary = review_storage.summary(TODAY)
        self.before_state = review_storage.read_state(CODE)
        self.before_history = review_storage.history(CODE)

    def test_backup_round_trip_keeps_all_five_review_tables(self) -> None:
        """核心护栏：整库文件往返后，5 张复习表逐行一致。"""
        name = backup_service.create_full_backup("review-round-trip")
        self.assertTrue(name.endswith(".zip"))

        # 破坏数据：把 5 张表全部清空（模拟"换机/误删/旧库替换"）
        with storage.open_state_database() as connection:
            for table in REVIEW_TABLES:
                connection.execute(f"DELETE FROM {table}")
        wiped = dump_review_tables()
        self.assertEqual({table: len(rows) for table, rows in wiped.items()},
                         {table: 0 for table in REVIEW_TABLES},
                         "清空失败，后面的恢复断言不算数")

        backup_service.restore_full_backup(name)

        self.assertEqual(dump_review_tables(), self.before)
        self.assertEqual(review_storage.summary(TODAY)["total"], self.before_summary["total"])
        self.assertEqual({item["answer"] for item in review_storage.history(CODE)["attempts"]},
                         {"往返测试", "第二次作答"})

    def test_backup_zip_snapshot_already_contains_review_rows(self) -> None:
        """备份文件本身（不是恢复后的库）就得带着复习行：防止备份阶段只挑了部分表。"""
        name = backup_service.create_full_backup("review-zip-content")
        with zipfile.ZipFile(BACKUP_DIR / name) as archive:
            self.assertIn("todo.sqlite3", archive.namelist())
            payload = archive.read("todo.sqlite3")

        extracted = Path(_TEMP_DIR.name) / "extracted-todo.sqlite3"
        extracted.write_bytes(payload)
        with closing(sqlite3.connect(extracted)) as connection:
            counts = {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                      for table in REVIEW_TABLES}
            answers = {str(row[0]) for row in
                       connection.execute("SELECT answer FROM review_attempts")}
        self.assertEqual(counts, {table: len(rows) for table, rows in self.before.items()})
        self.assertEqual(answers, {"往返测试", "第二次作答"})

    def test_restore_keeps_schedule_and_attempt_payload(self) -> None:
        """语义护栏：调度状态与作答正文（不是行数）也逐字段还原。"""
        name = backup_service.create_full_backup("review-schedule")
        with storage.open_state_database() as connection:
            connection.execute("DELETE FROM review_attempts")
            connection.execute(
                "UPDATE review_states SET due='',interval_days=0,streak=0,lapses=0,"
                "last_grade=0,weak=0,last_reviewed_at=''")

        backup_service.restore_full_backup(name)

        self.assertEqual(review_storage.read_state(CODE), self.before_state)
        after_history = review_storage.history(CODE)
        self.assertEqual(after_history["state"], self.before_history["state"])
        self.assertEqual(sorted(item["answer"] for item in after_history["attempts"]),
                         sorted(item["answer"] for item in self.before_history["attempts"]))
        self.assertEqual(after_history["attempts"][0]["reviewedOn"], TODAY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
