"""Standalone SQLite storage for portable memos."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


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


_memo_lock = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_text(value: Any, fallback: str = "") -> str:
    return str(value if value is not None else fallback).strip()


def open_memo_database() -> sqlite3.Connection:
    MEMO_DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        MEMO_DATABASE_FILE.parent.chmod(0o700)
    except OSError:
        pass
    connection = sqlite3.connect(MEMO_DATABASE_FILE, timeout=10, factory=_ManagedConnection)
    connection.row_factory = sqlite3.Row
    try:
        MEMO_DATABASE_FILE.chmod(0o600)
    except OSError:
        pass
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=10000")
    stored_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if stored_version > MEMO_SCHEMA_VERSION:
        connection.close()
        raise MemoSchemaVersionError(
            f"备忘录库 schema 版本为 {stored_version}，高于本程序支持的 {MEMO_SCHEMA_VERSION}；请升级程序"
        )
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
    return connection


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


def export_database(target: Path) -> None:
    checkpoint()
    target.parent.mkdir(parents=True, exist_ok=True)
    with _memo_lock, sqlite3.connect(MEMO_DATABASE_FILE) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    target.chmod(0o600)


def import_database(payload: bytes) -> None:
    if not payload:
        raise ValueError("备忘录数据库文件为空")
    if len(payload) > 110 * 1024 * 1024:
        raise ValueError("备忘录数据库文件不能超过 110 MB")
    parent = MEMO_DATABASE_FILE.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="memo-import-", suffix=".sqlite3", dir=parent, delete=False) as temporary:
            temporary.write(payload)
            temp_path = Path(temporary.name)
        if not check_integrity(temp_path):
            raise ValueError("备忘录数据库完整性检查失败")
        with sqlite3.connect(temp_path) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "memos" not in tables:
                raise ValueError("不是有效的备忘录数据库")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(memos)")}
            required = {"memo_id", "title", "content", "pinned", "created_at", "updated_at", "revision"}
            if not required.issubset(columns):
                raise ValueError("备忘录数据库结构不完整")
        with _memo_lock:
            checkpoint()
            for suffix in ("-wal", "-shm"):
                Path(f"{MEMO_DATABASE_FILE}{suffix}").unlink(missing_ok=True)
            os.replace(temp_path, MEMO_DATABASE_FILE)
            temp_path = None
            initialize()
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


def database_size() -> int:
    return sum(Path(f"{MEMO_DATABASE_FILE}{suffix}").stat().st_size
               for suffix in ("", "-wal", "-shm") if Path(f"{MEMO_DATABASE_FILE}{suffix}").exists())
