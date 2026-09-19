#!/usr/bin/env python3
"""SQLite persistence, migration, backup, and recovery for the todo app."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
DATABASE_FILE = Path(
    os.environ.get("TODO_SQLITE_FILE", str(APP_DIR / "data" / "todo.sqlite3"))
).expanduser()
BACKUP_DIR = Path(
    os.environ.get("TODO_SQLITE_BACKUP_DIR", str(DATABASE_FILE.parent / "backups"))
).expanduser()
MAX_PROJECT_PAYLOAD_BYTES = 50 * 1024 * 1024
TRASH_RETENTION_DAYS = 7
# 应用级设置（存在 app_state 的 'settings' 键里，可被前端改）
DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "trashRetentionDays": TRASH_RETENTION_DAYS,   # 回收站保留天数 1~365
    "autoArchiveEnabled": False,                  # 是否自动归档"全部完成且很久没动"的项目
    "autoArchiveDays": 30,                        # 多久没动算"很久" 1~3650
    "reviewDailyLimit": 10,                       # 每日复习上限 5~15
    "reviewNewPerDay": 2,                         # 每日新知识点名额 0~5
}
MIN_TRASH_RETENTION_DAYS = 1
MAX_TRASH_RETENTION_DAYS = 365
MAX_AUTO_ARCHIVE_DAYS = 3650
ORPHAN_BOX_TITLE = "孤立任务箱"                    # 父节点被删掉时，恢复到这里
ACTIVITY_LIMIT_MAX = 500
SCHEMA_VERSION = 8
# 任务元数据（第 1~6 项日常功能）：优先级、截止日期、标签、预计耗时、备注、链接
PRIORITIES = ("", "high", "mid", "low")
MAX_TAGS = 20
MAX_TAG_CHARS = 40
MAX_NOTE_CHARS = 20000
MAX_LINKS = 20
MAX_LINK_CHARS = 2000
MAX_ESTIMATE_MINUTES = 60 * 24 * 30
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 导出 JSON 的 schema 版本。必须与前端 js/app.js 的 DATA_SCHEMA_VERSION 同步：
# 前端 extractProjects() 会拒绝比自己更新的 schemaVersion。
EXPORT_SCHEMA_VERSION = 2

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


_database_lock = threading.RLock()


def state_lock() -> threading.RLock:
    """给其他模块用的公开锁入口（复习答题写入与项目保存共用同一把闸）。"""
    return _database_lock


class StateConflictError(RuntimeError):
    pass


class SchemaVersionError(RuntimeError):
    """数据库 schema 版本高于本程序支持的版本：必须拒绝打开，绝不降级。"""


def clean_priority(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in PRIORITIES else ""


def clean_due_date(value: Any) -> str:
    text = str(value or "").strip()[:10]
    if not ISO_DATE_RE.match(text):
        return ""
    try:
        date.fromisoformat(text)
    except ValueError:
        return ""
    return text


def clean_estimate_minutes(value: Any) -> int:
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_ESTIMATE_MINUTES, minutes))


def clean_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        tag = str(item or "").strip()[:MAX_TAG_CHARS]
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) >= MAX_TAGS:
            break
    return tags


def clean_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    links: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()[:MAX_LINK_CHARS]
        if not url:
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("链接必须以 http:// 或 https:// 开头：" + url[:60])
        label = str(item.get("label") or "").strip()[:80] or url[:80]
        links.append({"label": label, "url": url})
        if len(links) >= MAX_LINKS:
            break
    return links


REPEAT_FREQUENCIES = ("daily", "weekday", "weekly", "monthly")


def review_columns(value: Any) -> tuple[str, int, str]:
    """review 字段 → (review_due, review_learning, review_log) 三列。

    前端传的是 {due, learning, log:[{at,result}]}；整树写入与节点级 patch 共用这一处口径，
    避免出现"全量保存认这个字段、patch 不认"的偏差。
    """
    review_due = ""
    review_learning = 0
    review_log = ""
    if isinstance(value, dict):
        due = str(value.get("due") or "")[:10].strip()
        if due:
            review_due = due
        review_learning = int(bool(value.get("learning")))
        log = value.get("log")
        if isinstance(log, list):
            entries = []
            for entry in log[-50:]:
                if not isinstance(entry, dict):
                    continue
                at = str(entry.get("at") or "")[:10].strip()
                result = str(entry.get("result") or "")[:10].strip()
                if at and result:
                    entries.append({"at": at, "result": result})
            if entries:
                review_log = _json(entries)
    return review_due, review_learning, review_log


def clean_repeat(value: Any) -> dict[str, Any] | None:
    """周期规则：{freq, interval?, weekday?, day?, until?}；非法返回 None。"""
    if not isinstance(value, dict):
        return None
    freq = str(value.get("freq") or "").strip().lower()
    if freq not in REPEAT_FREQUENCIES:
        return None
    rule: dict[str, Any] = {"freq": freq}
    if freq == "weekly":
        try:
            weekday = int(value.get("weekday"))
        except (TypeError, ValueError):
            return None
        if not 0 <= weekday <= 6:   # 0=周日（JS getDay()，见 next_repeat_due）
            return None
        rule["weekday"] = weekday
    if freq == "monthly":
        try:
            day = int(value.get("day"))
        except (TypeError, ValueError):
            return None
        if not 1 <= day <= 31:
            return None
        rule["day"] = day
    if freq == "daily":
        try:
            interval = int(value.get("interval") or 1)
        except (TypeError, ValueError):
            return None
        rule["interval"] = max(1, min(365, interval))
    until = clean_due_date(value.get("until"))
    if until:
        rule["until"] = until
    return rule


def next_repeat_due(rule: Any, from_date: str) -> str:
    """按周期规则算出下一次到期日；无效规则或超过 until 返回空串。"""
    cleaned = clean_repeat(rule)
    if not cleaned:
        return ""
    base = clean_due_date(from_date) or date.today().isoformat()
    start = date.fromisoformat(base)
    freq = cleaned["freq"]
    if freq == "daily":
        candidate = start + timedelta(days=cleaned.get("interval", 1))
    elif freq == "weekday":
        candidate = start + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
    elif freq == "weekly":
        # weekday 的取值与前端（也是唯一客户端）统一用 JS getDay()：0=周日 … 6=周六。
        # 历史上前端按 getDay() 写、后端按 date.weekday() 读，同一个规则会差一天。
        target = cleaned["weekday"]
        candidate = start + timedelta(days=1)
        while (candidate.weekday() + 1) % 7 != target:
            candidate += timedelta(days=1)
    else:  # monthly
        day = cleaned["day"]
        year, month = start.year, start.month
        for _ in range(24):
            month += 1
            if month > 12:
                month = 1
                year += 1
            last_day = (date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)).day
            if day <= last_day:
                candidate = date(year, month, day)
                break
        else:
            return ""
    until = cleaned.get("until")
    if until and candidate.isoformat() > until:
        return ""
    return candidate.isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode_object(payload: str, error_message: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        raise RuntimeError(error_message) from None
    if not isinstance(value, dict):
        raise RuntimeError(error_message)
    return value


def database_user_version() -> int:
    with sqlite3.connect(DATABASE_FILE, timeout=10, factory=_ManagedConnection) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


_schema_ready: dict[str, tuple[tuple[int, int], int]] = {}
_schema_ready_lock = threading.Lock()


def _file_signature(path: Path) -> tuple[int, int]:
    """库文件身份 = (设备号, inode)；恢复/导入都是 os.replace 整体换文件，inode 会变。"""
    try:
        stat_result = path.stat()
    except OSError:
        return (-1, -1)
    return (stat_result.st_dev, stat_result.st_ino)


def _schema_is_ready(path: Path, signature: tuple[int, int], version: int) -> bool:
    with _schema_ready_lock:
        return _schema_ready.get(str(path)) == (signature, version)


def _remember_schema_ready(path: Path, signature: tuple[int, int], version: int) -> None:
    with _schema_ready_lock:
        _schema_ready[str(path)] = (signature, version)


def open_state_database() -> sqlite3.Connection:
    """打开主库：连接级 PRAGMA + 版本守卫每次都做，幂等 DDL 只在本进程首次见到该文件时重放。

    实测那一遍 DDL + table_info 约 243 µs，而 GET /api/trash 以前一条请求要开 4 次连接。
    缓存键是 (路径, inode, 打开时读到的版本)，所以：
      · 备份恢复 / 备忘录导入 / 迁移回滚换掉文件 → inode 变 → 重新建表；
      · 删库重建 → inode 或版本(0) 不符 → 重新建表；
      · 更高版本的库 → 版本守卫照旧先拒绝，缓存短路不了安全检查。
    """
    database_file = DATABASE_FILE
    database_file.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_file, timeout=10, factory=_ManagedConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    # 版本守卫必须在任何"会写文件"的 PRAGMA 之前：journal_mode=WAL 会改写数据库文件头，
    # 对一个未来版本的库执行它，等于在被拒绝打开的同时动了别人的文件。
    stored_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if stored_version > SCHEMA_VERSION:
        connection.close()
        raise SchemaVersionError(
            f"数据库 schema 版本为 {stored_version}，高于本程序支持的 {SCHEMA_VERSION}；"
            "请升级程序后再打开（已拒绝打开，避免降级损坏数据）"
        )
    signature = _file_signature(database_file)
    if not _schema_is_ready(database_file, signature, stored_version):
        _bootstrap_state_database(connection, database_file)
        after = int(connection.execute("PRAGMA user_version").fetchone()[0])
        _remember_schema_ready(database_file, signature, after)
    # 下面这些是连接级设置（不持久化），每条新连接都必须设，否则会静默失去外键级联与忙等。
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA wal_autocheckpoint=1000")
    return connection


def _bootstrap_state_database(connection: sqlite3.Connection, database_file: Path) -> None:
    """本进程第一次打开这个库文件时：收紧权限 → 开 WAL → 重放幂等建表/建索引/补列。"""
    try:
        database_file.parent.chmod(0o700)
    except OSError:
        pass
    try:
        database_file.chmod(0o600)
    except OSError:
        pass
    # WAL 记在文件头里（持久化），所以只在 bootstrap 设一次；换了文件会重新 bootstrap。
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS app_state ("
        "key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "revision INTEGER NOT NULL DEFAULT 0)"
    )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            id_json TEXT NOT NULL,
            position INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            assessment_enabled INTEGER NOT NULL DEFAULT 0,
            revision INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            summary_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_projects_position ON projects(position);
        CREATE TABLE IF NOT EXISTS nodes (
            project_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            id_json TEXT NOT NULL,
            parent_id TEXT,
            position INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('week', 'day', 'item')),
            text TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            optional INTEGER NOT NULL DEFAULT 0,
            assessment_required INTEGER NOT NULL DEFAULT 0,
            assessment_history INTEGER NOT NULL DEFAULT 0,
            expanded INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(project_id, node_id),
            FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_nodes_parent
            ON nodes(project_id, parent_id, position);
        CREATE TABLE IF NOT EXISTS assessments (
            project_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id, node_id),
            FOREIGN KEY(project_id, node_id)
                REFERENCES nodes(project_id, node_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS conversations (
            project_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            question_index INTEGER NOT NULL,
            message_index INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            PRIMARY KEY(project_id, node_id, question_index, message_index),
            FOREIGN KEY(project_id, node_id)
                REFERENCES nodes(project_id, node_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS app_asset (
            key TEXT PRIMARY KEY,
            payload BLOB NOT NULL,
            mime_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trash_items (
            trash_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK(kind IN ('project', 'node')),
            project_id TEXT NOT NULL,
            parent_id TEXT,
            position INTEGER NOT NULL,
            title TEXT NOT NULL,
            context TEXT NOT NULL,
            payload TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_trash_deleted_at
            ON trash_items(deleted_at DESC, trash_id);
        CREATE TABLE IF NOT EXISTS saved_views (
            view_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_saved_views_name ON saved_views(name);
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL,
            project_id TEXT NOT NULL DEFAULT '',
            project_name TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            undoable INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_activity_at ON activity_log(at DESC, id DESC);
        CREATE TABLE IF NOT EXISTS project_templates (
            template_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            builtin INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS review_points (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            minutes INTEGER NOT NULL DEFAULT 10,
            module TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL DEFAULT '基础',
            origin TEXT NOT NULL DEFAULT 'builtin',
            content_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_point_tasks (
            code TEXT NOT NULL,
            task_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            PRIMARY KEY (code, task_id, project_id)
        );
        CREATE TABLE IF NOT EXISTS review_states (
            code TEXT PRIMARY KEY,
            due TEXT NOT NULL DEFAULT '',
            interval_days INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 0,
            lapses INTEGER NOT NULL DEFAULT 0,
            last_grade INTEGER NOT NULL DEFAULT 0,
            weak INTEGER NOT NULL DEFAULT 0,
            last_reviewed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS review_attempts (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            task_id TEXT NOT NULL DEFAULT '',
            project_id TEXT NOT NULL DEFAULT '',
            question_type TEXT NOT NULL,
            grade INTEGER NOT NULL,
            answer TEXT NOT NULL DEFAULT '',
            ai_verdict TEXT NOT NULL DEFAULT '',
            reviewed_on TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            session_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_sessions (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT '',
            planned INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0,
            grade_counts_json TEXT NOT NULL DEFAULT '{}',
            duration_ms INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_review_states_due ON review_states(due);
        CREATE INDEX IF NOT EXISTS idx_review_states_weak ON review_states(weak);
        CREATE INDEX IF NOT EXISTS idx_review_attempts_code ON review_attempts(code, created_at);
        CREATE INDEX IF NOT EXISTS idx_review_attempts_day ON review_attempts(reviewed_on);
        CREATE INDEX IF NOT EXISTS idx_review_tasks_task ON review_point_tasks(task_id);
        """
    )
    node_columns = {row[1] for row in connection.execute("PRAGMA table_info(nodes)")}
    if "completed_at" not in node_columns:
        connection.execute("ALTER TABLE nodes ADD COLUMN completed_at TEXT NOT NULL DEFAULT ''")
    if "review_due" not in node_columns:
        connection.execute("ALTER TABLE nodes ADD COLUMN review_due TEXT NOT NULL DEFAULT ''")
    if "review_learning" not in node_columns:
        connection.execute("ALTER TABLE nodes ADD COLUMN review_learning INTEGER NOT NULL DEFAULT 0")
    if "review_log" not in node_columns:
        connection.execute("ALTER TABLE nodes ADD COLUMN review_log TEXT NOT NULL DEFAULT ''")
    for column, ddl in (
        ("priority", "TEXT NOT NULL DEFAULT ''"),
        ("due_date", "TEXT NOT NULL DEFAULT ''"),
        ("estimate_minutes", "INTEGER NOT NULL DEFAULT 0"),
        ("tags", "TEXT NOT NULL DEFAULT ''"),
        ("note", "TEXT NOT NULL DEFAULT ''"),
        ("links", "TEXT NOT NULL DEFAULT ''"),
        ("repeat", "TEXT NOT NULL DEFAULT ''"),
    ):
        if column not in node_columns:
            connection.execute(f"ALTER TABLE nodes ADD COLUMN {column} {ddl}")
    project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    if "review_enabled" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN review_enabled INTEGER")
    if "archived" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
    if "last_opened_at" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN last_opened_at TEXT NOT NULL DEFAULT ''")
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_nodes_due ON nodes(project_id, due_date);
        CREATE INDEX IF NOT EXISTS idx_nodes_priority ON nodes(project_id, priority);
        CREATE INDEX IF NOT EXISTS idx_projects_archived ON projects(archived);
        -- 复习队列：completed=1 且 review_due 到期；工作台也用 review_due
        CREATE INDEX IF NOT EXISTS idx_nodes_review ON nodes(review_due)
            WHERE review_due <> '';
        CREATE INDEX IF NOT EXISTS idx_nodes_completed ON nodes(project_id, completed);
        -- 全局搜索按需扫 text/tags（LIKE 用不上索引，但限定 type 能减少行数）
        CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
        """
    )
    # 只做幂等补列/建表；版本号由 ensure_schema() 在迁移成功后写入。
    # 这里绝不能无条件写 user_version：那会把更高版本的库"降级"成旧结构继续用。


def project_summary(project: dict[str, Any]) -> dict[str, Any]:
    total = remaining = optional_total = optional_completed = 0

    def walk(nodes: Any) -> None:
        nonlocal total, remaining, optional_total, optional_completed
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("type") == "item":
                if node.get("optional"):
                    optional_total += 1
                    if node.get("completed"):
                        optional_completed += 1
                else:
                    total += 1
                    if not node.get("completed"):
                        remaining += 1
            walk(node.get("children"))

    walk(project.get("tree"))
    return {
        "id": project.get("id"),
        "name": str(project.get("name", "未命名项目")),
        "description": str(project.get("description", "")),
        "createdAt": str(project.get("createdAt", "")),
        "assessmentEnabled": bool(project.get("assessmentEnabled")),
        "archived": bool(project.get("archived")),
        "stats": {
            "total": total,
            "remaining": remaining,
            "optionalTotal": optional_total,
            "optionalCompleted": optional_completed,
        },
    }


def _flatten_nodes(project_id: str, nodes: Any, parent_id: str | None = None,
                   path: tuple[str, ...] = (), seen_ids: set[str] | None = None) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    if not isinstance(nodes, list):
        return flattened
    if seen_ids is None:
        seen_ids = set()
    for position, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            raise ValueError("项目中存在无效节点（不是对象）")
        node_type = str(raw.get("type", ""))
        if node_type not in {"week", "day", "item"}:
            raise ValueError("项目中存在未知节点类型：" + (str(raw.get("type")) or "(空)"))
        label = str(raw.get("text") or node_type)
        node_path = path + (label,)
        raw_id = raw.get("id")
        if raw_id is None or str(raw_id).strip() == "":
            raw_id = str(uuid.uuid4())  # 缺失 ID 直接生成，而不是整份导入失败
        node_id = str(raw_id)
        if node_id in seen_ids:
            raise ValueError(f"节点 ID 重复：{' / '.join(node_path)}（ID {node_id}）")
        seen_ids.add(node_id)
        assessment = raw.get("assessment") if isinstance(raw.get("assessment"), dict) else None
        metadata = {
            "priority": "",
            "due_date": "",
            "estimate_minutes": 0,
            "tags": "",
            "note": "",
            "links": "",
            "repeat": "",
        }
        if node_type == "item":
            metadata["priority"] = clean_priority(raw.get("priority"))
            metadata["due_date"] = clean_due_date(raw.get("dueDate"))
            metadata["estimate_minutes"] = clean_estimate_minutes(raw.get("estimateMinutes"))
            tags = clean_tags(raw.get("tags"))
            metadata["tags"] = _json(tags) if tags else ""
            metadata["note"] = str(raw.get("note") or "")[:MAX_NOTE_CHARS]
            links = clean_links(raw.get("links"))
            metadata["links"] = _json(links) if links else ""
            repeat = clean_repeat(raw.get("repeat"))
            metadata["repeat"] = _json(repeat) if repeat else ""
        review_due = ""
        review_learning = 0
        review_log = ""
        if node_type == "item":
            review_due, review_learning, review_log = review_columns(raw.get("review"))
        flattened.append({
            "project_id": project_id,
            "node_id": node_id,
            "id_json": _json(node_id),
            "parent_id": parent_id,
            "position": position,
            "type": node_type,
            "text": str(raw.get("text", "")),
            "completed": int(bool(raw.get("completed"))),
            "optional": int(bool(raw.get("optional"))) if node_type == "item" else 0,
            "assessment_required": int(bool(raw.get("assessmentRequired"))) if node_type == "item" else 0,
            "assessment_history": max(0, int(raw.get("assessmentHistory") or 0)) if node_type == "item" else 0,
            "expanded": int(bool(raw.get("expanded"))) if node_type != "item" else 0,
            "created_at": str(raw.get("createdAt", "")),
            "completed_at": str(raw.get("completedAt") or "") if node_type == "item" else "",
            "review_due": review_due,
            "review_learning": review_learning,
            "review_log": review_log,
            "assessment": assessment,
            **metadata,
        })
        flattened.extend(_flatten_nodes(project_id, raw.get("children"), node_id, node_path, seen_ids))
    return flattened


def _upsert_project(connection: sqlite3.Connection, project: dict[str, Any], position: int,
                    revision: int, updated_at: str) -> None:
    if project.get("id") is None:
        raise ValueError("项目缺少 ID")
    project_id = str(project["id"])
    nodes = _flatten_nodes(project_id, project.get("tree"))
    node_ids = [node["node_id"] for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("项目中存在重复节点 ID")
    summary = project_summary(project)
    if "reviewEnabled" in project:
        review_enabled = 1 if project.get("reviewEnabled") else 0
    else:
        review_enabled = None
    connection.execute(
        """INSERT INTO projects(
            project_id,id_json,position,name,description,created_at,
            assessment_enabled,revision,updated_at,summary_json,review_enabled,
            archived,last_opened_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(project_id) DO UPDATE SET
            id_json=excluded.id_json, position=excluded.position, name=excluded.name,
            description=excluded.description, created_at=excluded.created_at,
            assessment_enabled=excluded.assessment_enabled,
            revision=excluded.revision, updated_at=excluded.updated_at,
            summary_json=excluded.summary_json, review_enabled=excluded.review_enabled,
            archived=excluded.archived,
            -- 前端不会回传 lastOpenedAt（它由 touch_project_opened 维护）。
            -- 直接赋值会让每次保存都把"最近打开"时间清空，等于丢掉最近记录。
            last_opened_at=CASE
                WHEN excluded.last_opened_at <> '' THEN excluded.last_opened_at
                ELSE projects.last_opened_at
            END""",
        (project_id, _json(project["id"]), position, str(project.get("name", "未命名项目")),
         str(project.get("description", "")), str(project.get("createdAt", "")),
         int(bool(project.get("assessmentEnabled"))), revision, updated_at, _json(summary),
         review_enabled, int(bool(project.get("archived"))),
         str(project.get("lastOpenedAt") or "")),
    )
    existing_rows = _existing_node_rows(connection, project_id)
    changed_rows = []
    for node in nodes:
        fingerprint = tuple(node[column] for column in NODE_ROW_COLUMNS)
        if existing_rows.get(node["node_id"]) == fingerprint:
            continue  # 这一行一个字都没变：不再发一条注定空写的 upsert
        changed_rows.append(fingerprint)
    if changed_rows:
        connection.executemany(NODE_UPSERT_SQL, changed_rows)
    removed_ids = existing_rows.keys() - {node["node_id"] for node in nodes}
    if removed_ids:
        connection.executemany(
            "DELETE FROM nodes WHERE project_id=? AND node_id=?",
            [(project_id, node_id) for node_id in removed_ids],
        )
    _sync_assessments(connection, project_id, nodes, _now())


NODE_ROW_COLUMNS = (
    "project_id", "node_id", "id_json", "parent_id", "position", "type", "text",
    "completed", "optional", "assessment_required", "assessment_history", "expanded", "created_at",
    "completed_at", "review_due", "review_learning", "review_log",
    "priority", "due_date", "estimate_minutes", "tags", "note", "links", "repeat",
)


def _existing_node_rows(connection: sqlite3.Connection, project_id: str) -> dict[str, tuple[Any, ...]]:
    """一次读出项目里所有节点的完整行，作为"这一行有没有变"的指纹。

    改动前每个节点都无条件发一条 upsert（1000 个节点、内容一个字都没变也要 1000 条 SQL）；
    多读一次全行换掉整批空写，是这一轮写放大修复的核心。
    """
    columns = ",".join(NODE_ROW_COLUMNS)
    rows: dict[str, tuple[Any, ...]] = {}
    for row in connection.execute(
        f"SELECT {columns} FROM nodes WHERE project_id=?", (project_id,)
    ):
        rows[str(row["node_id"])] = tuple(row[column] for column in NODE_ROW_COLUMNS)
    return rows


NODE_UPSERT_SQL = """INSERT INTO nodes(
        project_id,node_id,id_json,parent_id,position,type,text,completed,
        optional,assessment_required,assessment_history,expanded,created_at,completed_at,
        review_due,review_learning,review_log,
        priority,due_date,estimate_minutes,tags,note,links,repeat
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(project_id,node_id) DO UPDATE SET
        id_json=excluded.id_json,parent_id=excluded.parent_id,position=excluded.position,
        type=excluded.type,text=excluded.text,completed=excluded.completed,
        optional=excluded.optional,assessment_required=excluded.assessment_required,
        assessment_history=excluded.assessment_history,expanded=excluded.expanded,
        created_at=excluded.created_at,completed_at=excluded.completed_at,
        review_due=excluded.review_due,review_learning=excluded.review_learning,
        review_log=excluded.review_log,
        priority=excluded.priority,due_date=excluded.due_date,
        estimate_minutes=excluded.estimate_minutes,tags=excluded.tags,
        note=excluded.note,links=excluded.links,repeat=excluded.repeat
    WHERE id_json<>excluded.id_json OR parent_id IS NOT excluded.parent_id
        OR position<>excluded.position OR type<>excluded.type OR text<>excluded.text
        OR completed<>excluded.completed OR optional<>excluded.optional
        OR assessment_required<>excluded.assessment_required
        OR assessment_history<>excluded.assessment_history
        OR expanded<>excluded.expanded OR created_at<>excluded.created_at
        OR completed_at<>excluded.completed_at
        OR review_due<>excluded.review_due OR review_learning<>excluded.review_learning
        OR review_log<>excluded.review_log
        OR priority<>excluded.priority OR due_date<>excluded.due_date
        OR estimate_minutes<>excluded.estimate_minutes OR tags<>excluded.tags
        OR note<>excluded.note OR links<>excluded.links OR repeat<>excluded.repeat"""

ASSESSMENT_UPSERT_SQL = """INSERT INTO assessments(project_id,node_id,payload,updated_at) VALUES(?,?,?,?)
    ON CONFLICT(project_id,node_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at
    WHERE payload<>excluded.payload"""

CONVERSATION_UPSERT_SQL = """INSERT INTO conversations(
        project_id,node_id,question_index,message_index,role,content
    ) VALUES(?,?,?,?,?,?)
    ON CONFLICT(project_id,node_id,question_index,message_index) DO UPDATE SET
        role=excluded.role,content=excluded.content
    WHERE role<>excluded.role OR content<>excluded.content"""

CONVERSATION_DELETE_SQL = (
    "DELETE FROM conversations WHERE project_id=? AND node_id=?"
    " AND question_index=? AND message_index=?"
)


def _insert_node_row(connection: sqlite3.Connection, node: dict[str, Any]) -> None:
    """插入/更新一行节点（列清单与整项目写入共用，避免两处漂移）。"""
    connection.execute(NODE_UPSERT_SQL, tuple(node[key] for key in NODE_ROW_COLUMNS))


def _assessment_payload(assessment: dict[str, Any]) -> tuple[str, bool, list[Any]]:
    """验收对象 → (落库 payload, payload 是否带 questionConversations 键, 逐题消息)。

    payload 里把 questionConversations 换成等长空数组占位（消息正文单独存表），
    但"这个键在不在"本身是语义：缺键表示客户端只改了别的字段，绝不能删已有对话。
    """
    stored = dict(assessment)
    conversations_present = "questionConversations" in stored
    conversations = stored.pop("questionConversations", [])
    if conversations_present and isinstance(conversations, list):
        stored["questionConversations"] = [[] for _ in conversations]
    return _json(stored), conversations_present, (conversations if isinstance(conversations, list) else [])


def _conversation_rows(project_id: str, node_id: str,
                       conversations: list[Any]) -> tuple[set[tuple[int, int]], list[tuple[Any, ...]]]:
    """逐题消息 → (有效键集合, 待写入行)；结构非法或角色不对的条目按原口径跳过。"""
    valid_keys: set[tuple[int, int]] = set()
    rows: list[tuple[Any, ...]] = []
    for question_index, messages in enumerate(conversations):
        if not isinstance(messages, list):
            continue
        for message_index, message in enumerate(messages):
            if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
                continue
            valid_keys.add((question_index, message_index))
            rows.append((project_id, node_id, question_index, message_index,
                         message["role"], str(message.get("content", ""))))
    return valid_keys, rows


def _sync_assessments(connection: sqlite3.Connection, project_id: str,
                      nodes: list[dict[str, Any]], updated_at: str) -> None:
    """整项目写入时批量同步验收记录与逐题对话：一次读存量 → 差集 → executemany。

    语义与单节点的 _write_assessment 完全一致（两者共用 _assessment_payload /
    _conversation_rows 与同一批 SQL 常量），只是把"N 个节点各发若干条 SQL"收敛成
    "读一次 + 只为真正的变化写"：没有验收的节点不再发空 DELETE，没变的消息不再重写。
    """
    existing_payloads: dict[str, str] = {
        str(row["node_id"]): str(row["payload"])
        for row in connection.execute(
            "SELECT node_id,payload FROM assessments WHERE project_id=?", (project_id,)
        )
    }
    needs_conversation_diff = any(
        isinstance(node.get("assessment"), dict) and "questionConversations" in node["assessment"]
        for node in nodes
    )
    existing_messages: dict[str, dict[tuple[int, int], tuple[str, str]]] = {}
    if needs_conversation_diff:
        for row in connection.execute(
            """SELECT node_id,question_index,message_index,role,content FROM conversations
            WHERE project_id=?""",
            (project_id,),
        ):
            existing_messages.setdefault(str(row["node_id"]), {})[
                (int(row["question_index"]), int(row["message_index"]))
            ] = (str(row["role"]), str(row["content"]))

    assessment_upserts: list[tuple[Any, ...]] = []
    assessment_deletes: list[tuple[Any, ...]] = []
    message_upserts: list[tuple[Any, ...]] = []
    message_deletes: list[tuple[Any, ...]] = []
    for node in nodes:
        node_id = node["node_id"]
        assessment = node["assessment"]
        if assessment is None:
            # 只删确实存在的行；以前对每个没有验收的节点也要发一条注定删不到东西的 DELETE
            if node_id in existing_payloads:
                assessment_deletes.append((project_id, node_id))
            continue
        payload, conversations_present, conversations = _assessment_payload(assessment)
        if existing_payloads.get(node_id) != payload:
            assessment_upserts.append((project_id, node_id, payload, updated_at))
        if not conversations_present:
            # 缺键 = 客户端没提交对话，一个字都不能动（老代码在这里删光过用户数据）
            continue
        valid_keys, rows = _conversation_rows(project_id, node_id, conversations)
        stored_messages = existing_messages.get(node_id, {})
        for row in rows:
            if stored_messages.get((row[2], row[3])) != (row[4], row[5]):
                message_upserts.append(row)
        for key in stored_messages:
            if key not in valid_keys:
                message_deletes.append((project_id, node_id, *key))

    if assessment_deletes:
        connection.executemany(
            "DELETE FROM assessments WHERE project_id=? AND node_id=?", assessment_deletes
        )
    if assessment_upserts:
        connection.executemany(ASSESSMENT_UPSERT_SQL, assessment_upserts)
    if message_upserts:
        connection.executemany(CONVERSATION_UPSERT_SQL, message_upserts)
    if message_deletes:
        connection.executemany(CONVERSATION_DELETE_SQL, message_deletes)


def _write_assessment(connection: sqlite3.Connection, node: dict[str, Any], updated_at: str) -> None:
    """单节点验收写入（节点级 patch 走这里）；与整项目写入的 _sync_assessments 共用口径。"""
    project_id, node_id = node["project_id"], node["node_id"]
    assessment = node["assessment"]
    if assessment is None:
        connection.execute("DELETE FROM assessments WHERE project_id=? AND node_id=?", (project_id, node_id))
        return
    payload, conversations_present, conversations = _assessment_payload(assessment)
    connection.execute(ASSESSMENT_UPSERT_SQL, (project_id, node_id, payload, updated_at))
    if not conversations_present:
        # 只有 payload 真的带了 questionConversations 键时才做差集删除。
        # 否则（例如客户端只发 {"passed": true}）valid_keys 为空，会把该节点已有的逐题对话全部删掉。
        return
    valid_keys, rows = _conversation_rows(project_id, node_id, conversations)
    if rows:
        connection.executemany(CONVERSATION_UPSERT_SQL, rows)
    for row in connection.execute(
        "SELECT question_index,message_index FROM conversations WHERE project_id=? AND node_id=?",
        (project_id, node_id),
    ):
        key = (int(row[0]), int(row[1]))
        if key not in valid_keys:
            connection.execute(CONVERSATION_DELETE_SQL, (project_id, node_id, *key))


def _read_project_from_connection(connection: sqlite3.Connection, project_id: str) -> tuple[dict[str, Any], int] | None:
    row = connection.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
    if not row:
        return None
    project = {
        "id": json.loads(row["id_json"]),
        "name": row["name"],
        "description": row["description"],
        "createdAt": row["created_at"],
        "assessmentEnabled": bool(row["assessment_enabled"]),
        "archived": bool(row["archived"]),
        "tree": [],
    }
    if row["last_opened_at"]:
        project["lastOpenedAt"] = str(row["last_opened_at"])
    if row["review_enabled"] is not None:
        project["reviewEnabled"] = bool(row["review_enabled"])
    node_rows = connection.execute(
        "SELECT * FROM nodes WHERE project_id=? ORDER BY parent_id,position,node_id", (project_id,)
    ).fetchall()
    by_id: dict[str, dict[str, Any]] = {}
    parent_by_id: dict[str, str | None] = {}
    for node_row in node_rows:
        node_type = node_row["type"]
        node = {
            "id": json.loads(node_row["id_json"]),
            "type": node_type,
            "text": node_row["text"],
            "completed": bool(node_row["completed"]),
            "optional": bool(node_row["optional"]),
            "assessmentRequired": bool(node_row["assessment_required"]),
            "assessment": None,
            "assessmentHistory": int(node_row["assessment_history"]),
            "expanded": bool(node_row["expanded"]),
            "createdAt": node_row["created_at"],
            "children": [],
        }
        if node_row["completed_at"]:
            node["completedAt"] = node_row["completed_at"]
        if node_type == "item":
            node["priority"] = str(node_row["priority"] or "")
            node["dueDate"] = str(node_row["due_date"] or "")
            if int(node_row["estimate_minutes"] or 0) > 0:
                node["estimateMinutes"] = int(node_row["estimate_minutes"])
            tags_raw = str(node_row["tags"] or "")
            if tags_raw:
                try:
                    parsed_tags = json.loads(tags_raw)
                except (TypeError, json.JSONDecodeError):
                    parsed_tags = None
                if isinstance(parsed_tags, list) and parsed_tags:
                    node["tags"] = [str(item)[:MAX_TAG_CHARS] for item in parsed_tags[:MAX_TAGS]]
            if node_row["note"]:
                node["note"] = str(node_row["note"])
            repeat_raw = str(node_row["repeat"] or "")
            if repeat_raw:
                try:
                    parsed_repeat = json.loads(repeat_raw)
                except (TypeError, json.JSONDecodeError):
                    parsed_repeat = None
                cleaned_repeat = clean_repeat(parsed_repeat)
                if cleaned_repeat:
                    node["repeat"] = cleaned_repeat
            links_raw = str(node_row["links"] or "")
            if links_raw:
                try:
                    parsed_links = json.loads(links_raw)
                except (TypeError, json.JSONDecodeError):
                    parsed_links = None
                if isinstance(parsed_links, list) and parsed_links:
                    node["links"] = [
                        {"label": str(entry.get("label") or "")[:80], "url": str(entry.get("url") or "")[:MAX_LINK_CHARS]}
                        for entry in parsed_links[:MAX_LINKS] if isinstance(entry, dict)
                    ]
        if node_type == "item" and (node_row["review_due"] or node_row["review_log"]
                                    or node_row["review_learning"]):
            review_due = str(node_row["review_due"] or "")
            review_log = []
            if node_row["review_log"]:
                try:
                    parsed_log = json.loads(node_row["review_log"])
                except (TypeError, json.JSONDecodeError):
                    parsed_log = None
                if isinstance(parsed_log, list):
                    for entry in parsed_log[-50:]:
                        if not isinstance(entry, dict):
                            continue
                        at = str(entry.get("at") or "")[:10]
                        result = str(entry.get("result") or "")[:10]
                        if at and result:
                            review_log.append({"at": at, "result": result})
            node["review"] = {
                "due": review_due,
                "learning": bool(node_row["review_learning"]),
                "log": review_log,
            }
        by_id[node_row["node_id"]] = node
        parent_by_id[node_row["node_id"]] = node_row["parent_id"]
    assessment_rows = connection.execute(
        "SELECT node_id,payload FROM assessments WHERE project_id=?", (project_id,)
    ).fetchall()
    for assessment_row in assessment_rows:
        node = by_id.get(assessment_row["node_id"])
        if not node:
            continue
        assessment = _decode_object(assessment_row["payload"], "SQLite 中的验收数据损坏")
        messages = connection.execute(
            """SELECT question_index,message_index,role,content FROM conversations
            WHERE project_id=? AND node_id=? ORDER BY question_index,message_index""",
            (project_id, assessment_row["node_id"]),
        ).fetchall()
        if messages:
            highest = max(int(message["question_index"]) for message in messages)
            existing_slots = assessment.get("questionConversations")
            slot_count = len(existing_slots) if isinstance(existing_slots, list) else 0
            conversations: list[list[dict[str, str]]] = [[] for _ in range(max(highest + 1, slot_count))]
            for message in messages:
                conversations[int(message["question_index"])].append({
                    "role": message["role"], "content": message["content"]
                })
            assessment["questionConversations"] = conversations
        node["assessment"] = assessment
    child_rows: dict[str | None, list[sqlite3.Row]] = {}
    for node_row in node_rows:
        child_rows.setdefault(node_row["parent_id"], []).append(node_row)
    def attach(parent_id: str | None) -> list[dict[str, Any]]:
        result = []
        for child_row in child_rows.get(parent_id, []):
            node = by_id[child_row["node_id"]]
            node["children"] = attach(child_row["node_id"])
            result.append(node)
        return result
    project["tree"] = attach(None)
    return project, int(row["revision"])


def ensure_schema() -> None:
    """启动/恢复后调用：版本检查 → 未来版本拒绝；低版本逐步迁移（先快照，失败回滚）。

    本项目的阶梯只有一级：v0/legacy（project_state / app_state 单表 JSON）→ 当前分表结构。
    以后新增版本时在这里加 `_migrate_vN_to_M` 步骤，并保证每步幂等、可回滚。
    """
    with _database_lock:
        version = 0
        with open_state_database() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version == SCHEMA_VERSION:
                return
            if version > SCHEMA_VERSION:
                raise SchemaVersionError(
                    f"数据库 schema 版本为 {version}，高于本程序支持的 {SCHEMA_VERSION}；"
                    "请升级程序后再打开（已拒绝打开，避免降级损坏数据）"
                )
            has_data = bool(
                connection.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
                or connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='project_state'"
                ).fetchone()
            )
        backup_name = create_manual_database_backup(f"before-migrate-v{version}") if has_data else ""
        try:
            # v7 -> v8：只新增 5 张复习表与索引（DDL 幂等，已在 open_state_database 里执行），
            # 不改动既有列、不回填数据；迁移前已自动快照，失败会回滚。
            migrate_legacy_state()
            with _database_lock:
                with open_state_database() as connection:
                    if not check_database_integrity():
                        raise RuntimeError("迁移后数据库完整性检查失败")
                    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        except Exception:
            if backup_name:
                _restore_database_file(BACKUP_DIR / backup_name)
            raise
        if backup_name:
            print(f"schema 从 v{version} 迁移到 v{SCHEMA_VERSION}；迁移前快照：{backup_name}")


def migrate_legacy_state() -> None:
    """Migrate old JSON rows into normalized tables and verify exact reconstruction."""
    with _database_lock, open_state_database() as connection:
        legacy_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='project_state'"
        ).fetchone()
        if connection.execute("SELECT 1 FROM projects LIMIT 1").fetchone():
            if legacy_table:
                connection.execute("DROP TABLE project_state")
            _mark_normalized_state(connection)
            return
        legacy_rows = []
        if legacy_table:
            legacy_columns = {row[1] for row in connection.execute("PRAGMA table_info(project_state)")}
            revision_sql = "revision" if "revision" in legacy_columns else "0 AS revision"
            legacy_rows = connection.execute(
                f"SELECT project_id,position,payload,updated_at,{revision_sql} "
                "FROM project_state ORDER BY position,project_id"
            ).fetchall()
        if not legacy_rows:
            state_row = connection.execute("SELECT payload FROM app_state WHERE key='projects'").fetchone()
            if state_row:
                state = _decode_object(state_row[0], "SQLite 中的项目数据损坏")
                for position, project in enumerate(state.get("projects", [])):
                    legacy_rows.append({"project_id": str(project.get("id")), "position": position,
                                        "payload": _json(project), "updated_at": str(state.get("updatedAt", "")),
                                        "revision": 0})
        if not legacy_rows:
            return
        connection.execute("BEGIN IMMEDIATE")
        originals: dict[str, dict[str, Any]] = {}
        for row in legacy_rows:
            project = _decode_object(row["payload"], "SQLite 中的项目数据损坏")
            project_id = str(project.get("id"))
            originals[project_id] = project
            _upsert_project(connection, project, int(row["position"]), int(row["revision"] or 0), row["updated_at"])
        for project_id, original in originals.items():
            rebuilt = _read_project_from_connection(connection, project_id)
            if not rebuilt or rebuilt[0] != original:
                raise RuntimeError(f"项目 {project_id} 分表迁移校验失败")
        if legacy_table:
            connection.execute("DROP TABLE project_state")
        _mark_normalized_state(connection)


def _mark_normalized_state(connection: sqlite3.Connection) -> None:
    state_row = connection.execute("SELECT payload FROM app_state WHERE key='projects'").fetchone()
    if not state_row:
        return
    state = _decode_object(state_row[0], "SQLite 中的项目数据损坏")
    state.pop("projects", None)
    state["storageMode"] = "normalized_tables"
    connection.execute("UPDATE app_state SET payload=? WHERE key='projects'", (_json(state),))


# ---------------------------------------------------------------------------
# 应用设置（回收站保留天数 / 自动归档）与活动历史
# ---------------------------------------------------------------------------

SETTINGS_KEY = "settings"


def _clean_int(value: Any, *, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def read_app_settings(connection: sqlite3.Connection | None = None) -> dict[str, Any]:
    """读取应用设置；缺失或损坏时回落到默认值（不能因为设置坏了打不开应用）。"""
    settings = dict(DEFAULT_APP_SETTINGS)

    def _load(conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute("SELECT payload FROM app_state WHERE key=?", (SETTINGS_KEY,)).fetchone()
        if not row:
            return dict(settings)
        try:
            stored = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return dict(settings)
        if not isinstance(stored, dict):
            return dict(settings)
        merged = dict(settings)
        merged["trashRetentionDays"] = _clean_int(
            stored.get("trashRetentionDays"), minimum=MIN_TRASH_RETENTION_DAYS,
            maximum=MAX_TRASH_RETENTION_DAYS, default=settings["trashRetentionDays"])
        merged["autoArchiveEnabled"] = bool(stored.get("autoArchiveEnabled", settings["autoArchiveEnabled"]))
        merged["autoArchiveDays"] = _clean_int(
            stored.get("autoArchiveDays"), minimum=1, maximum=MAX_AUTO_ARCHIVE_DAYS,
            default=settings["autoArchiveDays"])
        merged["reviewDailyLimit"] = _clean_int(
            stored.get("reviewDailyLimit"), minimum=5, maximum=15,
            default=settings["reviewDailyLimit"])
        merged["reviewNewPerDay"] = _clean_int(
            stored.get("reviewNewPerDay"), minimum=0, maximum=5,
            default=settings["reviewNewPerDay"])
        return merged

    if connection is not None:
        return _load(connection)
    with _database_lock, open_state_database() as own:
        return _load(own)


def update_app_settings(patch: dict[str, Any]) -> dict[str, Any]:
    """只接受白名单字段；非法值直接报错，避免把设置写成乱七八糟的值。"""
    if not isinstance(patch, dict):
        raise ValueError("设置格式不正确")
    unknown = set(patch) - set(DEFAULT_APP_SETTINGS)
    if unknown:
        raise ValueError("不支持的设置项：" + "、".join(sorted(unknown)))
    with _database_lock, open_state_database() as connection:
        settings = read_app_settings(connection)
        if "trashRetentionDays" in patch:
            try:
                days = int(patch["trashRetentionDays"])
            except (TypeError, ValueError):
                raise ValueError("回收站保留天数必须是整数") from None
            if not MIN_TRASH_RETENTION_DAYS <= days <= MAX_TRASH_RETENTION_DAYS:
                raise ValueError(f"回收站保留天数应在 {MIN_TRASH_RETENTION_DAYS}~{MAX_TRASH_RETENTION_DAYS} 天之间")
            settings["trashRetentionDays"] = days
        if "autoArchiveEnabled" in patch:
            settings["autoArchiveEnabled"] = bool(patch["autoArchiveEnabled"])
        if "autoArchiveDays" in patch:
            try:
                days = int(patch["autoArchiveDays"])
            except (TypeError, ValueError):
                raise ValueError("自动归档天数必须是整数") from None
            if not 1 <= days <= MAX_AUTO_ARCHIVE_DAYS:
                raise ValueError(f"自动归档天数应在 1~{MAX_AUTO_ARCHIVE_DAYS} 天之间")
            settings["autoArchiveDays"] = days
        if "reviewDailyLimit" in patch:
            settings["reviewDailyLimit"] = _clean_int(
                patch.get("reviewDailyLimit"), minimum=5, maximum=15, default=10)
        if "reviewNewPerDay" in patch:
            settings["reviewNewPerDay"] = _clean_int(
                patch.get("reviewNewPerDay"), minimum=0, maximum=5, default=2)
        encoded = _json(settings)
        row = connection.execute("SELECT 1 FROM app_state WHERE key=?", (SETTINGS_KEY,)).fetchone()
        if row:
            connection.execute("UPDATE app_state SET payload=?, updated_at=? WHERE key=?",
                               (encoded, _now(), SETTINGS_KEY))
        else:
            connection.execute(
                "INSERT INTO app_state(key,payload,updated_at,revision) VALUES(?,?,?,0)",
                (SETTINGS_KEY, encoded, _now()))
    return settings


def log_activity(kind: str, summary: str, *, project_id: Any = "", project_name: str = "",
                 detail: dict[str, Any] | None = None, undoable: bool = False,
                 connection: sqlite3.Connection | None = None) -> None:
    """记录一条活动历史（可追溯）。同一事务里调用时传 connection，保证与业务一起提交/回滚。"""
    payload = (
        str(kind or "unknown"),
        str(project_id or ""),
        str(project_name or ""),
        str(summary or "")[:500],
        _json(detail or {}),
        1 if undoable else 0,
        _now(),
    )

    def _write(conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO activity_log(kind,project_id,project_name,summary,detail,undoable,at) "
            "VALUES(?,?,?,?,?,?,?)",
            (payload[0], payload[1], payload[2], payload[3], payload[4], payload[5], payload[6]),
        )

    if connection is not None:
        _write(connection)
        return
    with _database_lock, open_state_database() as own:
        _write(own)


def list_activity(limit: int = 50) -> list[dict[str, Any]]:
    size = _clean_int(limit, minimum=1, maximum=ACTIVITY_LIMIT_MAX, default=50)
    with _database_lock, open_state_database() as connection:
        rows = connection.execute(
            "SELECT id,at,kind,project_id,project_name,summary,detail,undoable "
            "FROM activity_log ORDER BY id DESC LIMIT ?", (size,)
        ).fetchall()
    entries = []
    for row in rows:
        entries.append({
            "id": int(row["id"]),
            "at": str(row["at"]),
            "kind": str(row["kind"]),
            "projectId": str(row["project_id"]),
            "projectName": str(row["project_name"]),
            "summary": str(row["summary"]),
            "detail": _decode_object(row["detail"], "活动记录损坏"),
            "undoable": bool(row["undoable"]),
        })
    return entries


def clear_activity() -> int:
    with _database_lock, open_state_database() as connection:
        cursor = connection.execute("DELETE FROM activity_log")
    return cursor.rowcount


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_trash_id() -> str:
    return str(uuid.uuid4())


def _project_title(project: dict[str, Any]) -> str:
    return str(project.get("name") or "未命名项目")


def store_trash_item(
    kind: str,
    project_id: Any,
    title: str,
    payload: dict[str, Any],
    *,
    parent_id: Any | None = None,
    position: int = 0,
    context: str = "",
    revision: int = 0,
) -> dict[str, Any]:
    if kind not in {"project", "node"}:
        raise ValueError("不支持的回收站条目类型")
    trash_id = _new_trash_id()
    now = _now()
    with _database_lock, open_state_database() as connection:
        connection.execute(
            """INSERT INTO trash_items(
                trash_id,kind,project_id,parent_id,position,title,context,payload,deleted_at,revision
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                trash_id,
                kind,
                str(project_id),
                str(parent_id) if parent_id is not None else None,
                int(position),
                str(title or "未命名条目"),
                str(context or ""),
                _json(payload),
                now,
                int(revision or 0),
            ),
        )
    return {
        "id": trash_id,
        "kind": kind,
        "projectId": str(project_id),
        "parentId": str(parent_id) if parent_id is not None else None,
        "position": int(position),
        "title": str(title or "未命名条目"),
        "context": str(context or ""),
        "deletedAt": now,
        "revision": int(revision or 0),
    }


def _purge_trash_items(connection: sqlite3.Connection, days: int) -> int:
    """真正干活的版本：复用调用方已经打开的连接（回收站接口一次请求只开一次库）。"""
    cutoff = (datetime.now() - timedelta(days=max(1, int(days)))).isoformat(timespec="seconds")
    return connection.execute("DELETE FROM trash_items WHERE deleted_at < ?", (cutoff,)).rowcount


def purge_trash_items(days: int | None = None) -> int:
    """删除早于保留天数的回收站条目（默认取应用设置里的 trashRetentionDays）。"""
    with _database_lock, open_state_database() as connection:
        if days is None:
            days = int(read_app_settings(connection)["trashRetentionDays"])
        return _purge_trash_items(connection, days)


def _ensure_orphan_box(project: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """父节点已被删除时，把任务恢复到这个保留容器里（找不到就新建一个）。"""
    tree = project.setdefault("tree", [])
    for node in tree:
        if str(node.get("type")) in CONTAINER_TYPES and str(node.get("text")) == ORPHAN_BOX_TITLE:
            return node.setdefault("children", []), str(node.get("id"))
    box_id = str(uuid.uuid4())
    box = {
        "id": box_id,
        "type": "day",
        "text": ORPHAN_BOX_TITLE,
        "completed": False,
        "expanded": True,
        "createdAt": date.today().isoformat(),
        "children": [],
    }
    tree.append(box)
    return box["children"], box_id


def list_trash_items() -> list[dict[str, Any]]:
    # 以前这里要开 4 次连接（purge → settings → purge 自身 → settings + 自身），
    # 每开一次就重放一遍 DDL；现在清理、读设置、读列表共用同一个连接。
    with _database_lock, open_state_database() as connection:
        settings = read_app_settings(connection)
        retention = int(settings["trashRetentionDays"])
        _purge_trash_items(connection, retention)
        rows = connection.execute(
            "SELECT trash_id,kind,project_id,parent_id,position,title,context,deleted_at,revision "
            "FROM trash_items ORDER BY deleted_at DESC,trash_id"
        ).fetchall()
        live_projects = {str(row[0]) for row in connection.execute("SELECT project_id FROM projects")}
        known_nodes: set[tuple[str, str]] = {
            (str(row[0]), str(row[1]))
            for row in connection.execute("SELECT project_id,node_id FROM nodes")
        }
    items = []
    for row in rows:
        deleted_at = str(row["deleted_at"])
        expires = ""
        try:
            expires = (datetime.fromisoformat(deleted_at) + timedelta(days=retention)).isoformat(
                timespec="seconds")
        except ValueError:
            expires = ""
        project_id = str(row["project_id"])
        parent_id = row["parent_id"]
        # 告诉前端"能不能恢复到原位"：父节点/项目没了就走孤立任务箱或直接禁用
        if str(row["kind"]) == "node":
            if project_id not in live_projects:
                restore_target = "unavailable"
            elif parent_id is not None and (project_id, str(parent_id)) not in known_nodes:
                restore_target = "orphan"
            else:
                restore_target = "original"
        else:
            restore_target = "original" if project_id not in live_projects else "conflict"
        items.append({
            "id": row["trash_id"],
            "kind": row["kind"],
            "projectId": project_id,
            "parentId": parent_id,
            "position": int(row["position"]),
            "title": row["title"],
            "context": row["context"],
            "deletedAt": deleted_at,
            "expiresAt": expires,
            "revision": int(row["revision"]),
            "restoreTarget": restore_target,
        })
    return items


def delete_trash_item(trash_id: Any) -> None:
    with _database_lock, open_state_database() as connection:
        connection.execute("DELETE FROM trash_items WHERE trash_id=?", (str(trash_id),))


def _find_children_list(tree: list[dict[str, Any]], parent_id: str | None) -> list[dict[str, Any]] | None:
    """返回 parent_id 对应节点的 children 列表；找不到返回 None。"""
    if parent_id is None:
        return tree
    def walk(nodes: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        for current in nodes or []:
            if str(current.get("id")) == str(parent_id):
                return current.setdefault("children", [])
            found = walk(current.get("children") or [])
            if found is not None:
                return found
        return None
    return walk(tree)


def _find_parent_and_insert(tree: list[dict[str, Any]], parent_id: str | None, node: dict[str, Any], position: int) -> None:
    if parent_id is None:
        tree.insert(max(0, min(position, len(tree))), node)
        return
    children = _find_children_list(tree, parent_id)
    if children is None:
        raise ValueError("找不到原父节点，无法恢复任务")
    children.insert(max(0, min(position, len(children))), node)


def clear_trash_items() -> int:
    """立即清空回收站（调用方负责先做快照与确认）。"""
    with _database_lock, open_state_database() as connection:
        cursor = connection.execute("DELETE FROM trash_items")
    return cursor.rowcount


def restore_trash_items(ids: list[Any]) -> dict[str, Any]:
    """批量恢复：逐条独立处理，返回成功/失败明细，不因为一条失败就中断。"""
    restored: list[str] = []
    failed: list[dict[str, str]] = []
    for raw_id in ids:
        trash_id = str(raw_id)
        try:
            restore_trash_item(trash_id)
            restored.append(trash_id)
        except Exception as error:  # 冲突/父节点缺失等都要报给用户，而不是中断整批
            failed.append({"id": trash_id, "error": str(error)})
    return {"restored": restored, "failed": failed}


def delete_trash_items(ids: list[Any]) -> dict[str, Any]:
    deleted: list[str] = []
    failed: list[dict[str, str]] = []
    for raw_id in ids:
        trash_id = str(raw_id)
        try:
            delete_trash_item(trash_id)
            deleted.append(trash_id)
        except Exception as error:
            failed.append({"id": trash_id, "error": str(error)})
    return {"deleted": deleted, "failed": failed}


def restore_trash_item(trash_id: Any) -> dict[str, Any]:
    trash_id = str(trash_id)
    restored_to = "original"
    restored_parent: str | None = None
    with _database_lock:
        with open_state_database() as connection:
            row = connection.execute("SELECT * FROM trash_items WHERE trash_id=?", (trash_id,)).fetchone()
            if not row:
                raise ValueError("回收站条目不存在")
            payload = _decode_object(row["payload"], "回收站中的数据损坏")
            kind = str(row["kind"])
            if kind == "project":
                project = payload
                if project.get("id") is None:
                    raise ValueError("回收站中的项目缺少 ID")
                project_id = str(project["id"])
                current = connection.execute(
                    "SELECT 1 FROM projects WHERE project_id=?",
                    (project_id,),
                ).fetchone()
                if current:
                    raise StateConflictError("同名项目已经存在，请先删除现有项目")
                revision = int(row["revision"] or 0) or 1
                _upsert_project(connection, project, int(row["position"]), revision, _now())
                log_activity("restore-project", f"恢复项目「{_project_title(project)}」",
                             project_id=project_id, project_name=_project_title(project),
                             connection=connection)
            else:
                project_id = str(row["project_id"])
                project_row = connection.execute(
                    "SELECT revision FROM projects WHERE project_id=?",
                    (project_id,),
                ).fetchone()
                if not project_row:
                    raise ValueError("原项目已不存在，无法恢复任务")
                project = _read_project_from_connection(connection, project_id)
                if not project:
                    raise ValueError("原项目已不存在，无法恢复任务")
                root, revision = project
                parent_id = row["parent_id"]
                if parent_id is not None and _find_children_list(root.get("tree") or [], str(parent_id)) is None:
                    # 原位置已经不存在（父节点被删了）：恢复到"孤立任务箱"，而不是拒绝恢复
                    siblings, restored_parent = _ensure_orphan_box(root)
                    siblings.append(payload)
                    restored_to = "orphan"
                else:
                    _find_parent_and_insert(root.get("tree") or [], parent_id, payload, int(row["position"]))
                    restored_parent = str(parent_id) if parent_id is not None else None
                _upsert_project(connection, root, int(connection.execute(
                    "SELECT position FROM projects WHERE project_id=?", (project_id,)
                ).fetchone()[0]), int(revision) + 1, _now())
                log_activity("restore", f"恢复「{str(payload.get('text') or row['title'])}」",
                             project_id=project_id, project_name=_project_title(root),
                             detail={"trashId": trash_id, "restoredTo": restored_to},
                             connection=connection)
            connection.execute("DELETE FROM trash_items WHERE trash_id=?", (trash_id,))
    return {"id": trash_id, "kind": kind, "restoredTo": restored_to, "parentId": restored_parent}


def read_project_summaries() -> list[dict[str, Any]]:
    with _database_lock, open_state_database() as connection:
        rows = connection.execute(
            "SELECT summary_json,revision,archived,review_enabled,last_opened_at "
            "FROM projects ORDER BY position,project_id"
        ).fetchall()
    result = []
    for row in rows:
        summary = _decode_object(row["summary_json"], "SQLite 中的项目摘要损坏")
        summary["_revision"] = int(row["revision"])
        # summary_json 可能是旧版本程序写的（缺后来才加的字段），所以归档/复习状态
        # 一律以列为准覆盖：否则 /api/projects 里 archived 会缺失，
        # 前端"已归档"筛选和归档按钮就会失效。
        summary["archived"] = bool(row["archived"])
        summary["reviewEnabled"] = None if row["review_enabled"] is None else bool(row["review_enabled"])
        summary["lastOpenedAt"] = str(row["last_opened_at"] or "")
        result.append(summary)
    return result


def review_counts(today: str | None = None) -> dict[str, dict[str, int]]:
    """每个项目"已完成且排了复习"的任务数：今天到期 / 已逾期。

    只统计已完成且 review_due 非空的任务；返回 {project_id: {"today": n, "overdue": n}}。
    只有"未来复习"的项目也会出现，两个计数都是 0（保持前端原来的口径）。

    以前这里把每一行都取回 Python 再逐行分桶：30 个项目 × 1 万任务
    （306,823 节点 / 75,000 条待复习）实测 94.75 ms，而它只是给卡片徽标算两个数字。
    现在一条 GROUP BY 只回"每个项目一行"。
    """
    today = (today or date.today().isoformat())
    with _database_lock, open_state_database() as connection:
        rows = connection.execute(
            "SELECT project_id, "
            "SUM(CASE WHEN review_due < ? THEN 1 ELSE 0 END) AS overdue, "
            "SUM(CASE WHEN review_due = ? THEN 1 ELSE 0 END) AS today "
            "FROM nodes WHERE type='item' AND completed=1 AND review_due<>'' "
            "GROUP BY project_id",
            (today, today),
        ).fetchall()
    return {
        str(row["project_id"]): {"today": int(row["today"] or 0), "overdue": int(row["overdue"] or 0)}
        for row in rows
    }


MAX_REVIEW_QUEUE = 500
MAX_SEARCH_RESULTS = 200


def list_review_queue(today: str | None = None, limit: int = MAX_REVIEW_QUEUE) -> dict[str, Any]:
    """跨项目复习队列：只读 nodes 表，不再要求前端把每个项目的整棵树都拉下来。

    返回 {today, due, future, total, truncated, limit}；due/future 的条目字段与
    前端原来的本地计算结果一致（projectId/projectName/nodeId/text/due/learning/path/ancestorIds）。
    """
    reference = clean_due_date(today) or date.today().isoformat()
    try:
        wanted = int(limit)
    except (TypeError, ValueError):
        wanted = MAX_REVIEW_QUEUE
    wanted = max(1, min(MAX_REVIEW_QUEUE, wanted))
    with _database_lock, open_state_database() as connection:
        names = {
            str(row["project_id"]): str(row["name"])
            for row in connection.execute("SELECT project_id,name FROM projects WHERE archived=0")
        }
        rows = connection.execute(
            "SELECT project_id,node_id,parent_id,text,review_due,review_learning,completed_at "
            "FROM nodes WHERE type='item' AND completed=1 AND review_due<>'' "
            "ORDER BY review_due, project_id, position LIMIT ?",
            (wanted + 1,),
        ).fetchall()
        # 只为真正会返回的行建路径（原来这里会把全库节点读进来算一遍）
        locations = _node_locations(connection, rows[:wanted])
    truncated = len(rows) > wanted
    due_items: list[dict[str, Any]] = []
    future_items: list[dict[str, Any]] = []
    for row in rows[:wanted]:
        project_id = str(row["project_id"])
        if project_id not in names:
            continue
        node_id = str(row["node_id"])
        location = locations.get((project_id, node_id)) or {}
        item = {
            "projectId": project_id,
            "projectName": names[project_id],
            "nodeId": node_id,
            "text": str(row["text"] or ""),
            "due": str(row["review_due"]),
            "learning": bool(row["review_learning"]),
            "completedAt": str(row["completed_at"] or ""),
            "path": location.get("path", ""),
            "ancestorIds": list(location.get("ancestorIds", [])),
        }
        (due_items if item["due"] <= reference else future_items).append(item)
    return {
        "today": reference,
        "due": due_items,
        "future": future_items,
        "total": len(due_items) + len(future_items),
        "truncated": truncated,
        "limit": wanted,
    }


def search_everything(query: Any, limit: int = 100) -> dict[str, Any]:
    """跨项目搜索：SQL LIKE + 递归 CTE（命中的父节点连带其后代）。

    和前端 collectSearchMatches 的口径一致：项目命中看 name/description，
    节点命中看任务文本或其路径上的任意分组名（搜"第1周"能列出该周的任务）。
    这些规模下 LIKE 全表扫描是亚毫秒级，不需要 FTS5（见第六批 item 4 的实测数据）。
    """
    text = str(query or "").strip()
    try:
        wanted = int(limit)
    except (TypeError, ValueError):
        wanted = 100
    wanted = max(1, min(MAX_SEARCH_RESULTS, wanted))
    if not text:
        return {"query": "", "results": [], "total": 0, "truncated": False, "limit": wanted}
    pattern = "%" + text.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with _database_lock, open_state_database() as connection:
        all_names = {
            str(row["project_id"]): str(row["name"])
            for row in connection.execute("SELECT project_id,name FROM projects")
        }
        project_rows = connection.execute(
            "SELECT project_id,name,description FROM projects WHERE archived=0 "
            "AND (lower(name) LIKE ? ESCAPE '\\' OR lower(description) LIKE ? ESCAPE '\\') "
            "ORDER BY position LIMIT ?",
            (pattern, pattern, wanted + 1),
        ).fetchall()
        node_rows = connection.execute(
            """WITH RECURSIVE hit(project_id,node_id) AS (
                   SELECT project_id,node_id FROM nodes WHERE lower(text) LIKE ? ESCAPE '\\'
                   UNION
                   SELECT child.project_id,child.node_id FROM nodes child
                     JOIN hit ON child.project_id=hit.project_id AND child.parent_id=hit.node_id
               )
               SELECT node.project_id,node.node_id,node.parent_id,node.text,node.type,node.position
                 FROM nodes node
                 JOIN hit ON hit.project_id=node.project_id AND hit.node_id=node.node_id
                ORDER BY node.project_id, node.position, node.node_id LIMIT ?""",
            (pattern, wanted + 1),
        ).fetchall()
        # 只为命中的行建路径（原来这里会把全库节点读进来算一遍）
        locations = _node_locations(connection, node_rows)
    results: list[dict[str, Any]] = []
    for row in project_rows:
        project_id = str(row["project_id"])
        results.append({
            "kind": "project",
            "projectId": project_id,
            "label": str(row["name"]),
            "detail": str(row["description"] or "") or "项目摘要",
        })
    for row in node_rows:
        project_id = str(row["project_id"])
        node_id = str(row["node_id"])
        location = locations.get((project_id, node_id)) or {}
        results.append({
            "kind": "node",
            "projectId": project_id,
            "nodeId": node_id,
            "label": str(row["text"] or "未命名任务"),
            "detail": location.get("path") or all_names.get(project_id) or "项目任务",
            "ancestorIds": list(location.get("ancestorIds", [])),
        })
    truncated = len(results) > wanted
    return {"query": text, "results": results[:wanted], "total": len(results[:wanted]),
            "truncated": truncated, "limit": wanted}


def read_project(project_id: Any) -> tuple[dict[str, Any], int] | None:
    with _database_lock, open_state_database() as connection:
        return _read_project_from_connection(connection, str(project_id))


# JSON 导出附带的 5 张复习表的（导出键 → 表名、稳定排序键）映射。排序键都用主键：
# 行序不定会让"导出内容比对"变成随机假阴性。键名与前端 camelCase 习惯保持一致。
REVIEW_EXPORT_TABLES: dict[str, tuple[str, str]] = {
    "points": ("review_points", "code"),
    "pointTasks": ("review_point_tasks", "code,task_id,project_id"),
    "states": ("review_states", "code"),
    "attempts": ("review_attempts", "id"),
    "sessions": ("review_sessions", "id"),
}


def _camel_case_column(column: str) -> str:
    head, *rest = str(column).split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


# 导入侧：导出键（camelCase；JSON 列在导出时已去掉 Json 后缀）→ 库中的真实列名。
# 只列已知列，绝不用 payload 里的键去拼 SQL（列名必须可枚举、可审计）。
REVIEW_IMPORT_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "points": (
        ("code", "code"), ("title", "title"), ("minutes", "minutes"), ("module", "module"),
        ("level", "level"), ("origin", "origin"), ("content", "content_json"),
        ("createdAt", "created_at"), ("updatedAt", "updated_at"),
    ),
    "pointTasks": (
        ("code", "code"), ("taskId", "task_id"), ("projectId", "project_id"),
        ("relation", "relation"),
    ),
    "states": (
        ("code", "code"), ("due", "due"), ("intervalDays", "interval_days"),
        ("streak", "streak"), ("lapses", "lapses"), ("lastGrade", "last_grade"),
        ("weak", "weak"), ("lastReviewedAt", "last_reviewed_at"),
    ),
    "attempts": (
        ("id", "id"), ("code", "code"), ("taskId", "task_id"), ("projectId", "project_id"),
        ("questionType", "question_type"), ("grade", "grade"), ("answer", "answer"),
        ("aiVerdict", "ai_verdict"), ("reviewedOn", "reviewed_on"), ("durationMs", "duration_ms"),
        ("sessionId", "session_id"), ("createdAt", "created_at"),
    ),
    "sessions": (
        ("id", "id"), ("startedAt", "started_at"), ("finishedAt", "finished_at"),
        ("planned", "planned"), ("answered", "answered"), ("gradeCounts", "grade_counts_json"),
        ("durationMs", "duration_ms"),
    ),
}


def _review_column_defaults(connection: sqlite3.Connection, table: str) -> dict[str, Any]:
    """按库里的 DDL 给"payload 里没带的列"兜底。

    旧快照可能缺后来新增的列；给默认值而不是整行报错，导入才是向后兼容的。
    """
    defaults: dict[str, Any] = {}
    for row in connection.execute(f"PRAGMA table_info({table})").fetchall():
        name = str(row[1])
        declared = row[4]
        if declared is None:
            defaults[name] = 0 if str(row[2]).upper().startswith("INT") else ""
        elif str(declared).startswith("'") and str(declared).endswith("'"):
            defaults[name] = str(declared)[1:-1]
        else:
            try:
                defaults[name] = int(str(declared))
            except ValueError:
                defaults[name] = str(declared)
    return defaults


def _review_import_value(item: dict[str, Any], name: str, column: str,
                         defaults: dict[str, Any]) -> Any:
    value = item[name] if name in item else defaults.get(column, "")
    if column.endswith("_json"):
        # 导出时 JSON 列被解析成对象（content/gradeCounts）；写回库里必须是 JSON 文本。
        if isinstance(value, str):
            return value
        return "{}" if value is None else json.dumps(value, ensure_ascii=False)
    return value


def _read_review_export(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """把 5 张复习表读成 JSON 可序列化的快照（列名转 camelCase，JSON 文本列解析成对象）。"""
    review: dict[str, list[dict[str, Any]]] = {}
    for key, (table, order_by) in REVIEW_EXPORT_TABLES.items():
        rows = connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item: dict[str, Any] = {}
            for column in row.keys():
                name = _camel_case_column(column)
                value = row[column]
                if column.endswith("_json"):
                    # 落库时是 JSON 文本（content_json / grade_counts_json）；导出成对象后
                    # 人看得懂，将来的导入侧也不用再解一层转义字符串。
                    if name.endswith("Json"):
                        name = name[: -len("Json")]
                    try:
                        value = json.loads(value) if value else {}
                    except (TypeError, ValueError):
                        value = row[column]
                item[name] = value
            items.append(item)
        review[key] = items
    return review


def export_projects_snapshot() -> dict[str, Any]:
    """导出全部项目的完整快照，形状与前端"导入备份"（/api/import）兼容。

    刻意逐个读取完整项目，而不是复用 read_project_summaries() 的摘要：
    摘要里的 tree 是空的，直接导出会让未打开的项目变成空壳，导入后丢数据。
    整个导出必须在一把锁、一个连接里完成：分成两次加锁的话，中间新建的项目不会出现在
    导出结果里，而导入是"整体替换"语义，用这份 JSON 恢复就会把它删掉。

    顶层还额外带一个 `review` 键：5 张复习表（points / pointTasks / states / attempts /
    sessions）的快照。不加它的话，用户拿"导出 JSON → 导入"做迁移会静默丢掉复习进度与作答
    历史（规格 §9/§10.7 把"导出往返覆盖新增表"列为验收项）。`review` 是附加信息：
    前端 extractProjects 只消费 `projects`，/api/import 除了 `projects` 之外还会消费
    `review`（见 import_review_snapshot），旧快照没有这个键时原样跳过。
    因此 `schemaVersion` 必须原样保持 EXPORT_SCHEMA_VERSION，绝不能为了带上 review 而递增。
    """
    projects: list[dict[str, Any]] = []
    with _database_lock, open_state_database() as connection:
        rows = connection.execute(
            "SELECT project_id FROM projects ORDER BY position,project_id"
        ).fetchall()
        for row in rows:
            result = _read_project_from_connection(connection, str(row["project_id"]))
            if result:
                projects.append(result[0])
        review = _read_review_export(connection)
    return {
        "schemaVersion": EXPORT_SCHEMA_VERSION,
        "exportedAt": datetime.now().isoformat(timespec="seconds"),
        "projects": projects,
        "review": review,
    }


def import_review_snapshot(review: Any) -> dict[str, int]:
    """把 export_projects_snapshot() 附带的 `review` 快照 upsert 回 5 张复习表。

    规格 §10.7：JSON 导出的复习表必须在导入侧闭环，否则"导出 → 导入"的跨机迁移会静默
    丢复习进度与作答历史。语义是**只增不删**——payload 里出现的行按主键 upsert，没出现
    的行保持不动；整个 `review` 键缺失（旧快照）时直接跳过该表，不报错、不删数据。
    JSON 列（content / gradeCounts）在导出时已被解析成对象，这里按库里的列形态写回 JSON 文本。
    事务/锁沿用 storage 里其他写路径的风格：state_lock() + open_state_database() + BEGIN IMMEDIATE。
    """
    counts = {key: 0 for key in REVIEW_EXPORT_TABLES}
    if review is None:
        return counts
    if not isinstance(review, dict):
        raise ValueError("review 必须是对象")
    with state_lock(), open_state_database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for key, (table, primary_key) in REVIEW_EXPORT_TABLES.items():
            rows = review.get(key)
            if rows is None:
                # 某个键缺失就跳过该表：旧快照只有部分表也不能因此报错。
                continue
            if not isinstance(rows, list):
                raise ValueError(f"review.{key} 必须是数组")
            columns = REVIEW_IMPORT_COLUMNS[key]
            defaults = _review_column_defaults(connection, table)
            primary_columns = primary_key.split(",")
            column_sql = ",".join(column for _, column in columns)
            placeholders = ",".join("?" for _ in columns)
            updates = ",".join(
                f"{column}=excluded.{column}"
                for _, column in columns if column not in primary_columns)
            statement = (
                f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) "
                f"ON CONFLICT({primary_key}) DO UPDATE SET {updates}"
            )
            for item in rows:
                if not isinstance(item, dict):
                    raise ValueError(f"review.{key} 的每一项都必须是对象")
                values = [_review_import_value(item, name, column, defaults)
                          for name, column in columns]
                connection.execute(statement, values)
                counts[key] += 1
    return counts


# ---------------------------------------------------------------------------
# 导出（Markdown / CSV）、项目模板、导入预览与三种导入模式（第五批 7~10）
# ---------------------------------------------------------------------------

EXPORT_FORMATS = ("json", "markdown", "csv")


def _node_meta_suffix(node: dict[str, Any]) -> str:
    """任务的一行元数据后缀（Markdown/CSV 共用同一套字段名）。"""
    parts: list[str] = []
    priority = {"high": "高", "mid": "中", "low": "低"}.get(str(node.get("priority") or ""), "")
    if priority:
        parts.append(f"优先级 {priority}")
    if node.get("dueDate"):
        parts.append(f"截止 {node['dueDate']}")
    if node.get("estimateMinutes"):
        parts.append(f"预计 {int(node['estimateMinutes'])} 分钟")
    repeat = clean_repeat(node.get("repeat"))
    if repeat:
        parts.append("周期 " + format_repeat_text(repeat))
    if node.get("optional"):
        parts.append("选做")
    if node.get("assessmentRequired"):
        parts.append("需验收")
    return "（" + " · ".join(parts) + "）" if parts else ""


def format_repeat_text(rule: dict[str, Any]) -> str:
    freq = str(rule.get("freq"))
    if freq == "daily":
        interval = int(rule.get("interval") or 1)
        return "每天" if interval <= 1 else f"每 {interval} 天"
    if freq == "weekday":
        return "每个工作日"
    if freq == "weekly":
        names = ["日", "一", "二", "三", "四", "五", "六"]
        weekday = int(rule.get("weekday") or 0) % 7
        return f"每周{names[weekday]}"
    if freq == "monthly":
        return f"每月 {int(rule.get('day') or 1)} 日"
    return freq


def export_markdown() -> str:
    """人看的导出：按 周 → 单元 → 任务 分层，任务带复选框与元数据后缀。"""
    snapshot = export_projects_snapshot()
    lines: list[str] = ["# 学习计划导出", "",
                        f"导出时间：{snapshot['exportedAt']}　共 {len(snapshot['projects'])} 个项目", ""]
    for project in snapshot["projects"]:
        lines.append(f"## {project.get('name') or '未命名项目'}")
        description = str(project.get("description") or "").strip()
        if description:
            lines.append("")
            lines.append(f"> {description}")
        lines.append("")
        for week in project.get("tree") or []:
            lines.append(f"### {week.get('text') or '未命名'}{_node_meta_suffix(week)}")
            for day in week.get("children") or []:
                lines.append(f"#### {day.get('text') or '未命名'}{_node_meta_suffix(day)}")
                items = day.get("children") or []
                if not items:
                    lines.append("- （没有任务）")
                for node in items:
                    box = "x" if node.get("completed") else " "
                    line = f"- [{box}] {node.get('text') or '未命名'}{_node_meta_suffix(node)}"
                    if node.get("tags"):
                        line += " " + " ".join(f"#{tag}" for tag in node["tags"])
                    lines.append(line)
                    note = str(node.get("note") or "").strip()
                    if note:
                        for note_line in note.splitlines():
                            lines.append(f"      > {note_line}")
                    for link in node.get("links") or []:
                        label = str(link.get("label") or "链接")
                        lines.append(f"      - [{label}]({link.get('url')})")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


CSV_COLUMNS = ["项目", "周", "单元", "任务", "类型", "完成", "选做", "需验收", "优先级", "截止日期",
               "预计分钟", "标签", "备注", "链接", "周期", "创建时间", "完成时间"]


def export_csv() -> str:
    """表格导出：一行一个节点（任务为主，周/单元也各占一行便于透视）。UTF-8 BOM 便于 Excel 打开。"""
    import csv as _csv
    import io as _io
    snapshot = export_projects_snapshot()
    buffer = _io.StringIO()
    writer = _csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for project in snapshot["projects"]:
        project_name = str(project.get("name") or "未命名项目")
        for week in project.get("tree") or []:
            writer.writerow([project_name, week.get("text") or "", "", "", "week",
                             "是" if week.get("completed") else "否", "", "", "", "", "", "", "", "", "",
                             week.get("createdAt") or "", ""])
            for day in week.get("children") or []:
                writer.writerow([project_name, week.get("text") or "", day.get("text") or "", "", "day",
                                 "是" if day.get("completed") else "否", "", "", "", "", "", "", "", "", "",
                                 day.get("createdAt") or "", ""])
                for node in day.get("children") or []:
                    writer.writerow([
                        project_name,
                        week.get("text") or "",
                        day.get("text") or "",
                        node.get("text") or "",
                        node.get("type") or "item",
                        "是" if node.get("completed") else "否",
                        "是" if node.get("optional") else "",
                        "是" if node.get("assessmentRequired") else "",
                        node.get("priority") or "",
                        node.get("dueDate") or "",
                        int(node.get("estimateMinutes") or 0) or "",
                        "、".join(node.get("tags") or []),
                        str(node.get("note") or "").replace("\r\n", "\n"),
                        " ".join(str(link.get("url") or "") for link in (node.get("links") or [])),
                        format_repeat_text(clean_repeat(node.get("repeat"))) if node.get("repeat") else "",
                        node.get("createdAt") or "",
                        node.get("completedAt") or "",
                    ])
    return "\ufeff" + buffer.getvalue()


BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "builtin-8-week-review",
        "name": "8 周系统复习",
        "description": "每周一个主题：概念 → 练习 → 复盘，适合把一门课从头过一遍。",
        "builtin": True,
        "tree": [
            {"type": "week", "text": f"第{n}周：主题", "children": [
                {"type": "day", "text": "单元1：概念与原理", "children": [
                    {"type": "item", "text": "用自己的话解释本周核心概念"},
                    {"type": "item", "text": "画一张原理图 / 流程图"},
                ]},
                {"type": "day", "text": "单元2：动手练习", "children": [
                    {"type": "item", "text": "完成一个最小可运行示例"},
                    {"type": "item", "text": "给关键逻辑补 2 条测试"},
                ]},
                {"type": "day", "text": "单元3：复盘", "children": [
                    {"type": "item", "text": "整理易错点清单"},
                    {"type": "item", "text": "写 3 句话总结本周收获"},
                ]},
            ]} for n in range(1, 9)
        ],
    },
    {
        "id": "builtin-debug-drill",
        "name": "排错四步训练",
        "description": "复现 → 定位 → 修复 → 回归，训练排错肌肉记忆。",
        "builtin": True,
        "tree": [
            {"type": "week", "text": "第1周：排错基本功", "children": [
                {"type": "day", "text": "单元1：刻意练习", "children": [
                    {"type": "item", "text": "写下可复现的最短步骤"},
                    {"type": "item", "text": "用二分法定位到具体函数"},
                    {"type": "item", "text": "修复并说明根因"},
                    {"type": "item", "text": "补一条能挡住这个 bug 的测试"},
                ]},
            ]},
        ],
    },
]


def _template_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id")),
        "name": str(entry.get("name")),
        "description": str(entry.get("description") or ""),
        "builtin": bool(entry.get("builtin")),
        "tree": entry.get("tree") or [],
    }


