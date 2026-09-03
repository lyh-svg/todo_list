#!/usr/bin/env python3
"""SQLite persistence, migration, backup, and recovery for the todo app."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
from datetime import datetime
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
MAX_DATABASE_BACKUPS = 30
SCHEMA_VERSION = 4

_database_lock = threading.RLock()


class StateConflictError(RuntimeError):
    pass


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


def open_state_database() -> sqlite3.Connection:
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        DATABASE_FILE.parent.chmod(0o700)
    except OSError:
        pass
    connection = sqlite3.connect(DATABASE_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        DATABASE_FILE.chmod(0o600)
    except OSError:
        pass
    connection.execute("PRAGMA foreign_keys=ON")
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
        """
    )
    node_columns = {row[1] for row in connection.execute("PRAGMA table_info(nodes)")}
    if "completed_at" not in node_columns:
        connection.execute("ALTER TABLE nodes ADD COLUMN completed_at TEXT NOT NULL DEFAULT ''")
    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
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
        "stats": {
            "total": total,
            "remaining": remaining,
            "optionalTotal": optional_total,
            "optionalCompleted": optional_completed,
        },
    }


def _flatten_nodes(project_id: str, nodes: Any, parent_id: str | None = None) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    if not isinstance(nodes, list):
        return flattened
    for position, raw in enumerate(nodes):
        if not isinstance(raw, dict) or raw.get("id") is None:
            raise ValueError("项目中存在无效节点")
        node_type = str(raw.get("type", ""))
        if node_type not in {"week", "day", "item"}:
            raise ValueError("项目中存在未知节点类型")
        node_id = str(raw["id"])
        assessment = raw.get("assessment") if isinstance(raw.get("assessment"), dict) else None
        flattened.append({
            "project_id": project_id,
            "node_id": node_id,
            "id_json": _json(raw["id"]),
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
            "assessment": assessment,
        })
        flattened.extend(_flatten_nodes(project_id, raw.get("children"), node_id))
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
    connection.execute(
        """INSERT INTO projects(
            project_id,id_json,position,name,description,created_at,
            assessment_enabled,revision,updated_at,summary_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(project_id) DO UPDATE SET
            id_json=excluded.id_json, position=excluded.position, name=excluded.name,
            description=excluded.description, created_at=excluded.created_at,
            assessment_enabled=excluded.assessment_enabled,
            revision=excluded.revision, updated_at=excluded.updated_at,
            summary_json=excluded.summary_json""",
        (project_id, _json(project["id"]), position, str(project.get("name", "未命名项目")),
         str(project.get("description", "")), str(project.get("createdAt", "")),
         int(bool(project.get("assessmentEnabled"))), revision, updated_at, _json(summary)),
    )
    existing_ids = {row[0] for row in connection.execute(
        "SELECT node_id FROM nodes WHERE project_id=?", (project_id,)
    )}
    for node in nodes:
        connection.execute(
            """INSERT INTO nodes(
                project_id,node_id,id_json,parent_id,position,type,text,completed,
                optional,assessment_required,assessment_history,expanded,created_at,completed_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(project_id,node_id) DO UPDATE SET
                id_json=excluded.id_json,parent_id=excluded.parent_id,position=excluded.position,
                type=excluded.type,text=excluded.text,completed=excluded.completed,
                optional=excluded.optional,assessment_required=excluded.assessment_required,
                assessment_history=excluded.assessment_history,expanded=excluded.expanded,
                created_at=excluded.created_at,completed_at=excluded.completed_at
            WHERE id_json<>excluded.id_json OR parent_id IS NOT excluded.parent_id
                OR position<>excluded.position OR type<>excluded.type OR text<>excluded.text
                OR completed<>excluded.completed OR optional<>excluded.optional
                OR assessment_required<>excluded.assessment_required
                OR assessment_history<>excluded.assessment_history
                OR expanded<>excluded.expanded OR created_at<>excluded.created_at
                OR completed_at<>excluded.completed_at""",
            tuple(node[key] for key in (
                "project_id", "node_id", "id_json", "parent_id", "position", "type", "text",
                "completed", "optional", "assessment_required", "assessment_history", "expanded", "created_at",
                "completed_at"
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
    if isinstance(conversations, list):
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
        "tree": [],
    }
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


def read_project_summaries() -> list[dict[str, Any]]:
    with _database_lock, open_state_database() as connection:
        rows = connection.execute("SELECT summary_json,revision FROM projects ORDER BY position,project_id").fetchall()
    result = []
    for row in rows:
        summary = _decode_object(row["summary_json"], "SQLite 中的项目摘要损坏")
        summary["_revision"] = int(row["revision"])
        result.append(summary)
    return result


def read_project(project_id: Any) -> tuple[dict[str, Any], int] | None:
    with _database_lock, open_state_database() as connection:
        return _read_project_from_connection(connection, str(project_id))


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
            row = connection.execute("SELECT revision FROM projects WHERE project_id=?", (str(project_id),)).fetchone()
            if not row:
                raise StateConflictError("项目已经被删除")
            if int(row[0]) != expected_revision:
                raise StateConflictError(f"项目已被其他页面更新（当前版本 {int(row[0])}）")
            connection.execute("DELETE FROM projects WHERE project_id=?", (str(project_id),))


def replace_projects(projects: list[dict[str, Any]]) -> None:
    """Atomically replace every project, used only by explicit JSON import."""
    encoded = _json(projects).encode("utf-8")
    if len(encoded) > 110 * 1024 * 1024:
        raise ValueError("导入数据过大")
    with _database_lock:
        create_manual_database_backup("before-import")
        with open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM projects")
            now = datetime.now().isoformat(timespec="seconds")
            for position, project in enumerate(projects):
                if len(_json(project).encode("utf-8")) > MAX_PROJECT_PAYLOAD_BYTES:
                    raise ValueError("导入中存在超过 50 MB 的单个项目")
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
    with sqlite3.connect(source, timeout=10) as source_connection:
        with sqlite3.connect(target) as destination:
            source_connection.backup(destination)
    target.chmod(0o600)
    with sqlite3.connect(f"file:{target}?mode=ro&immutable=1", uri=True) as connection:
        result = connection.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError("数据库备份完整性检查失败")


def create_database_backup() -> None:
    if not DATABASE_FILE.exists():
        return
    with _database_lock:
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d")
            target = BACKUP_DIR / f"todo-{stamp}.sqlite3"
            marker = BACKUP_DIR / f".write-backup-{stamp}"
            if marker.exists():
                return
            with open_state_database() as connection:
                has_projects = connection.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
                has_legacy_table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='project_state'"
                ).fetchone()
                has_legacy_rows = has_legacy_table and connection.execute(
                    "SELECT 1 FROM project_state LIMIT 1"
                ).fetchone()
                if not has_projects and not has_legacy_rows:
                    return
            _validated_backup(DATABASE_FILE, target)
            marker.touch(mode=0o600, exist_ok=True)
            backups = sorted(BACKUP_DIR.glob("todo-*.sqlite3"), key=lambda path: path.stat().st_mtime, reverse=True)
            for stale in backups[MAX_DATABASE_BACKUPS:]:
                stale.unlink(missing_ok=True)
        except (OSError, sqlite3.Error) as error:
            print(f"Unable to create SQLite backup: {error}", file=sys.stderr)


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
        try:
            stat = path.stat()
            backups.append({"name": path.name, "bytes": stat.st_size,
                            "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                            "valid": stat.st_size > 0})
        except OSError:
            backups.append({"name": path.name, "bytes": 0, "modifiedAt": "", "valid": False})
    return backups


def rename_database_backup(old_name: str, new_name: str) -> str:
    """Rename a backup without changing its SQLite contents."""
    if Path(old_name).name != old_name or not old_name.endswith(".sqlite3"):
        raise ValueError("原备份文件名不正确")
    new_name = str(new_name).strip()
    if not new_name.endswith(".sqlite3"):
        new_name += ".sqlite3"
    if (
        Path(new_name).name != new_name
        or len(new_name) > 100
        or new_name.startswith(".")
        or not re.fullmatch(r"[\w.\- ()（）]+\.sqlite3", new_name, flags=re.UNICODE)
    ):
        raise ValueError("新名称只能包含字母、数字、中文、空格、括号、下划线、连字符和点")
    with _database_lock:
        source = BACKUP_DIR / old_name
        target = BACKUP_DIR / new_name
        if not source.is_file():
            raise ValueError("备份不存在")
        if target.exists() and target != source:
            raise ValueError("该备份名称已经存在")
        if target != source:
            source.replace(target)
            target.chmod(0o600)
    return new_name


def delete_database_backup(name: str) -> None:
    if Path(name).name != name or not name.endswith(".sqlite3"):
        raise ValueError("备份文件名不正确")
    with _database_lock:
        target = BACKUP_DIR / name
        if not target.is_file():
            raise ValueError("备份不存在")
        target.unlink()


def restore_database_backup(name: str) -> None:
    if Path(name).name != name or not name.endswith(".sqlite3"):
        raise ValueError("备份文件名不正确")
    source = BACKUP_DIR / name
    if not source.is_file():
        raise ValueError("备份不存在")
    with _database_lock:
        with sqlite3.connect(f"file:{source}?mode=ro&immutable=1", uri=True) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("备份完整性检查失败，不能恢复")
        emergency_name = create_manual_database_backup("before-restore")
        emergency = BACKUP_DIR / emergency_name
        try:
            _restore_database_file(source)
            migrate_legacy_state()
            if not check_database_integrity():
                raise RuntimeError("恢复后的数据库完整性检查失败")
        except Exception:
            _restore_database_file(emergency)
            raise


def _restore_database_file(source: Path) -> None:
    source_uri = f"file:{source}?mode=ro&immutable=1"
    with sqlite3.connect(source_uri, uri=True) as backup:
        with sqlite3.connect(DATABASE_FILE, timeout=10) as destination:
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