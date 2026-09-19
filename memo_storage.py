"""Standalone SQLite storage for portable memos."""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from db_support import ManagedConnection as _ManagedConnection, now_iso as _now


APP_DIR = Path(__file__).resolve().parent
MEMO_DATABASE_FILE = Path(
    os.environ.get("TODO_MEMO_SQLITE_FILE", str(APP_DIR / "data" / "memo.sqlite3"))
).expanduser()
MEMO_SCHEMA_VERSION = 1
MAX_MEMO_CONTENT_BYTES = 50 * 1024 * 1024
# 列表只回传前这么多字符做预览，全文由 GET /api/memo?id= 按需加载。
MEMO_PREVIEW_CHARS = 200


class MemoConflictError(RuntimeError):
    """备忘录版本冲突：另一个页面已经改过它。"""


class MemoSchemaVersionError(RuntimeError):
    """备忘录库 schema 高于本程序支持：拒绝打开，绝不降级。"""


_memo_lock = threading.RLock()


def memo_lock() -> threading.RLock:
    """给其他模块用的公开锁入口（对齐 storage.state_lock 的先例）。

    备份恢复要整文件替换备忘录库，必须能明确拿到这把锁；以前靠 backup_service 用
    getattr 链去猜锁名，改名就会静默拿不到锁。
    """
    return _memo_lock


def _safe_text(value: Any, fallback: str = "") -> str:
    return str(value if value is not None else fallback).strip()


_memo_schema_ready: dict[str, tuple[tuple[int, int], int]] = {}
_memo_schema_ready_lock = threading.Lock()


def _memo_file_signature() -> tuple[int, int]:
    """库文件身份 = (设备号, inode)；整库导入是 os.replace 换文件，inode 会变。"""
    try:
        stat_result = MEMO_DATABASE_FILE.stat()
    except OSError:
        return (-1, -1)
    return (stat_result.st_dev, stat_result.st_ino)