def list_templates() -> list[dict[str, Any]]:
    templates = [_template_payload(entry) for entry in BUILTIN_TEMPLATES]
    with _database_lock, open_state_database() as connection:
        rows = connection.execute(
            "SELECT template_id,name,description,payload,builtin FROM project_templates "
            "ORDER BY builtin DESC, name"
        ).fetchall()
    for row in rows:
        stored = _decode_object(row["payload"], "模板数据损坏")
        templates.append({
            "id": str(row["template_id"]),
            "name": str(row["name"]),
            "description": str(row["description"] or ""),
            "builtin": bool(row["builtin"]),
            "tree": stored.get("tree") or [],
        })
    return templates


def save_project_as_template(project_id: Any, name: Any = None, description: Any = "") -> dict[str, Any]:
    """把现有项目存成模板（只存结构，不存完成状态/AI 历史/复习）。"""
    project_key = str(project_id)
    with _database_lock, open_state_database() as connection:
        result = _read_project_from_connection(connection, project_key)
        if not result:
            raise ValueError("项目不存在")
        project, _revision = result
        template_name = str(name or "").strip()[:60] or f"{_project_title(project)} 模板"
        existing = connection.execute(
            "SELECT template_id FROM project_templates WHERE name=?", (template_name,)
        ).fetchone()
        tree = []
        for node in project.get("tree") or []:
            clone = _refresh_all_ids(node)
            clone["text"] = str(node.get("text") or "未命名")
            for entry in _walk_nodes([clone]):
                entry["completed"] = False
                entry["completedAt"] = None
                entry["assessment"] = None
                entry["assessmentHistory"] = 0
                entry.pop("review", None)
            tree.append(clone)
        payload = _json({"tree": tree})
        template_id = str(existing["template_id"]) if existing else str(uuid.uuid4())
        now = _now()
        if existing:
            connection.execute(
                "UPDATE project_templates SET payload=?,description=? WHERE template_id=?",
                (payload, str(description or "")[:200], template_id))
        else:
            connection.execute(
                "INSERT INTO project_templates(template_id,name,description,payload,created_at,builtin) "
                "VALUES(?,?,?,?,?,0)",
                (template_id, template_name, str(description or "")[:200], payload, now))
        log_activity("template", f"把「{_project_title(project)}」存为模板「{template_name}」",
                     project_id=project_key, project_name=_project_title(project),
                     connection=connection)
    return {"id": template_id, "name": template_name, "description": str(description or ""),
            "builtin": False, "tree": tree}


