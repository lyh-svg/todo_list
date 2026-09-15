#!/usr/bin/env python3
"""Serve the todo app locally and proxy structured assessments to DeepSeek."""

from __future__ import annotations

import datetime
import json
import hmac
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import traceback
import urllib.parse
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import backup_service
import storage as storage_service
import ai_service
import memo_storage
import summary_storage

APP_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("TODO_AI_PORT", "8765"))
IDLE_SHUTDOWN_SECONDS = max(1, int(os.environ.get("TODO_IDLE_SHUTDOWN_SECONDS", "300")))
# Supports several small source files plus a short per-question conversation.
MAX_AI_REQUEST_BYTES = 5 * 1024 * 1024
MAX_STATE_REQUEST_BYTES = 110 * 1024 * 1024
SESSION_TOKEN = os.environ.get("TODO_SESSION_TOKEN", "") or secrets.token_urlsafe(32)
SESSION_TOKEN_FILE = Path(
    os.environ.get("TODO_SESSION_TOKEN_FILE", f"/tmp/todo-list-ai-{PORT}.token")
)
PUBLIC_PATHS = {"/", "/index.html", "/css/style.css", "/js/api-client.js", "/js/study-tools.js", "/js/app.js"}
# 这些静态资源的 URL 带 ?v= 版本号（见 index.html），可以放心缓存；入口 HTML 与所有 /api/* 仍用 no-store。
VERSIONED_STATIC_PATHS = {"/css/style.css", "/js/api-client.js", "/js/study-tools.js", "/js/app.js"}
STATIC_CACHE_CONTROL = "public, max-age=86400"
NO_STORE = "no-store"

_heartbeat_lock = threading.Lock()
_last_heartbeat = time.monotonic()
_shutdown_requested = threading.Event()

# The HTTP and AI layers use the dedicated normalized SQLite storage module.
# The aliases keep the handler surface small while old backups remain readable.
DATABASE_FILE = storage_service.DATABASE_FILE
BACKUP_DIR = storage_service.BACKUP_DIR
MAX_PROJECT_PAYLOAD_BYTES = storage_service.MAX_PROJECT_PAYLOAD_BYTES
StateConflictError = storage_service.StateConflictError
migrate_legacy_state = storage_service.migrate_legacy_state
ensure_schema = storage_service.ensure_schema
ensure_inbox_project = storage_service.ensure_inbox_project
add_inbox_item = storage_service.add_inbox_item
add_project_item = storage_service.add_project_item
move_node = storage_service.move_node
touch_project_opened = storage_service.touch_project_opened
list_saved_views = storage_service.list_saved_views
save_saved_view = storage_service.save_saved_view
delete_saved_view = storage_service.delete_saved_view
batch_update_nodes = storage_service.batch_update_nodes
workbench = storage_service.workbench
recent_overview = storage_service.recent_overview
SchemaVersionError = storage_service.SchemaVersionError
read_project_summaries = storage_service.read_project_summaries
read_project = storage_service.read_project
export_projects_snapshot = storage_service.export_projects_snapshot
write_project = storage_service.write_project
delete_project = storage_service.delete_project
harden_storage_permissions = storage_service.harden_storage_permissions
list_database_backups = backup_service.list_backups
create_full_backup = backup_service.create_full_backup
describe_backup = backup_service.describe_backup
restore_full_backup = backup_service.restore_full_backup
rename_backup = backup_service.rename_backup
delete_backup = backup_service.delete_backup
check_database_integrity = storage_service.check_database_integrity
checkpoint_database = storage_service.checkpoint_database
list_trash_items = storage_service.list_trash_items
restore_trash_items = storage_service.restore_trash_items
delete_trash_items = storage_service.delete_trash_items
clear_trash_items = storage_service.clear_trash_items
store_trash_item = storage_service.store_trash_item
restore_trash_item = storage_service.restore_trash_item
delete_trash_item = storage_service.delete_trash_item
CONFIG_FILE = ai_service.CONFIG_FILE
read_settings = ai_service.read_settings
model_aliases = ai_service.model_aliases
normalize_result = ai_service.normalize_result
call_deepseek = ai_service.call_deepseek
call_question = ai_service.call_question