def open_memo_database() -> sqlite3.Connection:
    """打开备忘录库；连接级 PRAGMA 与版本守卫每次都做，幂等 DDL 只在首次见到该文件时重放。

    缓存键是 (inode, 打开时读到的版本)：整库导入换掉文件、删库重建、版本变化都会重新建表。
    """
    MEMO_DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(MEMO_DATABASE_FILE, timeout=10, factory=_ManagedConnection)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        stored_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if stored_version > MEMO_SCHEMA_VERSION:
            raise MemoSchemaVersionError(
                f"备忘录库 schema 版本为 {stored_version}，高于本程序支持的 {MEMO_SCHEMA_VERSION}；请升级程序"
            )
        signature = _memo_file_signature()
        with _memo_schema_ready_lock:
            ready = _memo_schema_ready.get(str(MEMO_DATABASE_FILE)) == (signature, stored_version)
        if not ready:
            try:
                MEMO_DATABASE_FILE.parent.chmod(0o700)
            except OSError:
                pass
            try:
                MEMO_DATABASE_FILE.chmod(0o600)
            except OSError:
                pass
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memos (
                    memo_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_memos_order
                    ON memos(pinned DESC, updated_at DESC, memo_id);
                """
            )
            connection.execute(f"PRAGMA user_version={MEMO_SCHEMA_VERSION}")
            with _memo_schema_ready_lock:
                _memo_schema_ready[str(MEMO_DATABASE_FILE)] = (
                    signature, int(connection.execute("PRAGMA user_version").fetchone()[0]))
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection
    except BaseException:
        # 与 storage.open_state_database 同样的道理：建好连接之后、返回之前抛异常时，
        # 调用方拿不到连接对象，必须在这里自己关掉（坏库文件 / 版本不符 / 建表失败）。
        connection.close()
        raise


def initialize() -> None:
    with _memo_lock, open_memo_database() as connection:
        if connection.execute("SELECT 1 FROM memos LIMIT 1").fetchone() is None:
            now = _now()
            connection.execute(
                "INSERT INTO memos(memo_id,title,content,pinned,created_at,updated_at,revision) "
                "VALUES(?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), "未命名备忘录", "", 0, now, now, 1),
            )


MAX_MEMO_LIST = 200


def list_memo_summaries(limit: int = MAX_MEMO_LIST, offset: int = 0) -> list[dict[str, Any]]:
    """列表用数据：只给预览（前 MEMO_PREVIEW_CHARS 字）与长度，绝不带全文。

    默认最多 200 条（配合 total 给出"显示前 N 条"），避免几千条备忘录一次全传。
    """
    return _summary_rows(limit=limit, offset=offset)


def search_memo_summaries(query: str, limit: int = MAX_MEMO_LIST, offset: int = 0) -> list[dict[str, Any]]:
    """按标题或**全文**搜索，同样只返回预览。

    LIKE 的 % 和 _ 必须转义：否则搜一个 "%" 会命中所有备忘录。
    """
    text = str(query or "").strip()
    if not text:
        return _summary_rows(limit=limit, offset=offset)
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return _summary_rows(
        "WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'",
        (pattern, pattern), limit=limit, offset=offset,
    )


def count_memos(query: str = "") -> int:
    """列表/搜索的总条数（前端用来显示"共 N 条，显示前 M 条"）。"""
    text = str(query or "").strip()
    with _memo_lock, open_memo_database() as connection:
        if not text:
            return int(connection.execute("SELECT COUNT(*) FROM memos").fetchone()[0])
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        return int(connection.execute(
            "SELECT COUNT(*) FROM memos WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'",
            (pattern, pattern)).fetchone()[0])


def read_memo(memo_id: Any) -> dict[str, Any] | None:
    with _memo_lock, open_memo_database() as connection:
        row = connection.execute(
            "SELECT memo_id,title,content,pinned,created_at,updated_at,revision FROM memos WHERE memo_id=?",
            (str(memo_id),),
        ).fetchone()
    return _row_to_memo(row) if row else None


def _row_to_memo(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["memo_id"],
        "title": row["title"],
        "content": row["content"],
        "pinned": bool(row["pinned"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "revision": int(row["revision"]),
    }


def _row_to_summary(row: sqlite3.Row) -> dict[str, Any]:
    content = row["content"] or ""
    return {
        "id": row["memo_id"],
        "title": row["title"],
        "contentPreview": content[:MEMO_PREVIEW_CHARS],
        "contentLength": len(content),
        "pinned": bool(row["pinned"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "revision": int(row["revision"]),
    }


def _summary_rows(where: str = "", params: tuple[Any, ...] = (),
                  limit: int = MAX_MEMO_LIST, offset: int = 0) -> list[dict[str, Any]]:
    size = max(1, min(MAX_MEMO_LIST, int(limit or MAX_MEMO_LIST)))
    start = max(0, int(offset or 0))
    with _memo_lock, open_memo_database() as connection:
        rows = connection.execute(
            "SELECT memo_id,title,content,pinned,created_at,updated_at,revision FROM memos "
            f"{where} ORDER BY pinned DESC,updated_at DESC,memo_id LIMIT ? OFFSET ?",
            (*params, size, start),
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def write_memo(payload: dict[str, Any]) -> dict[str, Any]:
    memo_id = _safe_text(payload.get("id")) or str(uuid.uuid4())
    title = _safe_text(payload.get("title"), "未命名备忘录") or "未命名备忘录"
    content = str(payload.get("content") or "")
    if len(content.encode("utf-8")) > MAX_MEMO_CONTENT_BYTES:
        raise ValueError("单条备忘录不能超过 50 MB")
    pinned = int(bool(payload.get("pinned")))
    expected = payload.get("expectedRevision")
    if expected is not None:
        try:
            expected = int(expected)
        except (TypeError, ValueError):
            raise ValueError("expectedRevision 格式不正确") from None
    with _memo_lock, open_memo_database() as connection:
        row = connection.execute(
            "SELECT revision,created_at FROM memos WHERE memo_id=?", (memo_id,)
        ).fetchone()
        if row:
            current_revision = int(row["revision"])
            if expected != current_revision:
                raise MemoConflictError(f"备忘录已被其他页面更新（当前版本 {current_revision}）")
            revision = current_revision + 1
            created_at = row["created_at"]
        else:
            if expected not in (None, 0):
                raise RuntimeError("备忘录不存在或已被删除")
            revision = 1
            created_at = _now()
        updated_at = _now()
        connection.execute(
            """INSERT INTO memos(memo_id,title,content,pinned,created_at,updated_at,revision)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(memo_id) DO UPDATE SET title=excluded.title,content=excluded.content,
                pinned=excluded.pinned,updated_at=excluded.updated_at,revision=excluded.revision""",
            (memo_id, title, content, pinned, created_at, updated_at, revision),
        )
        row = connection.execute(
            "SELECT memo_id,title,content,pinned,created_at,updated_at,revision FROM memos WHERE memo_id=?",
            (memo_id,),
        ).fetchone()
    return _row_to_memo(row)


def delete_memo(memo_id: Any, expected_revision: int) -> None:
    with _memo_lock, open_memo_database() as connection:
        row = connection.execute("SELECT revision FROM memos WHERE memo_id=?", (str(memo_id),)).fetchone()
        if not row or int(row["revision"]) != int(expected_revision):
            raise MemoConflictError("备忘录已被修改或不存在")
        connection.execute("DELETE FROM memos WHERE memo_id=?", (str(memo_id),))
        if connection.execute("SELECT 1 FROM memos LIMIT 1").fetchone() is None:
            now = _now()
            connection.execute(
                "INSERT INTO memos(memo_id,title,content,pinned,created_at,updated_at,revision) VALUES(?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), "未命名备忘录", "", 0, now, now, 1),
            )


def checkpoint() -> None:
    with _memo_lock, open_memo_database() as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def check_integrity(path: Path | None = None) -> bool:
    target = path or MEMO_DATABASE_FILE
    if not target.exists():
        return True
    try:
        with sqlite3.connect(target, timeout=10) as connection:
            return connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        return False


def database_size() -> int:
    return sum(Path(f"{MEMO_DATABASE_FILE}{suffix}").stat().st_size
               for suffix in ("", "-wal", "-shm") if Path(f"{MEMO_DATABASE_FILE}{suffix}").exists())