def delete_template(template_id: Any) -> bool:
    template_key = str(template_id)
    if any(entry["id"] == template_key for entry in BUILTIN_TEMPLATES):
        raise ValueError("内置模板不能删除")
    with _database_lock, open_state_database() as connection:
        cursor = connection.execute("DELETE FROM project_templates WHERE template_id=?", (template_key,))
    return cursor.rowcount > 0


def create_project_from_template(template_id: Any, name: Any = None) -> dict[str, Any]:
    template_key = str(template_id)
    template = next((entry for entry in list_templates() if entry["id"] == template_key), None)
    if template is None:
        raise ValueError("模板不存在")
    project = {
        "id": str(uuid.uuid4()),
        "name": str(name or "").strip()[:200] or template["name"],
        "description": str(template.get("description") or ""),
        "createdAt": date.today().isoformat(),
        "assessmentEnabled": False,
        "reviewEnabled": False,
        "archived": False,
        "tree": [_refresh_all_ids(node) for node in template.get("tree") or []],
    }
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            position = connection.execute("SELECT COALESCE(MAX(position),-1)+1 FROM projects").fetchone()[0]
            _upsert_project(connection, project, int(position), 1, _now())
            log_activity("template", f"用模板「{template['name']}」创建项目「{project['name']}」",
                         project_id=project["id"], project_name=project["name"],
                         detail={"templateId": template_key}, connection=connection)
    return {"project": project, "templateId": template_key}