def touch_heartbeat() -> None:
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = time.monotonic()


def valid_session(request: SimpleHTTPRequestHandler) -> bool:
    supplied = request.headers.get("X-Todo-Session", "")
    return bool(SESSION_TOKEN) and hmac.compare_digest(supplied, SESSION_TOKEN)


def idle_shutdown_monitor(server: ThreadingHTTPServer) -> None:
    check_interval = min(15, max(0.1, IDLE_SHUTDOWN_SECONDS / 2))
    while not _shutdown_requested.wait(check_interval):
        with _heartbeat_lock:
            idle_seconds = time.monotonic() - _last_heartbeat
        if idle_seconds >= IDLE_SHUTDOWN_SECONDS:
            print(f"No browser heartbeat for {IDLE_SHUTDOWN_SECONDS} seconds; stopping local service.")
            _shutdown_requested.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
            return


def allowed_origin(origin: str | None) -> bool:
    if not origin:
        return True
    return origin in {f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}


def query_params(request: Any) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(request.path).query)


def required_param(params: dict[str, list[str]], name: str) -> str:
    value = str(params.get(name, [""])[0]).strip()
    if not value:
        raise ValueError(f"缺少参数 {name}")
    return value


def int_param(params: dict[str, list[str]], name: str, *, required: bool = True, default: int = 0) -> int:
    raw = str(params.get(name, [""])[0]).strip()
    if not raw:
        if required:
            raise ValueError(f"缺少参数 {name}")
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"参数 {name} 必须是整数") from None


def optional_iso_date(value: str) -> str:
    """只接受 YYYY-MM-DD；非法就返回空串（调用方回落到服务端日期）。"""
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return ""
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return ""
    return text


