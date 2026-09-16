"""Standalone SQLite storage for AI knowledge summaries (data/summary.sqlite3)."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
SUMMARY_DATABASE_FILE = Path(
    os.environ.get("TODO_SUMMARY_SQLITE_FILE", str(APP_DIR / "data" / "summary.sqlite3"))
).expanduser()
SUMMARY_SCHEMA_VERSION = 1


class SummarySchemaVersionError(RuntimeError):
    """摘要库 schema 高于本程序支持：拒绝打开，绝不降级。"""
MAX_SUMMARY_CONTENT_BYTES = 1024 * 1024
class _ManagedConnection(sqlite3.Connection):
    """with 块结束时真正关闭连接。

    sqlite3 的上下文管理器只负责提交/回滚，不关闭连接；不关会留下未释放的句柄
    （表现为 ResourceWarning）。这里统一在 __exit__ 里关闭。
    """

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc, tb))
        finally:
            self.close()


_summary_lock = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def open_summary_database() -> sqlite3.Connection:
    SUMMARY_DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        SUMMARY_DATABASE_FILE.parent.chmod(0o700)
    except OSError:
        pass
    connection = sqlite3.connect(SUMMARY_DATABASE_FILE, timeout=10, factory=_ManagedConnection)
    connection.row_factory = sqlite3.Row
    try:
        SUMMARY_DATABASE_FILE.chmod(0o600)
    except OSError:
        pass
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=10000")
    stored_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if stored_version > SUMMARY_SCHEMA_VERSION:
        connection.close()
        raise SummarySchemaVersionError(
            f"摘要库 schema 版本为 {stored_version}，高于本程序支持的 {SUMMARY_SCHEMA_VERSION}；请升级程序"
        )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS summaries (
            summary_id TEXT PRIMARY KEY,
            question_key TEXT NOT NULL UNIQUE,
            question TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_summaries_order
            ON summaries(updated_at DESC, summary_id);
        """
    )
    connection.execute(f"PRAGMA user_version={SUMMARY_SCHEMA_VERSION}")
    return connection


def initialize() -> None:
    with _summary_lock, open_summary_database():
        pass


def question_key_of(question: str) -> str:
    return hashlib.sha256(str(question).strip().encode("utf-8")).hexdigest()


def _row_to_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["summary_id"],
        "question": row["question"],
        "content": row["content"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "revision": int(row["revision"]),
    }


MAX_SUMMARY_LIST = 200
SUMMARY_LIST_CONTENT_CHARS = 2000


def list_summaries(limit: int = MAX_SUMMARY_LIST, offset: int = 0) -> list[dict[str, Any]]:
    """列表：最多 200 条，正文截到 2000 字（单条上限 1 MB，全量返回会很大）。

    需要完整正文时用 read_summary(id)。
    """
    size = max(1, min(MAX_SUMMARY_LIST, int(limit or MAX_SUMMARY_LIST)))
    start = max(0, int(offset or 0))
    with _summary_lock, open_summary_database() as connection:
        rows = connection.execute(
            "SELECT summary_id,question,content,created_at,updated_at,revision "
            "FROM summaries ORDER BY updated_at DESC,summary_id LIMIT ? OFFSET ?",
            (size, start),
        ).fetchall()
    items = []
    for row in rows:
        item = _row_to_summary(row)
        content = str(item.get("content") or "")
        item["contentLength"] = len(content)
        if len(content) > SUMMARY_LIST_CONTENT_CHARS:
            item["content"] = content[:SUMMARY_LIST_CONTENT_CHARS]
            item["contentTruncated"] = True
        items.append(item)
    return items


def count_summaries() -> int:
    with _summary_lock, open_summary_database() as connection:
        return int(connection.execute("SELECT COUNT(*) FROM summaries").fetchone()[0])


def read_summary(summary_id: Any) -> dict[str, Any] | None:
    with _summary_lock, open_summary_database() as connection:
        row = connection.execute(
            "SELECT summary_id,question,content,created_at,updated_at,revision "
            "FROM summaries WHERE summary_id=?",
            (str(summary_id),),
        ).fetchone()
    return _row_to_summary(row) if row else None


def upsert_summary(question: str, content: str) -> dict[str, Any]:
    """同题去重：按 question 哈希决定新建或更新。"""
    question_text = str(question or "").strip()
    if not question_text:
        raise ValueError("题目不能为空")
    content_text = str(content or "").strip()
    if not content_text:
        raise ValueError("摘要内容不能为空")
    if len(content_text.encode("utf-8")) > MAX_SUMMARY_CONTENT_BYTES:
        raise ValueError("单条摘要不能超过 1 MB")
    key = question_key_of(question_text)
    with _summary_lock, open_summary_database() as connection:
        row = connection.execute(
            "SELECT summary_id,revision,created_at FROM summaries WHERE question_key=?",
            (key,),
        ).fetchone()
        now = _now()
        if row:
            summary_id = row["summary_id"]
            connection.execute(
                "UPDATE summaries SET content=?,updated_at=?,revision=? WHERE summary_id=?",
                (content_text, now, int(row["revision"]) + 1, summary_id),
            )
        else:
            summary_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO summaries(summary_id,question_key,question,content,created_at,updated_at,revision) "
                "VALUES(?,?,?,?,?,?,?)",
                (summary_id, key, question_text[:500], content_text, now, now, 1),
            )
        connection.commit()
        row = connection.execute(
            "SELECT summary_id,question,content,created_at,updated_at,revision FROM summaries WHERE summary_id=?",
            (summary_id,),
        ).fetchone()
    return _row_to_summary(row)


def delete_summary(summary_id: Any) -> bool:
    with _summary_lock, open_summary_database() as connection:
        cursor = connection.execute("DELETE FROM summaries WHERE summary_id=?", (str(summary_id),))
        connection.commit()
        return cursor.rowcount > 0


def clear_summaries() -> int:
    with _summary_lock, open_summary_database() as connection:
        cursor = connection.execute("DELETE FROM summaries")
        connection.commit()
        return cursor.rowcount


def checkpoint() -> None:
    with _summary_lock, open_summary_database() as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def database_size() -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{SUMMARY_DATABASE_FILE}{suffix}")
        if path.exists():
            total += path.stat().st_size
    return total


def check_integrity() -> bool:
    try:
        with _summary_lock, open_summary_database() as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
            return bool(result and result[0] == "ok")
    except sqlite3.Error:
        return False