def count_node_progress(nodes: Any) -> tuple[int, int]:
    items = [node for node in _walk_nodes(nodes) if str(node.get("type")) == "item"]
    return len(items), len([node for node in items if node.get("completed")])


def _node_index_by_id(nodes: Any) -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in _walk_nodes(nodes)}


def find_import_duplicate_ids(projects: list[Any]) -> list[str]:
    """导入前的重复 ID 检查（返回人类可读的问题列表；空列表=没问题）。"""
    problems: list[str] = []
    seen_projects: dict[str, str] = {}
    for project in projects:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        name = str(project.get("name") or "未命名项目")
        if project_id:
            if project_id in seen_projects:
                problems.append(f"重复的项目 ID：{project_id}（“{seen_projects[project_id]}”与“{name}”）")
            else:
                seen_projects[project_id] = name
        seen_nodes: set[str] = set()
        stack = [(node, name) for node in (project.get("tree") or []) if isinstance(node, dict)]
        while stack:
            node, path = stack.pop()
            node_id = str(node.get("id") or "")
            label = str(node.get("text") or node.get("type") or "未命名")
            node_path = f"{path} / {label}"
            if node_id:
                if node_id in seen_nodes:
                    problems.append(f"重复的节点 ID：{node_path}（ID {node_id}）")
                seen_nodes.add(node_id)
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    stack.append((child, node_path))
    return problems


