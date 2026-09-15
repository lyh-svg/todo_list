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
SCHEMA_VERSION = 6
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


def open_state_database() -> sqlite3.Connection:
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        DATABASE_FILE.parent.chmod(0o700)
    except OSError:
        pass
    connection = sqlite3.connect(DATABASE_FILE, timeout=10, factory=_ManagedConnection)
    connection.row_factory = sqlite3.Row
    try:
        DATABASE_FILE.chmod(0o600)
    except OSError:
        pass
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
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA wal_autocheckpoint=1000")
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
        """
    )
    # 只做幂等补列/建表；版本号由 ensure_schema() 在迁移成功后写入。
    # 这里绝不能无条件写 user_version：那会把更高版本的库"降级"成旧结构继续用。
    return connection


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
            review = raw.get("review") if isinstance(raw.get("review"), dict) else None
            if review is not None:
                due = str(review.get("due") or "")[:10].strip()
                if due:
                    review_due = due
                review_learning = int(bool(review.get("learning")))
                log = review.get("log")
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
    existing_ids = {row[0] for row in connection.execute(
        "SELECT node_id FROM nodes WHERE project_id=?", (project_id,)
    )}
    for node in nodes:
        connection.execute(
            """INSERT INTO nodes(
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
                OR note<>excluded.note OR links<>excluded.links OR repeat<>excluded.repeat""",
            tuple(node[key] for key in (
                "project_id", "node_id", "id_json", "parent_id", "position", "type", "text",
                "completed", "optional", "assessment_required", "assessment_history", "expanded", "created_at",
                "completed_at", "review_due", "review_learning", "review_log",
                "priority", "due_date", "estimate_minutes", "tags", "note", "links", "repeat"
            )),
        )
        _write_assessment(connection, node, updated_at)
    removed_ids = existing_ids - set(node_ids)
    if removed_ids:
        connection.executemany(
            "DELETE FROM nodes WHERE project_id=? AND node_id=?",
            [(project_id, node_id) for node_id in removed_ids],
        )


def _write_assessment(connection: sqlite3.Connection, node: dict[str, Any], updated_at: str) -> None:
    project_id, node_id = node["project_id"], node["node_id"]
    assessment = node["assessment"]
    if assessment is None:
        connection.execute("DELETE FROM assessments WHERE project_id=? AND node_id=?", (project_id, node_id))
        return
    stored = dict(assessment)
    conversations_present = "questionConversations" in stored
    conversations = stored.pop("questionConversations", [])
    if conversations_present and isinstance(conversations, list):
        # Preserve empty question slots while message bodies live in their own table.
        stored["questionConversations"] = [[] for _ in conversations]
    payload = _json(stored)
    connection.execute(
        """INSERT INTO assessments(project_id,node_id,payload,updated_at) VALUES(?,?,?,?)
        ON CONFLICT(project_id,node_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at
        WHERE payload<>excluded.payload""",
        (project_id, node_id, payload, updated_at),
    )
    valid_keys: set[tuple[int, int]] = set()
    if conversations_present and isinstance(conversations, list):
        for question_index, messages in enumerate(conversations):
            if not isinstance(messages, list):
                continue
            for message_index, message in enumerate(messages):
                if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
                    continue
                key = (question_index, message_index)
                valid_keys.add(key)
                connection.execute(
                    """INSERT INTO conversations(
                        project_id,node_id,question_index,message_index,role,content
                    ) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(project_id,node_id,question_index,message_index) DO UPDATE SET
                        role=excluded.role,content=excluded.content
                    WHERE role<>excluded.role OR content<>excluded.content""",
                    (project_id, node_id, question_index, message_index,
                     message["role"], str(message.get("content", ""))),
                )
    # 只有 payload 真的带了 questionConversations 键时才做差集删除。
    # 否则（例如客户端只发 {"passed": true}）valid_keys 为空，会把该节点已有的逐题对话全部删掉。
    if conversations_present:
        for row in connection.execute(
            "SELECT question_index,message_index FROM conversations WHERE project_id=? AND node_id=?",
            (project_id, node_id),
        ):
            key = (int(row[0]), int(row[1]))
            if key not in valid_keys:
                connection.execute(
                    "DELETE FROM conversations WHERE project_id=? AND node_id=? AND question_index=? AND message_index=?",
                    (project_id, node_id, *key),
                )


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


def purge_trash_items(days: int = TRASH_RETENTION_DAYS) -> int:
    """删除早于 days 天的回收站条目（默认 7 天）。"""
    cutoff = (datetime.now() - timedelta(days=max(1, int(days)))).isoformat(timespec="seconds")
    with _database_lock, open_state_database() as connection:
        cursor = connection.execute(
            "DELETE FROM trash_items WHERE deleted_at < ?", (cutoff,)
        )
    return cursor.rowcount


def list_trash_items() -> list[dict[str, Any]]:
    purge_trash_items()
    
    with _database_lock, open_state_database() as connection:
        rows = connection.execute(
            "SELECT trash_id,kind,project_id,parent_id,position,title,context,deleted_at,revision "
            "FROM trash_items ORDER BY deleted_at DESC,trash_id"
        ).fetchall()
    items = []
    for row in rows:
        deleted_at = str(row["deleted_at"])
        expires = ""
        try:
            expires = (datetime.fromisoformat(deleted_at) + timedelta(days=TRASH_RETENTION_DAYS)).isoformat(
                timespec="seconds")
        except ValueError:
            expires = ""
        items.append({
            "id": row["trash_id"],
            "kind": row["kind"],
            "projectId": row["project_id"],
            "parentId": row["parent_id"],
            "position": int(row["position"]),
            "title": row["title"],
            "context": row["context"],
            "deletedAt": deleted_at,
            "expiresAt": expires,
            "revision": int(row["revision"]),
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
                _find_parent_and_insert(root.get("tree") or [], row["parent_id"], payload, int(row["position"]))
                _upsert_project(connection, root, int(connection.execute(
                    "SELECT position FROM projects WHERE project_id=?", (project_id,)
                ).fetchone()[0]), int(revision) + 1, _now())
            connection.execute("DELETE FROM trash_items WHERE trash_id=?", (trash_id,))
    return {"id": trash_id, "kind": kind}


def read_project_summaries() -> list[dict[str, Any]]:
    with _database_lock, open_state_database() as connection:
        rows = connection.execute("SELECT summary_json,revision FROM projects ORDER BY position,project_id").fetchall()
    result = []
    for row in rows:
        summary = _decode_object(row["summary_json"], "SQLite 中的项目摘要损坏")
        summary["_revision"] = int(row["revision"])
        result.append(summary)
    return result


def review_counts(today: str | None = None) -> dict[str, dict[str, int]]:
    """Live per-project review counts from the normalized review columns.

    Counts only completed items that still carry a scheduled review date.
    Returns {project_id: {"today": int, "overdue": int}}.
    """
    today = (today or date.today().isoformat())
    with _database_lock, open_state_database() as connection:
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


def read_project(project_id: Any) -> tuple[dict[str, Any], int] | None:
    with _database_lock, open_state_database() as connection:
        return _read_project_from_connection(connection, str(project_id))


def export_projects_snapshot() -> dict[str, Any]:
    """导出全部项目的完整快照，形状与前端"导入备份"（/api/import）兼容。

    刻意逐个读取完整项目，而不是复用 read_project_summaries() 的摘要：
    摘要里的 tree 是空的，直接导出会让未打开的项目变成空壳，导入后丢数据。
    整个导出必须在一把锁、一个连接里完成：分成两次加锁的话，中间新建的项目不会出现在
    导出结果里，而导入是"整体替换"语义，用这份 JSON 恢复就会把它删掉。
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
    return {
        "schemaVersion": EXPORT_SCHEMA_VERSION,
        "exportedAt": datetime.now().isoformat(timespec="seconds"),
        "projects": projects,
    }


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


def delete_project(project_id: Any, expected_revision: int) -> None:
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
            if project:
                stored_project, project_revision = project
                connection.execute(
                    """INSERT INTO trash_items(
                        trash_id,kind,project_id,parent_id,position,title,context,payload,deleted_at,revision
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        _new_trash_id(),
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
    if Path(name).name != name or not name.endswith(".sqlite3"):
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


def touch_project_opened(project_id: Any) -> None:
    with _database_lock, open_state_database() as connection:
        connection.execute(
            "UPDATE projects SET last_opened_at=? WHERE project_id=?",
            (datetime.now().isoformat(timespec="seconds"), str(project_id)),
        )


def _node_locations(connection: sqlite3.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    """每个节点的可读路径与祖先 id（工作台用于展示与定位）。"""
    rows = connection.execute("SELECT project_id,node_id,parent_id,text FROM nodes").fetchall()
    parent: dict[tuple[str, str], tuple[str | None, str]] = {}
    for row in rows:
        parent[(str(row["project_id"]), str(row["node_id"]))] = (row["parent_id"], str(row["text"] or ""))

    locations: dict[tuple[str, str], dict[str, Any]] = {}
    for key in parent:
        labels: list[str] = []
        ancestors: list[str] = []
        entry = parent.get(key)
        cursor: str | None = str(entry[0]) if entry and entry[0] is not None else None
        seen: set[str] = set()
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            ancestors.append(cursor)
            parent_entry = parent.get((key[0], cursor))
            if not parent_entry:
                break
            if parent_entry[1]:
                labels.append(parent_entry[1])
            cursor = str(parent_entry[0]) if parent_entry[0] is not None else None
        locations[key] = {"path": " / ".join(reversed(labels)), "ancestorIds": list(reversed(ancestors))}
    return locations


def workbench(today: str | None = None) -> dict[str, Any]:
    """今日工作台：逾期 / 今天 / 未来 7 天 / 今天要复习 / 收集箱。"""
    reference = clean_due_date(today) or date.today().isoformat()
    horizon = (date.fromisoformat(reference) + timedelta(days=WORKBENCH_HORIZON_DAYS)).isoformat()
    groups: dict[str, list[dict[str, Any]]] = {"overdue": [], "today": [], "next7": [], "reviewToday": [], "inbox": []}
    with _database_lock, open_state_database() as connection:
        project_names = {
            str(row["project_id"]): str(row["name"])
            for row in connection.execute("SELECT project_id,name FROM projects WHERE archived=0")
        }
        locations = _node_locations(connection)
        rows = connection.execute(
            """SELECT project_id,node_id,text,completed,priority,due_date,estimate_minutes,tags,
                      note,links,repeat,review_due,completed_at
               FROM nodes WHERE type='item'"""
        ).fetchall()
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
            if due:
                if due < reference:
                    groups["overdue"].append(dict(item, daysOverdue=_days_between(due, reference)))
                elif due == reference:
                    groups["today"].append(item)
                elif due <= horizon:
                    groups["next7"].append(dict(item, daysUntil=_days_between(reference, due)))
            if project_id == INBOX_PROJECT_ID:
                groups["inbox"].append(item)
        if completed and review_due and review_due <= reference:
            groups["reviewToday"].append(dict(item, reviewDue=review_due,
                                              daysOverdue=_days_between(review_due, reference)))
    priority_rank = {"high": 0, "mid": 1, "low": 2, "": 3}
    for key, items in groups.items():
        items.sort(key=lambda entry: (priority_rank.get(entry["priority"], 3),
                                      entry.get("dueDate") or entry.get("reviewDue") or "",
                                      entry["text"]))
    return {
        "today": reference,
        "serverToday": date.today().isoformat(),
        "horizonDays": WORKBENCH_HORIZON_DAYS,
        "groups": groups,
        "totals": {key: len(items) for key, items in groups.items()},
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
    with _database_lock, open_state_database() as connection:
        project_count = int(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
        node_count = int(connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
        conversation_count = int(connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])
        largest = 0
        total = 0
        for row in connection.execute("SELECT project_id FROM projects"):
            rebuilt = _read_project_from_connection(connection, row[0])
            size = len(_json(rebuilt[0]).encode("utf-8")) if rebuilt else 0
            total += size
            largest = max(largest, size)
    return {"databaseBytes": database_file_size(), "projectBytes": total,
            "largestProjectBytes": largest, "projectCount": project_count,
            "nodeCount": node_count, "conversationCount": conversation_count,
            "maxProjectBytes": MAX_PROJECT_PAYLOAD_BYTES, "schemaVersion": SCHEMA_VERSION}