class TodoHandler(SimpleHTTPRequestHandler):
    server_version = "TodoAI/1.0"
    # 客户端声明了 Content-Length 却中断发送时，读操作不能永远挂住这个线程。
    timeout = 60

    def log_message(self, format: str, *args: Any) -> None:
        if self.path == "/api/heartbeat":
            return
        super().log_message(format, *args)

    def end_headers(self) -> None:
        origin = self.headers.get("Origin")
        if allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin or "*")
            self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", getattr(self, "_cache_control", NO_STORE))
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # 客户端提前断开：正常情况，不必打堆栈。
            self.close_connection = True

    def send_evaluate_stream(self, payload: dict[str, Any]) -> None:
        """NDJSON 流式返回 AI 验收: {"type":"text","text":..} ... {"type":"result","result":..}"""
        try:
            generator = ai_service.call_deepseek_stream(payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.end_headers()
            for event in generator:
                line = json.dumps(event, ensure_ascii=False) + "\n"
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
        except Exception as error:
            try:
                line = json.dumps({"type": "error", "message": str(error)}, ensure_ascii=False) + "\n"
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

    def send_file(self, path: Path, content_type: str, download_name: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        try:
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def send_blob(self, payload: bytes, content_type: str, file_name: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("X-File-Name", urllib.parse.quote(file_name))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def read_body(self, length: int) -> bytes | None:
        """读请求体；客户端中途断开时不要抛异常打堆栈。"""
        try:
            return self.rfile.read(length)
        except (ConnectionError, OSError):
            self.close_connection = True
            return None

    def discard_body(self, length: int, *, limit: int = 64 * 1024) -> None:
        """错误响应前把请求体读掉。

        不读干净的 body 会让客户端收到连接重置，表现就是"HTTP 空回复"。
        只有"客户端几乎肯定已经发完"的小 body（≤64 KiB）才值得读掉；更大的直接关闭连接，
        绝不能在错误路径上去等一个可能永远不会到来的 body（那会把线程挂住）。
        """
        if length <= 0:
            return
        if length > limit:
            self.close_connection = True
            return
        remaining = length
        try:
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (ConnectionError, OSError):
            self.close_connection = True

    def do_OPTIONS(self) -> None:
        if not allowed_origin(self.headers.get("Origin")):
            self.send_json(403, {"error": "不允许的请求来源"})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Todo-Session")
        self.end_headers()

    def do_HEAD(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path not in PUBLIC_PATHS:
            self.send_response(404)
            self.end_headers()
            return
        if path in VERSIONED_STATIC_PATHS:
            self._cache_control = STATIC_CACHE_CONTROL
        self.path = path
        try:
            super().do_HEAD()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/health":
            self.send_json(200, {"ok": True})
            return
        if path == "/api/backup/download":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            supplied = self.headers.get("X-Todo-Session", "") or query.get("token", [""])[0]
            if not hmac.compare_digest(supplied, SESSION_TOKEN):
                self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
                return
            name = query.get("name", [""])[0]
            if Path(name).name != name or not (name.endswith(".sqlite3") or name.endswith(".zip")):
                self.send_json(400, {"error": "备份文件名不正确"})
                return
            backup = BACKUP_DIR / name
            if not backup.is_file():
                self.send_json(404, {"error": "备份不存在"})
                return
            content_type = "application/zip" if name.endswith(".zip") else "application/vnd.sqlite3"
            self.send_file(backup, content_type, name)
            return
        if path == "/api/export":
            # 与 /api/backup/download 同理：浏览器直接下载带不了自定义头，允许查询串 token。
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            supplied = self.headers.get("X-Todo-Session", "") or query.get("token", [""])[0]
            if not hmac.compare_digest(supplied, SESSION_TOKEN):
                self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
                return
            try:
                snapshot = export_projects_snapshot()
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"导出项目失败：{error}"})
                return
            body = json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="todo-projects-{time.strftime("%Y%m%d")}.json"',
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith("/api/") and path not in {"/api/config"} and not valid_session(self):
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        if path == "/api/config" and not valid_session(self):
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        if path == "/api/projects":
            try:
                # 复习计数用"浏览器本地日期"，避免 WSL 与宿主时区不同导致午夜前后差一天。
                requested_today = optional_iso_date(query_params(self).get("today", [""])[0])
                server_today = datetime.date.today().isoformat()
                summaries = read_project_summaries()
                counts = storage_service.review_counts(requested_today or server_today)
                totals = {"today": 0, "overdue": 0}
                for summary in summaries:
                    bucket = counts.get(str(summary.get("id")), {"today": 0, "overdue": 0})
                    summary["reviewToday"] = bucket["today"]
                    summary["reviewOverdue"] = bucket["overdue"]
                    totals["today"] += bucket["today"]
                    totals["overdue"] += bucket["overdue"]
                self.send_json(200, {
                    "projects": summaries,
                    "reviewTotals": totals,
                    "serverToday": server_today,
                    "usedToday": requested_today or server_today,
                })
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取项目列表失败：{error}"})
            return
        if path == "/api/project":
            try:
                project_id = required_param(query_params(self), "id")
                result = read_project(project_id)
                if not result:
                    self.send_json(404, {"error": "项目不存在"})
                else:
                    project, revision = result
                    if not project.get("archived"):
                        touch_project_opened(project_id)
                    self.send_json(200, {"project": project, "revision": revision})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取项目失败：{error}"})
            return
        if path == "/api/views":
            try:
                self.send_json(200, {"views": list_saved_views()})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取筛选视图失败：{error}"})
            return
        if path == "/api/workbench":
            try:
                today = optional_iso_date(query_params(self).get("today", [""])[0])
                self.send_json(200, workbench(today or None))
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                self.send_json(500, {"error": f"读取今日工作台失败：{error}"})
            return
        if path == "/api/recent":
            try:
                self.send_json(200, recent_overview())
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取最近记录失败：{error}"})
            return
        if path == "/api/inbox":
            try:
                project, revision = ensure_inbox_project()
                self.send_json(200, {"ok": True, "project": project, "revision": revision,
                                     "summary": storage_service.project_summary(project)})
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                self.send_json(500, {"error": f"读取收集箱失败：{error}"})
            return
        if path == "/api/heartbeat":
            touch_heartbeat()
            self.send_json(200, {"ok": True})
            return
        if path == "/api/config":
            settings = read_settings()
            ready = bool(settings.get("DEEPSEEK_API_KEY"))
            self.send_json(
                200,
                {
                    "ready": ready,
                    "models": model_aliases(settings),
                    "error": "" if ready else f"请编辑 {CONFIG_FILE.name} 并填写 DEEPSEEK_API_KEY",
                },
            )
            return
        if path == "/api/storage":
            try:
                diagnostics = storage_service.storage_diagnostics()
                self.send_json(
                    200,
                    {
                        **diagnostics,
                        "stateBytes": diagnostics["projectBytes"],
                        "projectLimitBytes": MAX_PROJECT_PAYLOAD_BYTES,
                        "stateLimitBytes": MAX_PROJECT_PAYLOAD_BYTES,
                        "aiRequestLimitBytes": MAX_AI_REQUEST_BYTES,
                        "stateRequestLimitBytes": MAX_STATE_REQUEST_BYTES,
                        "requestLimitBytes": MAX_AI_REQUEST_BYTES,
                        "backupDirectory": str(BACKUP_DIR),
                    },
                )
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取 SQLite 信息失败：{error}"})
            return
        if path == "/api/backups":
            try:
                self.send_json(200, {"backups": list_database_backups()})
            except (OSError, RuntimeError) as error:
                self.send_json(500, {"error": f"读取备份列表失败：{error}"})
            return
        if path == "/api/backup/inspect":
            try:
                name = required_param(query_params(self), "name")
                self.send_json(200, {"backup": describe_backup(name)})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                self.send_json(500, {"error": f"读取备份内容失败：{error}"})
            return
        if path == "/api/trash":
            try:
                self.send_json(200, {"items": list_trash_items()})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取回收站失败：{error}"})
            return
        if path == "/api/background":
            try:
                row = storage_service.read_asset("background")
                if not row:
                    self.send_json(404, {"error": "未设置背景"})
                else:
                    self.send_blob(bytes(row[0]), str(row[1]), str(row[2]))
            except (OSError, sqlite3.Error) as error:
                self.send_json(500, {"error": f"读取背景失败：{error}"})
            return
        if path == "/api/summaries":
            try:
                self.send_json(200, {"summaries": summary_storage.list_summaries()})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取摘要清单失败：{error}"})
            return
        if path == "/api/memos":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("q", [""])[0]
            try:
                memos = (memo_storage.search_memo_summaries(query) if query.strip()
                         else memo_storage.list_memo_summaries())
                self.send_json(200, {"memos": memos, "databaseBytes": memo_storage.database_size()})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取备忘录失败：{error}"})
            return
        if path == "/api/memo":
            try:
                memo_id = required_param(query_params(self), "id")
                memo = memo_storage.read_memo(memo_id)
                if not memo:
                    self.send_json(404, {"error": "备忘录不存在"})
                else:
                    self.send_json(200, {"memo": memo})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取备忘录失败：{error}"})
            return
        if path == "/api/memos/database-download":
            memo_storage.checkpoint()
            self.send_file(memo_storage.MEMO_DATABASE_FILE, "application/vnd.sqlite3", "memo.sqlite3")
            return
        if path not in PUBLIC_PATHS:
            self.send_json(404, {"error": "资源不存在"})
            return
        if path in VERSIONED_STATIC_PATHS:
            self._cache_control = STATIC_CACHE_CONTROL
        self.path = path
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            # 客户端在下载静态文件时断开：正常情况，不要打堆栈。
            self.close_connection = True

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path not in {"/api/evaluate", "/api/question", "/api/project", "/api/import", "/api/backup",
                        "/api/inbox/add", "/api/inbox/move", "/api/views", "/api/batch",
                        "/api/background",
                        "/api/memo", "/api/memos/database-import",
                        "/api/trash",
                        "/api/summary",
                        "/api/project/plan"}:
            self.send_json(404, {"error": "接口不存在"})
            return
        if not valid_session(self):
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        if not allowed_origin(self.headers.get("Origin")):
            self.send_json(403, {"error": "不允许的请求来源"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        request_limit = 110 * 1024 * 1024 if path == "/api/memos/database-import" else (
            30 * 1024 * 1024 if path == "/api/background" else (
                MAX_STATE_REQUEST_BYTES if path in {"/api/project", "/api/import"} else MAX_AI_REQUEST_BYTES
            ))
        if length <= 0 or length > request_limit:
            self.discard_body(length)
            self.send_json(413, {"error": "请求内容为空或过大"})
            return
        if path == "/api/background":
            # 先把 body 读完：任何校验失败都不会留下未读数据（否则客户端看到的是空回复/连接重置）。
            blob = self.read_body(length)
            if blob is None:
                return
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            file_name = query.get("name", ["background"])[0][:200]
            mime_type = query.get("type", ["application/octet-stream"])[0][:100]
            try:
                if not mime_type.startswith("image/"):
                    raise ValueError("背景文件必须是图片")
                if len(blob) > 25 * 1024 * 1024:
                    raise ValueError("背景图片不能超过 25 MB")
                storage_service.write_asset("background", blob, mime_type, file_name)
                self.send_json(200, {"ok": True})
            except ValueError as error:
                self.send_json(400, {"error": f"保存背景失败：{error}"})
            except (OSError, sqlite3.Error) as error:
                self.send_json(500, {"error": f"保存背景失败：{error}"})
            return
        if path == "/api/memos/database-import":
            try:
                raw = self.read_body(length)
                if raw is None:
                    return
                memo_storage.import_database(raw)
                self.send_json(200, {"ok": True, "memos": memo_storage.list_memo_summaries()})
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                self.send_json(400, {"error": f"导入备忘录数据库失败：{error}"})
            return
        try:
            raw_body = self.read_body(length)
            if raw_body is None:
                return
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("请求必须是 JSON 对象")
            if path == "/api/backup":
                action = str(payload.get("action", "create"))
                if action == "create":
                    self.send_json(200, {"ok": True, "name": create_full_backup("manual")})
                elif action == "rename":
                    name = rename_backup(str(payload.get("name", "")), str(payload.get("newName", "")))
                    self.send_json(200, {"ok": True, "name": name})
                elif action == "delete":
                    delete_backup(str(payload.get("name", "")))
                    self.send_json(200, {"ok": True})
                elif action == "restore":
                    result = restore_full_backup(str(payload.get("name", "")))
                    self.send_json(200, {"ok": True, **result})
                elif action == "snapshot":
                    reason = str(payload.get("reason") or "before-bulk")[:40]
                    safe = re.sub(r"[^\w\-]", "-", reason) or "before-bulk"
                    self.send_json(200, {"ok": True, "name": create_full_backup(f"before-{safe}")})
                else:
                    raise ValueError("不支持的备份操作")
            elif path == "/api/project":
                project = payload.get("project")
                if not isinstance(project, dict):
                    raise ValueError("项目格式不正确")
                expected_revision = payload.get("expectedRevision")
                if expected_revision is not None:
                    try:
                        expected_revision = int(expected_revision)
                    except (TypeError, ValueError):
                        raise ValueError("expectedRevision 格式不正确") from None
                revision, summary = write_project(project, expected_revision)
                self.send_json(200, {"ok": True, "revision": revision, "summary": summary})
            elif path == "/api/import":
                projects = payload.get("projects")
                if not isinstance(projects, list):
                    raise ValueError("导入项目格式不正确")
                create_full_backup("before-import")
                storage_service.replace_projects(projects, pre_backup=False)
                self.send_json(200, {"ok": True, "projects": read_project_summaries()})
            elif path == "/api/views":
                saved = save_saved_view(payload.get("name"), payload.get("payload"))
                self.send_json(200, {"ok": True, "view": saved, "views": list_saved_views()})
            elif path == "/api/batch":
                targets = payload.get("targets")
                action = str(payload.get("action") or "")
                result = batch_update_nodes(targets, action, payload.get("value"))
                self.send_json(200, {"ok": True, **result})
            elif path == "/api/inbox/add":
                node = payload.get("node")
                if not isinstance(node, dict):
                    raise ValueError("任务格式不正确")
                target = str(payload.get("projectId") or storage_service.INBOX_PROJECT_ID)
                parent_id = payload.get("parentId")
                self.send_json(200, {"ok": True, **add_project_item(
                    target, node, str(parent_id) if parent_id else None)})
            elif path == "/api/inbox/move":
                node_id = str(payload.get("nodeId") or "")
                from_project = str(payload.get("fromProjectId") or storage_service.INBOX_PROJECT_ID)
                to_project = str(payload.get("toProjectId") or "")
                if not node_id or not to_project:
                    raise ValueError("缺少 nodeId 或 toProjectId")
                parent_id = payload.get("parentId")
                position = payload.get("position")
                moved = move_node(node_id, from_project, to_project,
                                  str(parent_id) if parent_id is not None else None,
                                  int(position) if position is not None else None)
                self.send_json(200, {"ok": True, **moved, "projects": read_project_summaries()})
            elif path == "/api/question":
                self.send_json(200, call_question(payload))
            elif path == "/api/memo":
                memo = memo_storage.write_memo(payload)
                self.send_json(200, {"ok": True, "memo": memo})
            elif path == "/api/trash":
                action = str(payload.get("action") or "store")
                if action == "store":
                    item = payload.get("item")
                    if not isinstance(item, dict):
                        raise ValueError("回收站条目格式不正确")
                    saved = store_trash_item(
                        str(item.get("kind") or "node"),
                        item.get("projectId"),
                        str(item.get("title") or "未命名条目"),
                        item.get("payload") if isinstance(item.get("payload"), dict) else {},
                        parent_id=item.get("parentId"),
                        position=int(item.get("position") or 0),
                        context=str(item.get("context") or ""),
                        revision=int(item.get("revision") or 0),
                    )
                    self.send_json(200, {"ok": True, "item": saved, "items": list_trash_items()})
                elif action == "restore":
                    trash_id = str(payload.get("id") or "")
                    if not trash_id or not any(entry["id"] == trash_id for entry in list_trash_items()):
                        self.send_json(404, {"error": "回收站条目不存在"})
                        return
                    result = restore_trash_item(trash_id)
                    self.send_json(200, {"ok": True, "item": result, "items": list_trash_items(), "projects": read_project_summaries()})
                elif action == "delete":
                    trash_id = str(payload.get("id") or "")
                    if not trash_id or not any(entry["id"] == trash_id for entry in list_trash_items()):
                        self.send_json(404, {"error": "回收站条目不存在"})
                        return
                    delete_trash_item(trash_id)
                    self.send_json(200, {"ok": True, "items": list_trash_items()})
                elif action in {"restore-many", "delete-many"}:
                    ids = payload.get("ids")
                    if not isinstance(ids, list) or not ids:
                        raise ValueError("请先选择要处理的回收站条目")
                    known = {entry["id"] for entry in list_trash_items()}
                    unknown = [str(item) for item in ids if str(item) not in known]
                    if unknown:
                        self.send_json(404, {"error": f"有 {len(unknown)} 条记录已不在回收站，请刷新后重试"})
                        return
                    if action == "restore-many":
                        result = restore_trash_items(ids)
                        self.send_json(200, {"ok": True, **result, "items": list_trash_items(),
                                             "projects": read_project_summaries()})
                    else:
                        result = delete_trash_items(ids)
                        self.send_json(200, {"ok": True, **result, "items": list_trash_items()})
                elif action == "purge":
                    removed = clear_trash_items()
                    self.send_json(200, {"ok": True, "purged": removed, "items": list_trash_items()})
                else:
                    raise ValueError("不支持的回收站操作")
            elif path == "/api/project/plan":
                topic = str(payload.get("topic") or "").strip()[:2000]
                model = str(payload.get("model") or "flash")
                if not topic:
                    raise ValueError("学习主题不能为空")
                plan = ai_service.plan_project(topic, model)
                self.send_json(200, {"ok": True, "plan": plan})
            elif path == "/api/summary":
                question = str(payload.get("question") or "").strip()[:4000]
                context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
                model = str(payload.get("model") or "flash")
                if not question:
                    raise ValueError("题目不能为空")
                result = ai_service.summarize_knowledge(question, context, model)
                saved = summary_storage.upsert_summary(question, result["summary"])
                self.send_json(200, {"ok": True, "summary": saved})
            elif path == "/api/evaluate":
                if payload.get("stream"):
                    self.send_evaluate_stream(payload)
                else:
                    result = call_deepseek(payload)
                    self.send_json(200, {"result": result})
        except StateConflictError as error:
            self.send_json(409, {"error": str(error)})
        except memo_storage.MemoConflictError as error:
            self.send_json(409, {"error": str(error)})
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": "本地 AI 服务发生未预期错误"})

    def do_DELETE(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path not in {"/api/project", "/api/background", "/api/memo", "/api/summary", "/api/summaries",
                        "/api/views"}:
            self.send_json(404, {"error": "接口不存在"})
            return
        if not valid_session(self) or not allowed_origin(self.headers.get("Origin")):
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        # 所有分支都在 try 里：参数缺失/非法 → 400，资源不存在 → 404，版本冲突 → 409，
        # 绝不把异常抛到 HTTP 层（那会变成"空回复"）。
        params = query_params(self)
        try:
            if path == "/api/views":
                view_id = required_param(params, "id")
                if not delete_saved_view(view_id):
                    self.send_json(404, {"error": "视图不存在"})
                    return
                self.send_json(200, {"ok": True, "views": list_saved_views()})
                return
            if path == "/api/summary":
                summary_id = required_param(params, "id")
                if not summary_storage.delete_summary(summary_id):
                    self.send_json(404, {"error": "摘要不存在"})
                    return
                self.send_json(200, {"ok": True, "summaries": summary_storage.list_summaries()})
                return
            if path == "/api/summaries":
                summary_storage.clear_summaries()
                self.send_json(200, {"ok": True, "summaries": summary_storage.list_summaries()})
                return
            if path == "/api/background":
                storage_service.delete_asset("background")
                self.send_json(200, {"ok": True})
                return
            if path == "/api/memo":
                memo_id = required_param(params, "id")
                expected_revision = int_param(params, "revision")
                if not memo_storage.read_memo(memo_id):
                    self.send_json(404, {"error": "备忘录不存在"})
                    return
                memo_storage.delete_memo(memo_id, expected_revision)
                self.send_json(200, {"ok": True, "memos": memo_storage.list_memo_summaries()})
                return
            project_id = required_param(params, "id")
            expected_revision = int_param(params, "revision")
            if read_project(project_id) is None:
                self.send_json(404, {"error": "项目不存在"})
                return
            delete_project(project_id, expected_revision)
            self.send_json(200, {"ok": True})
        except StateConflictError as error:
            self.send_json(409, {"error": str(error)})
        except memo_storage.MemoConflictError as error:
            self.send_json(409, {"error": str(error)})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
        except (TypeError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})
        except (OSError, sqlite3.Error) as error:
            self.send_json(500, {"error": f"删除失败：{error}"})
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": "本地服务发生未预期错误"})


def main() -> None:
    os.umask(0o077)
    harden_storage_permissions()
    if not check_database_integrity():
        raise RuntimeError(
            f"SQLite integrity check failed; restore a backup from {BACKUP_DIR}"
        )
    ensure_schema()
    backup_service.create_daily_snapshot()
    storage_service.purge_trash_items()
    memo_storage.initialize()
    if not memo_storage.check_integrity():
        raise RuntimeError("备忘录 SQLite 完整性检查失败")
    summary_storage.initialize()
    if not summary_storage.check_integrity():
        raise RuntimeError("摘要清单 SQLite 完整性检查失败")
    SESSION_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_TOKEN_FILE.write_text(SESSION_TOKEN, encoding="utf-8")
    SESSION_TOKEN_FILE.chmod(0o600)
    handler = partial(TodoHandler, directory=str(APP_DIR))
    server = ThreadingHTTPServer((HOST, PORT), handler)
    threading.Thread(target=idle_shutdown_monitor, args=(server,), daemon=True).start()
    print(f"Todo AI running at http://{HOST}:{PORT}/?token={SESSION_TOKEN}")
    if not read_settings().get("DEEPSEEK_API_KEY"):
        print(f"Set DEEPSEEK_API_KEY in {CONFIG_FILE}; the file is reloaded for every assessment.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Todo AI.")
    finally:
        _shutdown_requested.set()
        checkpoint_database()
        server.server_close()
        try:
            if SESSION_TOKEN_FILE.read_text(encoding="utf-8").strip() == SESSION_TOKEN:
                SESSION_TOKEN_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"Unable to start local server: {error}", file=sys.stderr)
        raise SystemExit(1)