def preview_import(projects: Any, mode: str = "replace", *, keep_ai_history: bool = True) -> dict[str, Any]:
    """导入前的差异报告：新增/更新/删除、重复 ID、覆盖内容与 AI 历史处理方式。"""
    if not isinstance(projects, list):
        raise ValueError("导入数据格式不正确")
    if mode not in {"replace", "merge", "new"}:
        raise ValueError("不支持的导入模式")
    duplicate_problems = find_import_duplicate_ids(projects)
    incoming_ids: list[str] = []
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise ValueError(f"导入的第 {index + 1} 项不是项目对象")
        incoming_ids.append(str(project.get("id") or ""))
    existing = {entry["id"]: entry for entry in read_project_summaries()}

    new_projects: list[dict[str, Any]] = []
    updated_projects: list[dict[str, Any]] = []
    unchanged_projects: list[dict[str, Any]] = []
    removed_projects: list[dict[str, Any]] = []
    totals = {"addedNodes": 0, "updatedNodes": 0, "keptLocalOnlyNodes": 0, "deletedNodes": 0}
    ai_nodes = 0
    review_nodes = 0

    for project in projects:
        incoming = dict(project)
        pid = str(incoming.get("id") or "")
        local = existing.get(pid)
        item_count, completed_count = count_node_progress(incoming.get("tree"))
        ai_nodes += len([node for node in _walk_nodes(incoming.get("tree"))
                         if isinstance(node.get("assessment"), dict) and node.get("assessment")])
        review_nodes += len([node for node in _walk_nodes(incoming.get("tree")) if node.get("review")])
        summary = {
            "id": pid,
            "name": str(incoming.get("name") or "未命名项目"),
            "itemCount": item_count,
            "completedCount": completed_count,
        }
        if mode == "new" or local is None:
            summary["duplicateName"] = any(
                entry["name"] == summary["name"] and entry["id"] != pid for entry in existing.values())
            new_projects.append(summary)
            continue
        # merge / replace 且本地已有同 ID 项目
        with _database_lock, open_state_database() as connection:
            stored = _read_project_from_connection(connection, pid)
        local_tree = stored[0].get("tree") if stored else []
        local_index = _node_index_by_id(local_tree)
        incoming_index = _node_index_by_id(incoming.get("tree"))
        added = len([nid for nid in incoming_index if nid not in local_index])
        updated = len([nid for nid in incoming_index if nid in local_index])
        kept_local = len([nid for nid in local_index if nid not in incoming_index])
        totals["addedNodes"] += added
        totals["updatedNodes"] += updated
        totals["keptLocalOnlyNodes"] += kept_local
        if mode == "replace":
            totals["deletedNodes"] += len([nid for nid in local_index if nid not in incoming_index])
        summary.update({"addedNodes": added, "updatedNodes": updated, "keptLocalOnlyNodes": kept_local})
        (unchanged_projects if added == 0 and updated == 0 else updated_projects).append(summary)

    if mode == "replace":
        incoming_set = {pid for pid in incoming_ids if pid}
        removed_projects = [
            {"id": entry["id"], "name": entry["name"]}
            for entry in existing.values() if entry["id"] not in incoming_set
        ]
        totals["deletedNodes"] = sum(
            len(_walk_nodes((read_project(entry["id"]) or ({}, 0))[0].get("tree") or []))
            for entry in removed_projects
        )
    return {
        "mode": mode,
        "keepAiHistory": bool(keep_ai_history),
        "duplicates": duplicate_problems,
        "newProjects": new_projects,
        "updatedProjects": updated_projects,
        "unchangedProjects": unchanged_projects,
        "removedProjects": removed_projects,
        "totals": totals,
        "aiHistory": {
            "nodesWithAssessment": ai_nodes,
            "nodesWithReview": review_nodes,
            "policy": "保留" if keep_ai_history else "导入时清空 AI 验收历史与复习安排",
        },
    }


def _merge_tree(local: list[dict[str, Any]], incoming: list[dict[str, Any]],
                *, keep_ai_history: bool = True) -> dict[str, int]:
    """按节点 ID 合并：同 ID 用新内容覆盖（保留顺序），新 ID 追加，本地独有的保留不删。

    keep_ai_history=False 时，被覆盖的节点也要清掉验收/复习——否则"导入时清空 AI 历史"
    对合并模式只在本地没有该节点时才生效，看起来像没生效。
    """
    added = updated = 0
    local_index = _node_index_by_id(local)

    def _merge_into(local_nodes: list[dict[str, Any]], incoming_nodes: list[dict[str, Any]]) -> None:
        nonlocal added, updated
        for node in incoming_nodes or []:
            node_id = str(node.get("id") or "")
            if not node_id:
                continue
            target = local_index.get(node_id)
            if target is not None:
                children = target.get("children") or []
                for key, value in node.items():
                    if key == "children":
                        continue
                    target[key] = value
                if not keep_ai_history:
                    target["assessment"] = None
                    target["assessmentHistory"] = 0
                    target.pop("review", None)
                _merge_into(children, node.get("children") or [])
                updated += 1
            else:
                clone = json.loads(json.dumps(node))
                if not isinstance(clone.get("children"), list):
                    clone["children"] = []
                local_nodes.append(clone)
                local_index[node_id] = clone
                added += 1
                _merge_into(clone["children"], node.get("children") or [])

    _merge_into(local, incoming)
    return {"addedNodes": added, "updatedNodes": updated}


def import_projects(projects: Any, mode: str = "replace", *, keep_ai_history: bool = True) -> dict[str, Any]:
    """按模式导入：replace（整体替换）/ merge（合并进现有项目）/ new（都当新项目）。"""
    if not isinstance(projects, list) or not projects:
        raise ValueError("没有可导入的项目")
    if mode not in {"replace", "merge", "new"}:
        raise ValueError("不支持的导入模式")
    preview = preview_import(projects, mode, keep_ai_history=keep_ai_history)
    if preview["duplicates"]:
        raise ValueError("导入被拒绝：发现重复 ID——" + preview["duplicates"][0])
    prepared = [json.loads(json.dumps(project)) for project in projects]
    if not keep_ai_history:
        for project in prepared:
            for node in _walk_nodes(project.get("tree") if isinstance(project, dict) else []):
                node["assessment"] = None
                node["assessmentHistory"] = 0
                node.pop("review", None)
    if mode == "replace":
        replace_projects(prepared, pre_backup=False)
        log_activity("import", f"整体替换导入 {len(prepared)} 个项目",
                     detail={"mode": mode, "projects": len(prepared), "preview": preview["totals"]})
    elif mode == "new":
        created = []
        with _database_lock:
            with open_state_database() as connection:
                connection.execute("BEGIN IMMEDIATE")
                position = connection.execute("SELECT COALESCE(MAX(position),-1)+1 FROM projects").fetchone()[0]
                for project in prepared:
                    project = dict(project)
                    project["id"] = str(uuid.uuid4())
                    project["createdAt"] = str(project.get("createdAt") or date.today().isoformat())
                    _upsert_project(connection, project, int(position), 1, _now())
                    position += 1
                    created.append({"id": project["id"], "name": project.get("name")})
                log_activity("import", f"导入为新项目 {len(created)} 个",
                             detail={"mode": mode, "projects": created}, connection=connection)
    else:  # merge：只增不删
        totals = {"addedNodes": 0, "updatedNodes": 0, "newProjects": 0}
        with _database_lock:
            with open_state_database() as connection:
                connection.execute("BEGIN IMMEDIATE")
                for project in prepared:
                    pid = str(project.get("id") or "")
                    existing = _read_project_from_connection(connection, pid) if pid else None
                    if not existing:
                        position = connection.execute(
                            "SELECT COALESCE(MAX(position),-1)+1 FROM projects").fetchone()[0]
                        _upsert_project(connection, project, int(position), 1, _now())
                        totals["newProjects"] += 1
                        continue
                    local_project, revision = existing
                    counts = _merge_tree(local_project.setdefault("tree", []), project.get("tree") or [],
                                           keep_ai_history=keep_ai_history)
                    totals["addedNodes"] += counts["addedNodes"]
                    totals["updatedNodes"] += counts["updatedNodes"]
                    local_project["name"] = str(project.get("name") or local_project.get("name"))
                    local_project["description"] = str(project.get("description") or local_project.get("description") or "")
                    _upsert_project(connection, local_project,
                                    _project_position(connection, pid), int(revision) + 1, _now())
                log_activity("import", f"合并导入：新增 {totals['addedNodes']} 个任务、更新 {totals['updatedNodes']} 个",
                             detail={"mode": mode, **totals}, connection=connection)
    return {"mode": mode, "preview": preview, "projects": read_project_summaries()}


def auto_archive_projects(days: int | None = None) -> dict[str, Any]:
    """把"所有任务都完成、且很久没动过"的项目自动归档（可在设置里关掉）。"""
    archived: list[dict[str, str]] = []
    with _database_lock:
        with open_state_database() as connection:
            settings = read_app_settings(connection)
            if days is None:
                if not settings["autoArchiveEnabled"]:
                    return {"archived": [], "skipped": "autoArchiveEnabled=false"}
                days = int(settings["autoArchiveDays"])
            cutoff = (datetime.now() - timedelta(days=max(1, int(days)))).isoformat(timespec="seconds")
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT project_id,position,revision,updated_at FROM projects "
                "WHERE archived=0 AND project_id<>? AND updated_at<>'' AND updated_at<? "
                "ORDER BY position",
                (INBOX_PROJECT_ID, cutoff),
            ).fetchall()
            for row in rows:
                project_id = str(row["project_id"])
                if project_id in {"inbox"}:
                    continue
                result = _read_project_from_connection(connection, project_id)
                if not result:
                    continue
                project, revision = result
                total, completed = count_node_progress(project.get("tree"))
                if total == 0 or completed < total:
                    continue
                project["archived"] = True
                _upsert_project(connection, project, int(row["position"]), int(revision) + 1, _now())
                archived.append({"id": project_id, "name": _project_title(project)})
                log_activity("auto-archive", f"自动归档已完成项目「{_project_title(project)}」",
                             project_id=project_id, project_name=_project_title(project),
                             detail={"days": int(days)}, connection=connection)
    return {"archived": archived, "days": int(days)}


def write_project(project: dict[str, Any], expected_revision: int | None) -> tuple[int, dict[str, Any]]:
    stored = {key: value for key, value in project.items() if not str(key).startswith("_")}
    encoded = _json(stored).encode("utf-8")
    if len(encoded) > MAX_PROJECT_PAYLOAD_BYTES:
        raise ValueError("单个项目数据已超过 50 MB，请先导出备份后清理该项目的旧验收记录")
    if stored.get("id") is None:
        raise ValueError("项目缺少 ID")
    project_id = str(stored["id"])
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision,position FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if row:
                current_revision = int(row["revision"])
                if expected_revision is None or expected_revision != current_revision:
                    raise StateConflictError(f"项目已被其他页面更新（当前版本 {current_revision}）")
                position = int(row["position"])
            else:
                if expected_revision not in {None, 0}:
                    raise StateConflictError("项目已经被删除，请刷新页面后重试")
                current_revision = 0
                position = int(connection.execute("SELECT COALESCE(MAX(position),-1)+1 FROM projects").fetchone()[0])
            next_revision = current_revision + 1
            now = datetime.now().isoformat(timespec="seconds")
            _upsert_project(connection, stored, position, next_revision, now)
        summary = project_summary(stored)
        summary["_revision"] = next_revision
        return next_revision, summary


def delete_project(project_id: Any, expected_revision: int) -> dict[str, Any]:
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT project_id,position,revision FROM projects WHERE project_id=?",
                (str(project_id),)
            ).fetchone()
            if not row:
                raise StateConflictError("项目已经被删除")
            if int(row["revision"]) != expected_revision:
                raise StateConflictError(f"项目已被其他页面更新（当前版本 {int(row['revision'])}）")
            project = _read_project_from_connection(connection, str(project_id))
            trash_id = ""
            if project:
                stored_project, project_revision = project
                trash_id = _new_trash_id()
                connection.execute(
                    """INSERT INTO trash_items(
                        trash_id,kind,project_id,parent_id,position,title,context,payload,deleted_at,revision
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        trash_id,
                        "project",
                        str(project_id),
                        None,
                        int(row["position"]),
                        _project_title(stored_project),
                        str(stored_project.get("description") or ""),
                        _json(stored_project),
                        _now(),
                        int(project_revision),
                    ),
                )
            connection.execute("DELETE FROM projects WHERE project_id=?", (str(project_id),))
            if project:
                log_activity("delete-project", f"删除项目「{_project_title(stored_project)}」（可在回收站恢复）",
                             project_id=str(project_id), project_name=_project_title(stored_project),
                             detail={"title": _project_title(stored_project)}, connection=connection)
    return {"trashId": trash_id, "projectId": str(project_id)}


def replace_projects(projects: list[dict[str, Any]], *, pre_backup: bool = True) -> None:
    """Atomically replace every project, used only by explicit JSON import."""
    encoded = _json(projects).encode("utf-8")
    if len(encoded) > 110 * 1024 * 1024:
        raise ValueError("导入数据过大")
    prepared: list[dict[str, Any]] = []
    seen_projects: dict[str, str] = {}
    for position, project in enumerate(projects):
        if not isinstance(project, dict):
            raise ValueError(f"导入的第 {position + 1} 项不是项目对象")
        raw_id = project.get("id")
        if raw_id is None or str(raw_id).strip() == "":
            project = {**project, "id": str(uuid.uuid4())}
            raw_id = project["id"]
        project_id = str(raw_id)
        name = str(project.get("name") or "未命名项目")
        if project_id in seen_projects:
            raise ValueError(
                f"导入中存在重复的项目 ID：{project_id}"
                f"（“{seen_projects[project_id]}”与第 {position + 1} 个项目“{name}”），已拒绝导入"
            )
        seen_projects[project_id] = name
        if len(_json(project).encode("utf-8")) > MAX_PROJECT_PAYLOAD_BYTES:
            raise ValueError("导入中存在超过 50 MB 的单个项目")
        prepared.append(project)
    with _database_lock:
        if pre_backup:
            create_manual_database_backup("before-import")
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM projects")
            now = datetime.now().isoformat(timespec="seconds")
            for position, project in enumerate(prepared):
                _upsert_project(connection, project, position, 1, now)


def database_file_size() -> int:
    return sum(Path(f"{DATABASE_FILE}{suffix}").stat().st_size
               for suffix in ("", "-wal", "-shm") if Path(f"{DATABASE_FILE}{suffix}").exists())


def harden_storage_permissions() -> None:
    for directory in {DATABASE_FILE.parent, BACKUP_DIR}:
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError as error:
            print(f"Unable to protect storage directory {directory}: {error}", file=sys.stderr)
    for path in [DATABASE_FILE, *BACKUP_DIR.glob("*.sqlite3")]:
        try:
            if path.exists():
                path.chmod(0o600)
        except OSError as error:
            print(f"Unable to protect SQLite file {path}: {error}", file=sys.stderr)


def _validated_backup(source: Path, target: Path) -> None:
    # 注意：`with sqlite3.connect(...)` 只提交/回滚事务，并不关闭连接（会一直留到 GC）。
    # 备份路径连接多，必须用 closing() 显式关闭。
    with closing(sqlite3.connect(source, timeout=10)) as source_connection:
        with closing(sqlite3.connect(target)) as destination:
            source_connection.backup(destination)
    target.chmod(0o600)
    with closing(sqlite3.connect(f"file:{target}?mode=ro&immutable=1", uri=True)) as connection:
        result = connection.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError("数据库备份完整性检查失败")


def create_manual_database_backup(prefix: str = "manual") -> str:
    with _database_lock:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        target = BACKUP_DIR / f"{prefix}-{stamp}.sqlite3"
        _validated_backup(DATABASE_FILE, target)
        return target.name


def list_database_backups() -> list[dict[str, Any]]:
    backups = []
    for path in sorted(BACKUP_DIR.glob("*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.name.startswith("."):
            # 恢复/回滚过程用的临时文件（.restore-* / .rollback-*）不是可恢复的备份。
            continue
        try:
            stat = path.stat()
            backups.append({"name": path.name, "bytes": stat.st_size,
                            "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                            "valid": stat.st_size > 0})
        except OSError:
            backups.append({"name": path.name, "bytes": 0, "modifiedAt": "", "valid": False})
    return backups


def restore_database_backup(name: str) -> None:
    # 点开头的隐藏文件是恢复/回滚的临时文件，不能当备份恢复（可能是半个库）。
    if Path(name).name != name or name.startswith(".") or not name.endswith(".sqlite3"):
        raise ValueError("备份文件名不正确")
    source = BACKUP_DIR / name
    if not source.is_file():
        raise ValueError("备份不存在")
    with _database_lock:
        with closing(sqlite3.connect(f"file:{source}?mode=ro&immutable=1", uri=True)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("备份完整性检查失败，不能恢复")
        emergency_name = create_manual_database_backup("before-restore")
        emergency = BACKUP_DIR / emergency_name
        try:
            _restore_database_file(source)
            ensure_schema()
            if not check_database_integrity():
                raise RuntimeError("恢复后的数据库完整性检查失败")
        except Exception:
            _restore_database_file(emergency)
            raise


def _restore_database_file(source: Path) -> None:
    source_uri = f"file:{source}?mode=ro&immutable=1"
    with closing(sqlite3.connect(source_uri, uri=True)) as backup:
        with closing(sqlite3.connect(DATABASE_FILE, timeout=10)) as destination:
            backup.backup(destination)


def check_database_integrity() -> bool:
    try:
        with _database_lock, open_state_database() as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
        return bool(result and result[0] == "ok")
    except sqlite3.Error as error:
        print(f"Unable to check SQLite integrity: {error}", file=sys.stderr)
        return False


def checkpoint_database() -> None:
    try:
        with _database_lock, open_state_database() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error as error:
        print(f"Unable to checkpoint SQLite database: {error}", file=sys.stderr)


def read_asset(key: str) -> tuple[bytes, str, str] | None:
    with _database_lock, open_state_database() as connection:
        row = connection.execute("SELECT payload,mime_type,file_name FROM app_asset WHERE key=?", (key,)).fetchone()
    return (bytes(row[0]), row[1], row[2]) if row else None


def write_asset(key: str, payload: bytes, mime_type: str, file_name: str) -> None:
    with _database_lock:
        with open_state_database() as connection:
            connection.execute(
                """INSERT INTO app_asset(key,payload,mime_type,file_name,updated_at) VALUES(?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,mime_type=excluded.mime_type,
                file_name=excluded.file_name,updated_at=excluded.updated_at""",
                (key, payload, mime_type, file_name, datetime.now().isoformat(timespec="seconds")),
            )


def delete_asset(key: str) -> None:
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("DELETE FROM app_asset WHERE key=?", (key,))


BATCH_ACTIONS = {
    "set-priority", "add-tags", "remove-tags", "set-due", "shift-due",
    "set-estimate", "complete", "uncomplete",
}


def _row_to_view(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {
        "id": str(row["view_id"]),
        "name": str(row["name"]),
        "payload": payload if isinstance(payload, dict) else {},
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"]),
    }


def list_saved_views() -> list[dict[str, Any]]:
    with _database_lock, open_state_database() as connection:
        rows = connection.execute(
            "SELECT view_id,name,payload,created_at,updated_at FROM saved_views ORDER BY name"
        ).fetchall()
    return [_row_to_view(row) for row in rows]


def save_saved_view(name: Any, payload: Any) -> dict[str, Any]:
    """按名称 upsert：同名视图直接覆盖，避免存出一堆重复项。"""
    view_name = str(name or "").strip()[:60]
    if not view_name:
        raise ValueError("视图名称不能为空")
    if not isinstance(payload, dict):
        raise ValueError("视图内容格式不正确")
    encoded = _json(payload)
    if len(encoded.encode("utf-8")) > 64 * 1024:
        raise ValueError("视图内容过大")
    now = _now()
    with _database_lock, open_state_database() as connection:
        row = connection.execute("SELECT view_id FROM saved_views WHERE name=?", (view_name,)).fetchone()
        if row:
            connection.execute(
                "UPDATE saved_views SET payload=?, updated_at=? WHERE view_id=?",
                (encoded, now, row["view_id"]),
            )
            view_id = str(row["view_id"])
        else:
            view_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO saved_views(view_id,name,payload,created_at,updated_at) VALUES(?,?,?,?,?)",
                (view_id, view_name, encoded, now, now),
            )
        saved = connection.execute(
            "SELECT view_id,name,payload,created_at,updated_at FROM saved_views WHERE view_id=?", (view_id,)
        ).fetchone()
    return _row_to_view(saved)


def delete_saved_view(view_id: Any) -> bool:
    with _database_lock, open_state_database() as connection:
        cursor = connection.execute("DELETE FROM saved_views WHERE view_id=?", (str(view_id),))
    return cursor.rowcount > 0


def _shift_iso_date(base_iso: str, days: int) -> str:
    try:
        return (date.fromisoformat(base_iso) + timedelta(days=int(days))).isoformat()
    except (TypeError, ValueError):
        return ""


def _apply_batch_action(node: dict[str, Any], action: str, value: Any, today: str,
                        marks: list[dict[str, Any]] | None = None) -> bool:
    """对单个节点应用批量动作，返回是否有变化。"""
    if action == "set-priority":
        cleaned = clean_priority(value)
        if node.get("priority", "") == cleaned:
            return False
        node["priority"] = cleaned
        return True
    if action == "add-tags":
        tags = list(node.get("tags") or [])
        for tag in clean_tags(value):
            if tag not in tags:
                tags.append(tag)
        tags = clean_tags(tags)
        if tags == list(node.get("tags") or []):
            return False
        node["tags"] = tags
        return True
    if action == "remove-tags":
        remove = set(clean_tags(value))
        tags = [tag for tag in (node.get("tags") or []) if tag not in remove]
        if tags == list(node.get("tags") or []):
            return False
        node["tags"] = tags
        return True
    if action == "set-due":
        cleaned = clean_due_date(value)
        # 非空但清洗后为空 = 日期格式不合法。绝不能当成"清除"：
        # 用户输错格式时会静默抹掉所有选中任务的截止日期。
        if str(value or "").strip() and not cleaned:
            raise ValueError("日期格式不正确，请用 YYYY-MM-DD（要清除截止日期请留空）")
        if node.get("dueDate", "") == cleaned:
            return False
        node["dueDate"] = cleaned
        return True
    if action == "shift-due":
        try:
            days = int(value)
        except (TypeError, ValueError):
            raise ValueError("延期天数必须是整数") from None
        base = clean_due_date(node.get("dueDate")) or (today if days >= 0 else "")
        if not base:
            return False
        shifted = _shift_iso_date(base, days)
        if not shifted or node.get("dueDate", "") == shifted:
            return False
        node["dueDate"] = shifted
        return True
    if action == "set-estimate":
        cleaned = clean_estimate_minutes(value)
        if int(node.get("estimateMinutes") or 0) == cleaned:
            return False
        node["estimateMinutes"] = cleaned
        return True
    if action in {"complete", "uncomplete"}:
        want = action == "complete"
        if bool(node.get("completed")) == want:
            return False
        if want and node.get("assessmentRequired") and not (node.get("assessment") or {}).get("passed"):
            raise ValueError("需要 AI 验收的任务不能批量完成")
        node["completed"] = want
        node["completedAt"] = datetime.now().isoformat(timespec="seconds") if want else None
        if not want:
            node.pop("review", None)
        if want and marks is not None:
            marks.append(node)
        return True
    raise ValueError("不支持的批量操作：" + str(action))


def _spawn_next_occurrences(project: dict[str, Any], completed_nodes: list[dict[str, Any]]) -> int:
    """批量完成周期任务时，在同一个父节点下生成下一次出现。"""
    if not completed_nodes:
        return 0
    def find_parent(nodes: list[dict[str, Any]], target_id: str | None) -> list[dict[str, Any]] | None:
        if target_id is None:
            return nodes
        for node in nodes or []:
            if str(node.get("id")) == str(target_id):
                return node.setdefault("children", [])
            found = find_parent(node.get("children") or [], target_id)
            if found is not None:
                return found
        return None

    def locate_parent_id(nodes: list[dict[str, Any]], target_id: str, parent_id: str | None = None) -> str | None:
        for node in nodes or []:
            if str(node.get("id")) == str(target_id):
                return parent_id
            found = locate_parent_id(node.get("children") or [], target_id, str(node.get("id")))
            if found is not None:
                return found
        return None

    spawned = 0
    tree = project.setdefault("tree", [])
    for node in completed_nodes:
        rule = clean_repeat(node.get("repeat"))
        if not rule:
            continue
        next_due = next_repeat_due(rule, clean_due_date(node.get("dueDate")) or date.today().isoformat())
        if not next_due:
            continue
        parent_id = locate_parent_id(tree, str(node.get("id")))
        siblings = find_parent(tree, parent_id)
        if siblings is None:
            continue
        clone = json.loads(json.dumps(node))
        clone["id"] = str(uuid.uuid4())
        clone["completed"] = False
        clone["completedAt"] = None
        clone["dueDate"] = next_due
        clone["assessment"] = None
        clone["assessmentHistory"] = 0
        # 不能连 children 一起深拷贝：子节点 id 会重复，_flatten_nodes 会抛
        # "节点 ID 重复" 让整批事务回滚。周期任务的下一次只复制任务本身。
        clone["children"] = []
        clone.pop("review", None)
        siblings.append(clone)
        spawned += 1
    return spawned


_BATCH_ACTION_NAMES = {
    "set-priority": "改优先级",
    "add-tags": "加标签",
    "remove-tags": "移标签",
    "set-due": "设截止",
    "shift-due": "延期",
    "set-estimate": "设耗时",
    "complete": "标记完成",
    "uncomplete": "取消完成",
}


def _project_auto_review(project: dict[str, Any]) -> bool:
    """与前端 projectAutoReview 一致：reviewEnabled 显式布尔优先，否则看 assessmentEnabled。"""
    enabled = project.get("reviewEnabled")
    if isinstance(enabled, bool):
        return enabled
    return bool(project.get("assessmentEnabled"))


def batch_update_nodes(targets: Any, action: str, value: Any = None) -> dict[str, Any]:
    """按项目分组批量修改节点：每个项目一次事务、revision 前进一次。"""
    if action not in BATCH_ACTIONS:
        raise ValueError("不支持的批量操作：" + str(action))
    if not isinstance(targets, list) or not targets:
        raise ValueError("请先选择要修改的任务")
    grouped: dict[str, set[str]] = {}
    for target in targets:
        if not isinstance(target, dict):
            continue
        project_id = str(target.get("projectId") or "")
        node_id = str(target.get("nodeId") or "")
        if project_id and node_id:
            grouped.setdefault(project_id, set()).add(node_id)
    if not grouped:
        raise ValueError("请先选择要修改的任务")
    today = date.today().isoformat()
    changed = 0
    spawned_total = 0
    failed: list[dict[str, str]] = []
    projects_touched: list[str] = []
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = datetime.now().isoformat(timespec="seconds")
            position = _project_position
            for project_id, node_ids in grouped.items():
                result = _read_project_from_connection(connection, project_id)
                if not result:
                    failed.append({"projectId": project_id, "error": "项目不存在"})
                    continue
                project, revision = result
                applied = 0
                marks: list[dict[str, Any]] = []
                stack = list(project.get("tree") or [])
                while stack:
                    node = stack.pop()
                    if str(node.get("id")) in node_ids and node.get("type") == "item":
                        try:
                            if _apply_batch_action(node, action, value, today, marks):
                                applied += 1
                        except ValueError as error:
                            failed.append({"projectId": project_id, "nodeId": str(node.get("id")), "error": str(error)})
                    stack.extend(node.get("children") or [])
                if applied == 0:
                    continue
                # 批量完成也要安排复习，否则和逐条完成的行为不一致
                # （同一批任务，逐条点会排进复习队列，批量点却永远不进）。
                if marks and action == "complete" and _project_auto_review(project):
                    review_due = (date.today() + timedelta(days=1)).isoformat()
                    for node in marks:
                        if not node.get("optional") and not node.get("review"):
                            node["review"] = {"due": review_due, "learning": False, "log": []}
                spawned = _spawn_next_occurrences(project, marks)
                _upsert_project(connection, project, position(connection, project_id), revision + 1, now)
                log_activity(
                    "batch", f"批量{_BATCH_ACTION_NAMES.get(action, action)} {applied} 项",
                    project_id=project_id, project_name=_project_title(project),
                    detail={"action": action, "changed": applied, "spawned": spawned,
                            "nodeIds": sorted(node_ids)},
                    undoable=action not in {"complete"},
                    connection=connection,
                )
                projects_touched.append(project_id)
                changed += applied
                spawned_total += spawned
    summaries = read_project_summaries()
    return {
        "changed": changed,
        "spawned": spawned_total,
        "failed": failed,
        "projects": [summary for summary in summaries if str(summary.get("id")) in set(projects_touched)],
    }


INBOX_PROJECT_ID = "inbox"
INBOX_PROJECT_NAME = "收集箱"
WORKBENCH_HORIZON_DAYS = 7


def _project_position(connection: sqlite3.Connection, project_id: str) -> int:
    row = connection.execute("SELECT position FROM projects WHERE project_id=?", (project_id,)).fetchone()
    return int(row["position"]) if row else 0


def ensure_inbox_project() -> tuple[dict[str, Any], int]:
    """收集箱是一个保留项目（id 固定 inbox），按需创建。"""
    existing = read_project(INBOX_PROJECT_ID)
    if existing:
        return existing
    project = {
        "id": INBOX_PROJECT_ID,
        "name": INBOX_PROJECT_NAME,
        "description": "快速记录，之后再归类到项目 / 周 / 单元",
        "createdAt": date.today().isoformat(),
        "assessmentEnabled": False,
        "reviewEnabled": False,
        "tree": [],
    }
    write_project(project, None)
    created = read_project(INBOX_PROJECT_ID)
    if not created:
        raise RuntimeError("收集箱创建失败")
    return created


def add_inbox_item(node: dict[str, Any]) -> dict[str, Any]:
    return add_project_item(INBOX_PROJECT_ID, node)


def add_project_item(project_id: str, node: dict[str, Any],
                     parent_id: str | None = None) -> dict[str, Any]:
    """在指定项目下快速新建一个任务（收集箱就是 id=inbox 的那个项目）。"""
    if str(project_id) == INBOX_PROJECT_ID:
        project, revision = ensure_inbox_project()
    else:
        found = read_project(project_id)
        if not found:
            raise ValueError("目标项目不存在")
        project, revision = found
        # 前端的选择器已经过滤掉归档项目；接口也要一致，
        # 否则能往一个在列表/工作台里都看不见的项目里加任务。
        if bool(project.get("archived")):
            raise ValueError("目标项目已归档，请先取消归档再添加")
    item_id = str(node.get("id") or uuid.uuid4())
    item = {
        "id": item_id,
        "type": "item",
        "text": str(node.get("text") or "").strip()[:500] or "未命名任务",
        "completed": False,
        "completedAt": None,
        "optional": bool(node.get("optional")),
        "assessmentRequired": False,
        "assessmentHistory": 0,
        "assessment": None,
        "createdAt": date.today().isoformat(),
        "children": [],
        "priority": clean_priority(node.get("priority")),
        "dueDate": clean_due_date(node.get("dueDate")),
        "estimateMinutes": clean_estimate_minutes(node.get("estimateMinutes")),
        "tags": clean_tags(node.get("tags")),
        "note": str(node.get("note") or "")[:MAX_NOTE_CHARS],
        "links": clean_links(node.get("links")),
        "repeat": clean_repeat(node.get("repeat")),
    }
    if parent_id:
        # 追加到目标父节点的末尾。position 是"父节点 children 里的下标"，
        # 以前传顶层节点数，父节点下任务多的时候会插到中间。
        children = _find_children_list(project.setdefault("tree", []), str(parent_id))
        if children is None:
            raise ValueError("找不到父节点，任务未创建")
        children.append(item)
    else:
        project["tree"] = list(project.get("tree") or []) + [item]
    revision_after, _summary = write_project(project, revision)
    stored = read_project(str(project_id))
    created = None
    if stored:
        created = _find_node_by_id(stored[0].get("tree") or [], item_id)
    if created is None:
        raise RuntimeError("写入后读不回该任务")
    return {"node": created, "revision": revision_after, "projectId": str(project_id)}


def _find_node_by_id(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    for node in nodes or []:
        if str(node.get("id")) == str(node_id):
            return node
        found = _find_node_by_id(node.get("children") or [], node_id)
        if found is not None:
            return found
    return None


def _detach_node(tree: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    for index, node in enumerate(list(tree)):
        if str(node.get("id")) == str(node_id):
            tree.pop(index)
            return node
        found = _detach_node(node.get("children") or [], node_id)
        if found is not None:
            return found
    return None


def move_node(node_id: str, from_project_id: str, to_project_id: str,
              parent_id: str | None = None, position: int | None = None) -> dict[str, Any]:
    """把任务从一个项目移到另一个项目（收集箱归类用），两个项目在同一个事务里更新。"""
    if str(from_project_id) == str(to_project_id):
        raise ValueError("源项目和目标项目相同")
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            source = _read_project_from_connection(connection, str(from_project_id))
            target = _read_project_from_connection(connection, str(to_project_id))
            if not source:
                raise ValueError("原项目不存在")
            if not target:
                raise ValueError("目标项目不存在")
            source_project, source_revision = source
            target_project, target_revision = target
            # 前端的目标项目下拉本来就把已归档项目过滤掉了；接口也要一致，
            # 否则能把任务归类进一个在工作台/列表里都看不见的项目。
            if bool(target_project.get("archived")) and str(to_project_id) != INBOX_PROJECT_ID:
                raise ValueError("目标项目已归档，请先取消归档再归类")
            if str(target_project.get("id")) == INBOX_PROJECT_ID and parent_id is None:
                parent_id = None  # 收集箱允许平铺任务
            moved = _detach_node(source_project.get("tree") or [], node_id)
            if moved is None:
                raise ValueError("任务不存在或已经被移动")
            _find_parent_and_insert(
                target_project.setdefault("tree", []),
                str(parent_id) if parent_id is not None else None,
                moved,
                int(position) if position is not None else len(target_project.get("tree") or []),
            )
            now = datetime.now().isoformat(timespec="seconds")
            _upsert_project(connection, source_project,
                            _project_position(connection, str(from_project_id)), source_revision + 1, now)
            _upsert_project(connection, target_project,
                            _project_position(connection, str(to_project_id)), target_revision + 1, now)
    return {"nodeId": str(node_id), "from": str(from_project_id), "to": str(to_project_id)}


# ---------- 拖拽排序 / 复制 / 删除影响面（第五批 1、2、3、13） ----------

CONTAINER_TYPES = ("week", "day")


def _find_node(nodes: Any, node_id: Any) -> dict[str, Any] | None:
    target = str(node_id)
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("id")) == target:
            return node
        found = _find_node(node.get("children") or [], target)
        if found is not None:
            return found
    return None


def _parent_of(nodes: list[dict[str, Any]], target_id: str, parent_id: str | None = None) -> str | None:
    for node in nodes or []:
        if str(node.get("id")) == str(target_id):
            return parent_id
        found = _parent_of(node.get("children") or [], target_id, str(node.get("id")))
        if found is not None:
            return found
    return None


def _index_of(nodes: list[dict[str, Any]], target_id: str) -> int:
    for index, node in enumerate(nodes or []):
        if str(node.get("id")) == str(target_id):
            return index
    return -1


def _walk_nodes(nodes: Any) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        collected.append(node)
        collected.extend(_walk_nodes(node.get("children") or []))
    return collected


def _refresh_all_ids(node: dict[str, Any]) -> dict[str, Any]:
    """深拷贝一棵子树并给每个节点换新 ID（复制用）。"""
    clone = json.loads(json.dumps(node))
    for item in _walk_nodes([clone]):
        item["id"] = str(uuid.uuid4())
    return clone


def _apply_copy_options(node: dict[str, Any], *, keep_completion: bool, keep_assessment: bool,
                        keep_review: bool) -> None:
    for item in _walk_nodes([node]):
        if not keep_completion:
            item["completed"] = False
            item["completedAt"] = None
        if not keep_assessment:
            item["assessment"] = None
            item["assessmentHistory"] = 0
        if not keep_review:
            item.pop("review", None)


def reorder_node(project_id: Any, node_id: Any, parent_id: Any = None,
                 position: Any = None) -> dict[str, Any]:
    """在同一个项目内拖拽排序/跨周跨单元移动（父节点与位置一起给）。"""
    project_key = str(project_id)
    target_parent = str(parent_id) if parent_id not in (None, "") else None
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = _read_project_from_connection(connection, project_key)
            if not result:
                raise ValueError("项目不存在")
            project, revision = result
            tree = project.setdefault("tree", [])
            node = _find_node(tree, node_id)
            if node is None:
                raise ValueError("节点不存在或已被删除")
            if target_parent is not None:
                if target_parent == str(node_id):
                    raise ValueError("不能把节点移动到它自己下面")
                parent_node = _find_node(tree, target_parent)
                if parent_node is None:
                    raise ValueError("目标父节点不存在")
                if str(parent_node.get("type")) not in CONTAINER_TYPES:
                    raise ValueError("只能移动到周或学习单元下面")
                if _find_node(node.get("children") or [], target_parent) is not None:
                    raise ValueError("不能把节点移动到它自己的子节点下面")
            previous_parent = _parent_of(tree, str(node_id))
            previous_list = _find_children_list(tree, previous_parent) or []
            previous_position = _index_of(previous_list, str(node_id))
            detached = _detach_node(tree, str(node_id))
            if detached is None:
                raise ValueError("节点不存在或已被删除")
            siblings = _find_children_list(tree, target_parent)
            if siblings is None:
                raise ValueError("目标父节点不存在")
            index = len(siblings) if position in (None, "") else max(0, min(int(position), len(siblings)))
            siblings.insert(index, detached)
            now = _now()
            _upsert_project(connection, project, _project_position(connection, project_key), revision + 1, now)
            log_activity(
                "reorder", f"移动「{str(detached.get('text') or '未命名')}」",
                project_id=project_key, project_name=_project_title(project),
                detail={"nodeId": str(node_id), "parentId": target_parent, "position": index,
                        "previousParentId": previous_parent, "previousPosition": previous_position},
                undoable=True, connection=connection,
            )
    return {
        "projectId": project_key,
        "nodeId": str(node_id),
        "parentId": target_parent,
        "position": index,
        "previous": {"parentId": previous_parent, "position": previous_position},
    }


def duplicate_node(project_id: Any, node_id: Any, *,
                   include_children: bool = True,
                   keep_completion: bool = False,
                   keep_assessment: bool = False,
                   keep_review: bool = False) -> dict[str, Any]:
    """复制节点（可整枝复制）。副本插在原节点后面，ID 全部重新生成。"""
    project_key = str(project_id)
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = _read_project_from_connection(connection, project_key)
            if not result:
                raise ValueError("项目不存在")
            project, revision = result
            tree = project.setdefault("tree", [])
            node = _find_node(tree, node_id)
            if node is None:
                raise ValueError("节点不存在或已被删除")
            parent_id = _parent_of(tree, str(node_id))
            siblings = _find_children_list(tree, parent_id)
            if siblings is None:
                raise ValueError("找不到原节点的位置")
            index = _index_of(siblings, str(node_id))
            clone = _refresh_all_ids(node)
            if not include_children:
                clone["children"] = []
            if str(clone.get("type")) == "item":
                clone["children"] = []
            clone["text"] = str(node.get("text") or "未命名") + "（副本）"
            _apply_copy_options(clone, keep_completion=keep_completion,
                                keep_assessment=keep_assessment, keep_review=keep_review)
            siblings.insert(index + 1, clone)
            now = _now()
            _upsert_project(connection, project, _project_position(connection, project_key), revision + 1, now)
            log_activity(
                "duplicate", f"复制「{str(node.get('text') or '未命名')}」",
                project_id=project_key, project_name=_project_title(project),
                detail={"sourceNodeId": str(node_id), "newNodeId": clone["id"],
                        "withChildren": bool(include_children)},
                undoable=True, connection=connection,
            )
    return {"projectId": project_key, "node": clone, "sourceNodeId": str(node_id)}


def duplicate_project(project_id: Any, *, name: str | None = None,
                      keep_completion: bool = True,
                      keep_assessment: bool = True,
                      keep_review: bool = True) -> dict[str, Any]:
    """复制整个项目（ID 全部重新生成），可选是否保留完成状态 / AI 历史 / 复习安排。"""
    project_key = str(project_id)
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = _read_project_from_connection(connection, project_key)
            if not result:
                raise ValueError("项目不存在")
            original, _revision = result
            clone = json.loads(json.dumps(original))
            clone["id"] = str(uuid.uuid4())
            clone["name"] = str(name or "").strip()[:200] or f"{_project_title(original)}（副本）"
            clone["createdAt"] = date.today().isoformat()
            clone["archived"] = False
            clone.pop("lastOpenedAt", None)
            clone["tree"] = [
                _refresh_all_ids(node) for node in (original.get("tree") or [])
            ]
            for node in clone["tree"]:
                _apply_copy_options(node, keep_completion=keep_completion,
                                    keep_assessment=keep_assessment, keep_review=keep_review)
            position = connection.execute("SELECT COALESCE(MAX(position),-1)+1 FROM projects").fetchone()[0]
            _upsert_project(connection, clone, int(position), 1, _now())
            log_activity(
                "duplicate-project", f"复制项目「{_project_title(original)}」",
                project_id=clone["id"], project_name=clone["name"],
                detail={"sourceProjectId": project_key, "keepCompletion": bool(keep_completion),
                        "keepAssessment": bool(keep_assessment), "keepReview": bool(keep_review)},
                connection=connection,
            )
    return {"project": clone, "sourceProjectId": project_key}


# ---------- 节点级 patch（item 2）：一个事务里改少量节点，不再整棵树重写 ----------

PATCH_NODE_FIELDS: dict[str, Any] = {
    "text": lambda value: str(value or "").strip()[:500] or "未命名任务",
    "completed": lambda value: int(bool(value)),
    "completedAt": lambda value: (str(value)[:40] if value else None),
    "optional": lambda value: int(bool(value)),
    "assessmentRequired": lambda value: int(bool(value)),
    "assessmentHistory": lambda value: max(0, int(value or 0)),
    "expanded": lambda value: int(bool(value)),
    "priority": clean_priority,
    "dueDate": clean_due_date,
    "estimateMinutes": clean_estimate_minutes,
    "tags": lambda value: (_json(clean_tags(value)) if clean_tags(value) else ""),
    "note": lambda value: str(value or "")[:MAX_NOTE_CHARS],
    "links": lambda value: (_json(clean_links(value)) if clean_links(value) else ""),
    "repeat": lambda value: (_json(clean_repeat(value)) if clean_repeat(value) else ""),
}
# 字段名 → 列名（前端用 camelCase）
PATCH_COLUMNS = {
    "text": "text", "completed": "completed", "completedAt": "completed_at",
    "optional": "optional", "assessmentRequired": "assessment_required",
    "assessmentHistory": "assessment_history", "expanded": "expanded",
    "priority": "priority", "dueDate": "due_date", "estimateMinutes": "estimate_minutes",
    "tags": "tags", "note": "note", "links": "links", "repeat": "repeat",
}
MAX_PATCH_OPS = 200


def _summary_from_sql(connection: sqlite3.Connection, project_id: str, base: dict[str, Any]) -> dict[str, Any]:
    """不重建整棵树，直接用 SQL 算出项目摘要（与 project_summary() 口径一致）。"""
    main = connection.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN completed=0 THEN 1 ELSE 0 END) AS remaining "
        "FROM nodes WHERE project_id=? AND type='item' AND optional=0",
        (project_id,),
    ).fetchone()
    optional = connection.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) AS done "
        "FROM nodes WHERE project_id=? AND type='item' AND optional=1",
        (project_id,),
    ).fetchone()
    return {
        "id": json.loads(base["id_json"]),
        "name": str(base["name"]),
        "description": str(base["description"]),
        "createdAt": str(base["created_at"]),
        "assessmentEnabled": bool(base["assessment_enabled"]),
        "archived": bool(base["archived"]),
        "stats": {
            "total": int(main["total"] or 0),
            "remaining": int(main["remaining"] or 0),
            "optionalTotal": int(optional["total"] or 0),
            "optionalCompleted": int(optional["done"] or 0),
        },
    }


def _subtree_ids(connection: sqlite3.Connection, project_id: str, node_id: str) -> list[str]:
    rows = connection.execute(
        """WITH RECURSIVE sub(node_id) AS (
               SELECT node_id FROM nodes WHERE project_id=? AND node_id=?
               UNION ALL
               SELECT n.node_id FROM nodes n JOIN sub ON n.parent_id = sub.node_id
               WHERE n.project_id=?
           ) SELECT node_id FROM sub""",
        (project_id, node_id, project_id),
    ).fetchall()
    return [str(row[0]) for row in rows]


def patch_project_nodes(project_id: Any, expected_revision: Any, ops: Any) -> dict[str, Any]:
    """节点级 patch：update / append / delete 在**一个事务**里完成，revision 只前进一次。

    刻意不做整棵树重建：所有操作都是 O(改动的节点数)，10k 节点的项目也只花毫秒级。
    """
    project_key = str(project_id)
    if not isinstance(ops, list) or not ops:
        raise ValueError("没有要应用的改动")
    if len(ops) > MAX_PATCH_OPS:
        raise ValueError(f"一次最多提交 {MAX_PATCH_OPS} 个节点改动")
    updated: list[str] = []
    appended: list[dict[str, Any]] = []
    deleted: list[str] = []
    with _database_lock:
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            base = connection.execute(
                "SELECT project_id,position,revision,id_json,name,description,created_at,"
                "assessment_enabled,archived FROM projects WHERE project_id=?",
                (project_key,),
            ).fetchone()
            if not base:
                raise ValueError("项目不存在")
            current_revision = int(base["revision"])
            if expected_revision is not None and int(expected_revision) != current_revision:
                raise StateConflictError(f"项目已被其他页面更新（当前版本 {current_revision}）")
            for op in ops:
                if not isinstance(op, dict):
                    raise ValueError("节点改动格式不正确")
                kind = str(op.get("op") or "")
                if kind == "update":
                    node_id = str(op.get("nodeId") or "")
                    if not node_id:
                        raise ValueError("缺少 nodeId")
                    fields = op.get("fields") if isinstance(op.get("fields"), dict) else {}
                    unknown = set(fields) - set(PATCH_COLUMNS) - {"assessment", "review"}
                    if unknown:
                        raise ValueError("不支持的节点字段：" + "、".join(sorted(unknown)))
                    columns = []
                    params: list[Any] = []
                    for key, value in fields.items():
                        if key in ("assessment", "review"):
                            continue
                        columns.append(f"{PATCH_COLUMNS[key]}=?")
                        params.append(PATCH_NODE_FIELDS[key](value))
                    if "review" in fields:
                        # 复习状态在库里是三个列，和整树写入共用 review_columns 口径
                        columns.extend(["review_due=?", "review_learning=?", "review_log=?"])
                        params.extend(review_columns(fields["review"]))
                    if columns:
                        cursor = connection.execute(
                            f"UPDATE nodes SET {', '.join(columns)} WHERE project_id=? AND node_id=?",
                            (*params, project_key, node_id),
                        )
                        if cursor.rowcount == 0:
                            raise ValueError("节点不存在或已被删除")
                    if "assessment" in fields:
                        exists = connection.execute(
                            "SELECT 1 FROM nodes WHERE project_id=? AND node_id=?",
                            (project_key, node_id)).fetchone()
                        if not exists:
                            raise ValueError("节点不存在或已被删除")
                        assessment = fields["assessment"]
                        _write_assessment(connection, {
                            "project_id": project_key, "node_id": node_id,
                            "assessment": assessment if isinstance(assessment, dict) else None,
                        }, _now())
                    updated.append(node_id)
                elif kind == "append":
                    node = op.get("node")
                    if not isinstance(node, dict):
                        raise ValueError("新增节点格式不正确")
                    parent_id = op.get("parentId")
                    parent_key = str(parent_id) if parent_id not in (None, "") else None
                    if parent_key is not None:
                        parent = connection.execute(
                            "SELECT type FROM nodes WHERE project_id=? AND node_id=?",
                            (project_key, parent_key)).fetchone()
                        if not parent:
                            raise ValueError("目标父节点不存在")
                        if str(parent["type"]) not in CONTAINER_TYPES:
                            raise ValueError("只能挂到周或学习单元下面")
                    node_id = str(node.get("id") or uuid.uuid4())
                    if connection.execute("SELECT 1 FROM nodes WHERE project_id=? AND node_id=?",
                                          (project_key, node_id)).fetchone():
                        raise ValueError("节点 ID 已存在")
                    node = {**node, "id": node_id}
                    rows = _flatten_nodes(project_key, [node], parent_key)
                    if not rows:
                        raise ValueError("新增节点格式不正确")
                    next_position = int(connection.execute(
                        "SELECT COALESCE(MAX(position),-1)+1 FROM nodes WHERE project_id=? AND parent_id IS ?",
                        (project_key, parent_key)).fetchone()[0])
                    for offset, flat in enumerate(rows):
                        flat["position"] = next_position + offset
                        flat["assessment"] = flat.get("assessment")
                        _insert_node_row(connection, flat)
                    appended.append({"id": node_id, "parentId": parent_key})
                elif kind == "delete":
                    node_id = str(op.get("nodeId") or "")
                    if not node_id:
                        raise ValueError("缺少 nodeId")
                    ids = _subtree_ids(connection, project_key, node_id)
                    if not ids:
                        raise ValueError("节点不存在或已被删除")
                    placeholders = ",".join("?" for _ in ids)
                    connection.execute(
                        f"DELETE FROM nodes WHERE project_id=? AND node_id IN ({placeholders})",
                        (project_key, *ids))
                    deleted.append(node_id)
                else:
                    raise ValueError("不支持的节点操作：" + (kind or "(空)"))
            revision = current_revision + 1
            summary = _summary_from_sql(connection, project_key, base)
            connection.execute(
                "UPDATE projects SET revision=?, updated_at=?, summary_json=? WHERE project_id=?",
                (revision, _now(), _json(summary), project_key))
            if deleted:
                log_activity("delete", f"删除节点 {len(deleted)} 处", project_id=project_key,
                             project_name=str(base["name"]),
                             detail={"nodeIds": deleted}, connection=connection)
    return {"projectId": project_key, "revision": revision, "summary": summary,
            "updated": updated, "appended": appended, "deleted": deleted}


def describe_node_delete(project_id: Any, node_id: Any) -> dict[str, Any]:
    """删除前的影响面：子树有多少任务、多少已完成、预计耗时合计。"""
    project_key = str(project_id)
    with _database_lock, open_state_database() as connection:
        result = _read_project_from_connection(connection, project_key)
    if not result:
        raise ValueError("项目不存在")
    project, _revision = result
    node = _find_node(project.get("tree") or [], node_id)
    if node is None:
        raise ValueError("节点不存在或已被删除")
    descendants = _walk_nodes(node.get("children") or [])
    items = [entry for entry in descendants if str(entry.get("type")) == "item"]
    if str(node.get("type")) == "item":
        items.append(node)
    minutes = sum(int(entry.get("estimateMinutes") or 0) for entry in items)
    return {
        "projectId": project_key,
        "nodeId": str(node_id),
        "title": str(node.get("text") or "未命名"),
        "type": str(node.get("type") or ""),
        "descendantCount": len(descendants),
        "itemCount": len(items),
        "completedCount": len([entry for entry in items if entry.get("completed")]),
        "estimateMinutes": minutes,
    }


def touch_project_opened(project_id: Any) -> None:
    with _database_lock, open_state_database() as connection:
        connection.execute(
            "UPDATE projects SET last_opened_at=? WHERE project_id=?",
            (datetime.now().isoformat(timespec="seconds"), str(project_id)),
        )


# 一次 IN(...) 里最多绑多少个参数：SQLite 旧版默认上限 999，这里留足余量。
SQL_PARAM_CHUNK = 400
# 工作台的分组名（顺序即界面顺序）；空响应也要保持同样的形状。
WORKBENCH_GROUP_KEYS = ("overdue", "today", "next7", "reviewToday", "inbox")


def _node_locations(connection: sqlite3.Connection,
                    rows: Any) -> dict[tuple[str, str], dict[str, Any]]:
    """为**给定**的节点行算可读路径与祖先 id（工作台 / 复习队列 / 搜索用）。

    rows 必须带 project_id / node_id / parent_id 三列。三层树里祖先只可能是周或单元，
    所以这里只额外读一次"这些项目里的周与单元"（占比很小），再在内存里向上走：
    O(目标行数 × 深度)。旧实现把全库节点（含 text）整表读进内存、为每个节点拼一遍路径
    （10k 节点实测 26.7 ms），而三个接口真正需要的行往往只有几十到几千。
    """
    project_ids = sorted({str(row["project_id"]) for row in rows})
    if not project_ids:
        return {}
    containers: dict[tuple[str, str], tuple[str | None, str]] = {}
    for start in range(0, len(project_ids), SQL_PARAM_CHUNK):
        chunk = project_ids[start:start + SQL_PARAM_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        for row in connection.execute(
            f"SELECT project_id,node_id,parent_id,text FROM nodes "
            f"WHERE project_id IN ({placeholders}) AND type IN ('week','day')",
            chunk,
        ):
            containers[(str(row["project_id"]), str(row["node_id"]))] = (
                str(row["parent_id"]) if row["parent_id"] is not None else None,
                str(row["text"] or ""),
            )

    locations: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["project_id"]), str(row["node_id"]))
        labels: list[str] = []
        ancestors: list[str] = []
        cursor: str | None = str(row["parent_id"]) if row["parent_id"] is not None else None
        seen: set[str] = set()
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            ancestors.append(cursor)
            parent_entry = containers.get((key[0], cursor))
            if not parent_entry:
                break
            if parent_entry[1]:
                labels.append(parent_entry[1])
            cursor = parent_entry[0]
        locations[key] = {"path": " / ".join(reversed(labels)), "ancestorIds": list(reversed(ancestors))}
    return locations


def _workbench_version(connection: sqlite3.Connection) -> str:
    """工作台的轻量变更指纹：只做聚合、不传行，用来判断"能不能跳过整次重算"。

    覆盖 workbench 真正读到的两处数据：
      · projects：COUNT / SUM(revision) / SUM(archived)。任何节点写入（整树保存、节点 patch、
        批量、导入、复习回流）都会让某个项目的 revision 前进；归档改 archived；增删项目改 COUNT。
      · nodes(type='item')：COUNT / SUM(completed) / 有截止或有复习日期的行数。这一项是兜底：
        换库/恢复备份/导入替换后 revision 恰好相同的情况，也能被它看出来。

    刻意不做的事：不读具体行、不算路径。10k 任务实测 2.4 ms，而完整 workbench 是 79 ms。
    """
    projects = connection.execute(
        "SELECT COUNT(*),COALESCE(SUM(revision),0),COALESCE(SUM(archived),0) FROM projects"
    ).fetchone()
    items = connection.execute(
        "SELECT COUNT(*),COALESCE(SUM(completed),0),"
        "COALESCE(SUM(CASE WHEN due_date<>'' OR review_due<>'' THEN 1 ELSE 0 END),0) "
        "FROM nodes WHERE type='item'"
    ).fetchone()
    return ":".join(str(int(value or 0)) for value in (*projects, *items))


def workbench(today: str | None = None, since: str | None = None) -> dict[str, Any]:
    """今日工作台：逾期 / 今天 / 未来 7 天 / 今天要复习 / 收集箱。

    `since` 是上一次响应里的 `version`；数据没变就直接回 `unchanged: true` 的空结果，
    让"每分钟轮询一次"的提醒功能不必每次重算全部分组（页面正常打开时不传 since）。
    """
    reference = clean_due_date(today) or date.today().isoformat()
    horizon = (date.fromisoformat(reference) + timedelta(days=WORKBENCH_HORIZON_DAYS)).isoformat()
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in WORKBENCH_GROUP_KEYS}
    with _database_lock, open_state_database() as connection:
        version = _workbench_version(connection)
        if since and str(since) == version:
            return {
                "today": reference,
                "serverToday": date.today().isoformat(),
                "horizonDays": WORKBENCH_HORIZON_DAYS,
                "groups": {key: [] for key in WORKBENCH_GROUP_KEYS},
                "totals": {key: 0 for key in WORKBENCH_GROUP_KEYS},
                "version": version,
                "unchanged": True,
            }
        # 收集箱即使被归档也要显示：快速添加永远写进它，看不见就等于任务消失。
        project_names = {
            str(row["project_id"]): str(row["name"])
            for row in connection.execute(
                "SELECT project_id,name FROM projects WHERE archived=0 OR project_id=?",
                (INBOX_PROJECT_ID,),
            )
        }
        # 只有"可能落进某个分组"的任务才需要读出来（下面 Python 仍然按原口径分桶）：
        # 未完成且截止日 <= horizon、未完成的收集箱任务、已完成且复习日 <= 今天。
        # 以前这里读全库每一个任务并为它造字典（含 json.loads），绝大多数行随后被丢掉。
        rows = connection.execute(
            """SELECT project_id,node_id,parent_id,text,completed,priority,due_date,estimate_minutes,tags,
                      note,links,repeat,review_due,completed_at
               FROM nodes WHERE type='item' AND (
                   (completed=0 AND ((due_date<>'' AND due_date<=?) OR project_id=?))
                   OR (completed=1 AND review_due<>'' AND review_due<=?)
               )""",
            (horizon, INBOX_PROJECT_ID, reference),
        ).fetchall()
        locations = _node_locations(connection, rows)
    for row in rows:
        project_id = str(row["project_id"])
        if project_id not in project_names:
            continue
        item = {
            "projectId": project_id,
            "projectName": project_names[project_id],
            "nodeId": str(row["node_id"]),
            "text": str(row["text"] or ""),
            "priority": str(row["priority"] or ""),
            "dueDate": str(row["due_date"] or ""),
            "estimateMinutes": int(row["estimate_minutes"] or 0),
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            # 徽标（备注 / 链接 / 周期）需要这三个字段，否则工作台的行看起来"没设过"。
            "note": str(row["note"] or ""),
            "links": json.loads(row["links"]) if row["links"] else [],
            "repeat": json.loads(row["repeat"]) if row["repeat"] else None,
            "path": (locations.get((project_id, str(row["node_id"]))) or {}).get("path", ""),
            "ancestorIds": (locations.get((project_id, str(row["node_id"]))) or {}).get("ancestorIds", []),
        }
        completed = bool(row["completed"])
        review_due = str(row["review_due"] or "")
        if not completed:
            due = str(row["due_date"] or "")
            bucketed = False
            if due:
                if due < reference:
                    groups["overdue"].append(dict(item, daysOverdue=_days_between(due, reference)))
                    bucketed = True
                elif due == reference:
                    groups["today"].append(item)
                    bucketed = True
                elif due <= horizon:
                    groups["next7"].append(dict(item, daysUntil=_days_between(reference, due)))
                    bucketed = True
            # 收集箱分组只放"没被日期分组收走"的任务，否则同一条任务会在
            # "今天到期"和"收集箱"里各出现一次，两个计数也重复。
            if project_id == INBOX_PROJECT_ID and not bucketed:
                groups["inbox"].append(item)
        if completed and review_due and review_due <= reference:
            groups["reviewToday"].append(dict(item, reviewDue=review_due,
                                              daysOverdue=_days_between(review_due, reference)))
    priority_rank = {"high": 0, "mid": 1, "low": 2, "": 3}
    for items in groups.values():
        items.sort(key=lambda entry: (priority_rank.get(entry["priority"], 3),
                                      entry.get("dueDate") or entry.get("reviewDue") or "",
                                      entry["text"]))
    return {
        "today": reference,
        "serverToday": date.today().isoformat(),
        "horizonDays": WORKBENCH_HORIZON_DAYS,
        "groups": groups,
        "totals": {key: len(items) for key, items in groups.items()},
        "version": version,
    }


def _days_between(start: str, end: str) -> int:
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def recent_overview(limit: int = 10) -> dict[str, Any]:
    """最近打开 / 最近修改 / 最近完成。"""
    with _database_lock, open_state_database() as connection:
        opened = [{
            "id": str(row["project_id"]), "name": str(row["name"]),
            "at": str(row["last_opened_at"] or ""), "archived": bool(row["archived"]),
        } for row in connection.execute(
            "SELECT project_id,name,last_opened_at,archived FROM projects "
            "WHERE last_opened_at<>'' ORDER BY last_opened_at DESC LIMIT ?", (int(limit),))]
        modified = [{
            "id": str(row["project_id"]), "name": str(row["name"]),
            "at": str(row["updated_at"] or ""), "archived": bool(row["archived"]),
        } for row in connection.execute(
            "SELECT project_id,name,updated_at,archived FROM projects "
            "ORDER BY updated_at DESC, project_id LIMIT ?", (int(limit),))]
        completed = [{
            "projectId": str(row["project_id"]), "projectName": str(row["name"]),
            "nodeId": str(row["node_id"]), "text": str(row["text"] or ""),
            "at": str(row["completed_at"] or ""),
        } for row in connection.execute(
            "SELECT n.project_id,n.node_id,n.text,n.completed_at,p.name FROM nodes n "
            "JOIN projects p ON p.project_id=n.project_id "
            "WHERE n.type='item' AND n.completed=1 AND n.completed_at<>'' "
            "ORDER BY n.completed_at DESC LIMIT ?", (int(limit),))]
    return {"opened": opened, "modified": modified, "completed": completed}


def storage_diagnostics() -> dict[str, Any]:
    """库大小 / 项目数 / 最大项目大小。

    以前这里会**重建每一个项目**再序列化（10k 节点约 145 ms），现在改成 SQL 汇总：
    按存储列的实际字节数 + 每节点固定开销估算，误差在个位数百分比（响应里标 sizeIsEstimate）。
    """
    with _database_lock, open_state_database() as connection:
        project_count = int(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
        node_count = int(connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
        conversation_count = int(connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])
        rows = connection.execute(
            """SELECT
                 LENGTH(CAST(p.id_json AS BLOB)) + LENGTH(CAST(p.name AS BLOB))
                 + LENGTH(CAST(p.description AS BLOB)) + LENGTH(CAST(p.summary_json AS BLOB))
                 + COALESCE((SELECT SUM(
                       LENGTH(CAST(n.id_json AS BLOB)) + LENGTH(CAST(n.text AS BLOB))
                     + LENGTH(CAST(n.note AS BLOB)) + LENGTH(CAST(n.tags AS BLOB))
                     + LENGTH(CAST(n.links AS BLOB)) + LENGTH(CAST(n.repeat AS BLOB))
                     + LENGTH(CAST(COALESCE(n.completed_at,'') AS BLOB)) + 48)
                     FROM nodes n WHERE n.project_id = p.project_id), 0)
                 + COALESCE((SELECT SUM(LENGTH(CAST(a.payload AS BLOB))) FROM assessments a
                             WHERE a.project_id = p.project_id), 0)
                 + COALESCE((SELECT SUM(LENGTH(CAST(c.content AS BLOB))) FROM conversations c
                             WHERE c.project_id = p.project_id), 0)
               AS size
               FROM projects p"""
        ).fetchall()
    sizes = [int(row[0] or 0) for row in rows]
    return {"databaseBytes": database_file_size(), "projectBytes": sum(sizes),
            "largestProjectBytes": max(sizes) if sizes else 0, "projectCount": project_count,
            "nodeCount": node_count, "conversationCount": conversation_count,
            "maxProjectBytes": MAX_PROJECT_PAYLOAD_BYTES, "schemaVersion": SCHEMA_VERSION,
            "sizeIsEstimate": True}
