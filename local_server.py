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
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import backup_service
import storage as storage_service
import ai_service
import memo_storage
import review_storage
import review_content

APP_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("TODO_AI_PORT", "8765"))
IDLE_SHUTDOWN_SECONDS = max(1, int(os.environ.get("TODO_IDLE_SHUTDOWN_SECONDS", "300")))
# Supports several small source files plus a short per-question conversation.
# workbench 的变更指纹最长就这么长；更长的 since 一律当没传（反正也不可能相等）。
MAX_SINCE_CHARS = 120
MAX_AI_REQUEST_BYTES = 5 * 1024 * 1024
MAX_STATE_REQUEST_BYTES = 110 * 1024 * 1024
# 备忘录正文本身允许到 50 MB（memo_storage.MAX_MEMO_CONTENT_BYTES），HTTP 上限必须不低于它，
# 否则 5–50 MB 的备忘录会永远存不进去（旧上限只给了 5 MB）。
MAX_MEMO_REQUEST_BYTES = 60 * 1024 * 1024
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
add_project_item = storage_service.add_project_item
move_node = storage_service.move_node
touch_project_opened = storage_service.touch_project_opened
batch_update_nodes = storage_service.batch_update_nodes
patch_project_nodes = storage_service.patch_project_nodes
reorder_node = storage_service.reorder_node
duplicate_node = storage_service.duplicate_node
duplicate_project = storage_service.duplicate_project
describe_node_delete = storage_service.describe_node_delete
preview_import = storage_service.preview_import
import_projects = storage_service.import_projects
import_review_snapshot = storage_service.import_review_snapshot
list_templates = storage_service.list_templates
create_project_from_template = storage_service.create_project_from_template
log_activity = storage_service.log_activity
read_app_settings = storage_service.read_app_settings
update_app_settings = storage_service.update_app_settings
export_markdown = storage_service.export_markdown
export_csv = storage_service.export_csv
workbench = storage_service.workbench
recent_overview = storage_service.recent_overview
list_review_queue = storage_service.list_review_queue
search_everything = storage_service.search_everything
SchemaVersionError = storage_service.SchemaVersionError
read_project_summaries = storage_service.read_project_summaries
read_project = storage_service.read_project
export_projects_snapshot = storage_service.export_projects_snapshot
write_project = storage_service.write_project
write_project_with_occurrences = storage_service.write_project_with_occurrences
delete_project = storage_service.delete_project
harden_storage_permissions = storage_service.harden_storage_permissions
list_database_backups = backup_service.list_backups
create_full_backup = backup_service.create_full_backup
restore_full_backup = backup_service.restore_full_backup
delete_backup = backup_service.delete_backup
check_database_integrity = storage_service.check_database_integrity
checkpoint_database = storage_service.checkpoint_database
list_trash_items = storage_service.list_trash_items
trash_item_ids = storage_service.trash_item_ids
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

    def handle_one_request(self) -> None:
        # _cache_control 是实例属性，必须在每个请求开始时重置：
        # 万一同一个连接被复用（keep-alive），静态资源的 max-age 会漏到 API 响应上，
        # 让浏览器把接口结果缓存一天。默认永远是 no-store，只有明确的静态资源才改。
        self._cache_control = NO_STORE
        super().handle_one_request()

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
        """读请求体；客户端中途断开时不要抛异常打堆栈。

        注意：返回的字节数可能少于 length（客户端声明了 Content-Length 却提前关闭连接）。
        调用方必须自己比对长度（尤其是二进制上传），否则会把半截数据当完整数据入库。
        """
        try:
            payload = self.rfile.read(length)
        except (ConnectionError, OSError):
            self.close_connection = True
            return None
        if len(payload) != length:
            self.close_connection = True
        return payload

    def request_length(self) -> int:
        """请求体长度（错误路径上也要用它把 body 读干净，否则客户端收到的是连接重置）。"""
        try:
            return max(0, int(self.headers.get("Content-Length", "0") or 0))
        except (TypeError, ValueError):
            return 0

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
        # GET 也可能有副作用（例如 /api/project 会更新"最近打开"），来源校验必须和 POST/DELETE 一致。
        if path.startswith("/api/") and not allowed_origin(self.headers.get("Origin")):
            self.discard_body(self.request_length())
            self.send_json(403, {"error": "不允许的请求来源"})
            return
        if path == "/api/backup/download":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            # 只认请求头：以前允许 ?token= 是因为"浏览器直接点链接带不了自定义头"，
            # 但那样 token 会留在浏览器历史和服务端日志里。前端现在改成 fetch + Blob
            # （与备忘录库导出同一套写法），URL 里不再需要 token。
            supplied = self.headers.get("X-Todo-Session", "")
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
            # 与 /api/backup/download 同理：只认请求头，token 不进 URL。
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            supplied = self.headers.get("X-Todo-Session", "")
            if not hmac.compare_digest(supplied, SESSION_TOKEN):
                self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
                return
            export_format = str(query.get("format", ["json"])[0] or "json").lower()
            if export_format in {"md", "markdown"}:
                export_format = "markdown"
            if export_format not in {"json", "markdown", "csv"}:
                self.send_json(400, {"error": "不支持的导出格式"})
                return
            stamp = time.strftime("%Y%m%d")
            try:
                if export_format == "markdown":
                    body = export_markdown().encode("utf-8")
                    content_type = "text/markdown; charset=utf-8"
                    file_name = f"todo-projects-{stamp}.md"
                elif export_format == "csv":
                    body = export_csv().encode("utf-8")
                    content_type = "text/csv; charset=utf-8"
                    file_name = f"todo-projects-{stamp}.csv"
                else:
                    body = json.dumps(export_projects_snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
                    content_type = "application/json; charset=utf-8"
                    file_name = f"todo-projects-{stamp}.json"
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                self.send_json(500, {"error": f"导出项目失败：{error}"})
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{file_name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith("/api/") and path not in {"/api/config"} and not valid_session(self):
            self.discard_body(self.request_length())
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        if path == "/api/config" and not valid_session(self):
            self.discard_body(self.request_length())
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        if path == "/api/review/counts":
            try:
                # 轻量计数：勾选/复习操作之后前端只要这两个数字，不必把全部项目摘要读出来。
                requested_today = optional_iso_date(query_params(self).get("today", [""])[0])
                server_today = datetime.date.today().isoformat()
                used_today = requested_today or server_today
                counts = storage_service.review_counts(used_today)
                totals = {"today": 0, "overdue": 0}
                for bucket in counts.values():
                    totals["today"] += bucket["today"]
                    totals["overdue"] += bucket["overdue"]
                self.send_json(200, {
                    "byProject": counts,
                    "totals": totals,
                    "serverToday": server_today,
                    "usedToday": used_today,
                })
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取复习计数失败：{error}"})
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
        if path.startswith("/api/review/"):
            try:
                params = query_params(self)
                raw_today = str(params.get("today", [""])[0] or "").strip()
                today = optional_iso_date(raw_today)
                if raw_today and not today:
                    raise ValueError("参数 today 必须是 YYYY-MM-DD")
                server_today = datetime.date.today().isoformat()
                # 注意：这是"复习页顶部统计"（due/overdue/weak/streak），与已取消的
                # 摘要清单（summary_storage）没有任何关系，别被名字骗了。
                if path == "/api/review/summary":
                    self.send_json(200, review_storage.summary(today or server_today))
                    return
                if path == "/api/review/queue":
                    limit = int_param(params, "limit", required=False, default=0)
                    new_per_day = int_param(params, "newPerDay", required=False, default=-1)
                    # 只为读 limit/newPerDay：以前这里跑一遍完整 summary()（全量 points 扫描 +
                    # streak + 两次 recent_attempts），而前端同时还会请求 /api/review/summary，
                    # 等于把同一套开销跑两遍。_settings() 只读设置。
                    settings = review_storage._settings()
                    queue = review_storage.build_queue(
                        today or server_today,
                        limit or settings["limit"],
                        code=(params.get("code", [""])[0] or "").strip(),
                        module=(params.get("module", [""])[0] or "").strip(),
                        level=(params.get("level", [""])[0] or "").strip(),
                        project_id=(params.get("projectId", [""])[0] or "").strip(),
                        task_id=(params.get("taskId", [""])[0] or "").strip(),
                        question_type=(params.get("type", [""])[0] or "").strip(),
                        new_per_day=settings["newPerDay"] if new_per_day < 0 else new_per_day,
                    )
                    self.send_json(200, queue)
                    return
                if path == "/api/review/points":
                    limit = int_param(params, "limit", required=False, default=200)
                    offset = int_param(params, "offset", required=False, default=0)
                    self.send_json(200, review_storage.list_points(
                        module=(params.get("module", [""])[0] or "").strip(),
                        level=(params.get("level", [""])[0] or "").strip(),
                        query=(params.get("query", [""])[0] or "").strip(),
                        limit=limit, offset=offset))
                    return
                if path == "/api/review/history":
                    code = required_param(params, "code")
                    limit = int_param(params, "limit", required=False, default=20)
                    self.send_json(200, review_storage.history(code, limit=limit))
                    return
            except ValueError as error:
                message = str(error)
                self.send_json(404 if "不存在" in message else 400, {"error": message})
                return
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"复习接口失败：{error}"})
                return
            self.send_json(404, {"error": "接口不存在"})
            return
        if path == "/api/reviews":
            # 跨项目复习队列：服务端直接算，前端不用再把每个项目的整棵树拉下来（第六批 item 3）
            try:
                params = query_params(self)
                today = optional_iso_date(params.get("today", [""])[0])
                limit = int_param(params, "limit", required=False, default=storage_service.MAX_REVIEW_QUEUE)
                self.send_json(200, list_review_queue(today or None, limit))
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                if isinstance(error, ValueError):
                    self.send_json(400, {"error": str(error)})
                else:
                    self.send_json(500, {"error": f"读取复习队列失败：{error}"})
            return
        if path == "/api/search":
            try:
                params = query_params(self)
                query = (params.get("q", [""])[0] or "").strip()
                if len(query) > 200:
                    raise ValueError("搜索关键词过长")
                limit = int_param(params, "limit", required=False, default=100)
                self.send_json(200, search_everything(query, limit))
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                if isinstance(error, ValueError):
                    self.send_json(400, {"error": str(error)})
                else:
                    self.send_json(500, {"error": f"搜索失败：{error}"})
            return
        if path == "/api/workbench":
            try:
                params = query_params(self)
                today = optional_iso_date(params.get("today", [""])[0])
                # since：客户端上一次拿到的 version。只做等值比较，超过长度上限的直接当没传
                # （提醒功能靠它跳过"数据没变"的整次重算，页面正常打开时不传）。
                since = str(params.get("since", [""])[0] or "").strip()[:MAX_SINCE_CHARS]
                self.send_json(200, workbench(today or None, since or None))
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                self.send_json(500, {"error": f"读取今日工作台失败：{error}"})
            return
        if path == "/api/recent":
            try:
                self.send_json(200, recent_overview())
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取最近记录失败：{error}"})
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
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
                self.send_json(500, {"error": f"读取 SQLite 信息失败：{error}"})
            return
        if path == "/api/backups":
            try:
                self.send_json(200, {"backups": list_database_backups()})
            except (OSError, RuntimeError) as error:
                self.send_json(500, {"error": f"读取备份列表失败：{error}"})
            return
        if path == "/api/node/delete-impact":
            try:
                params = query_params(self)
                impact = describe_node_delete(required_param(params, "projectId"), required_param(params, "nodeId"))
                self.send_json(200, {"impact": impact})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取删除影响面失败：{error}"})
            return
        if path == "/api/templates":
            try:
                self.send_json(200, {"templates": list_templates()})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取模板失败：{error}"})
            return
        if path == "/api/settings":
            try:
                self.send_json(200, {"settings": read_app_settings()})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取设置失败：{error}"})
            return
        if path == "/api/trash":
            try:
                self.send_json(200, {"items": list_trash_items()})
            except (OSError, sqlite3.Error, RuntimeError) as error:
                self.send_json(500, {"error": f"读取回收站失败：{error}"})
            return
        if path == "/api/memos":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("q", [""])[0]
            try:
                params = query_params(self)
                limit = int_param(params, "limit", required=False, default=memo_storage.MAX_MEMO_LIST)
                offset = int_param(params, "offset", required=False, default=0)
                memos = (memo_storage.search_memo_summaries(query, limit, offset) if query.strip()
                         else memo_storage.list_memo_summaries(limit, offset))
                self.send_json(200, {"memos": memos, "total": memo_storage.count_memos(query),
                                     "databaseBytes": memo_storage.database_size()})
            except ValueError as error:
                # limit/offset 非法 → 400；漏了这一步就会变成"空回复"（本仓库明令禁止）
                self.send_json(400, {"error": str(error)})
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
        length = self.request_length()
        if path not in {"/api/evaluate", "/api/question", "/api/project", "/api/import", "/api/backup",
                        "/api/node/patch",
                        "/api/node/reorder", "/api/node/duplicate", "/api/project/duplicate",
                        "/api/import/preview", "/api/project/from-template",
                        "/api/settings",
                        "/api/inbox/add", "/api/inbox/move", "/api/batch",
                        "/api/memo",
                        "/api/trash",
                        "/api/project/plan",
                        "/api/review/reveal", "/api/review/answer", "/api/review/session",
                        "/api/review/generate", "/api/review/ai-grade"}:
            self.discard_body(length)
            self.send_json(404, {"error": "接口不存在"})
            return
        if not valid_session(self):
            self.discard_body(length)
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        if not allowed_origin(self.headers.get("Origin")):
            self.discard_body(length)
            self.send_json(403, {"error": "不允许的请求来源"})
            return
        if path == "/api/memo":
            request_limit = MAX_MEMO_REQUEST_BYTES
        elif path in {"/api/project", "/api/import", "/api/import/preview"}:
            # 预览与真正导入必须同档：预览过去落在 5MiB 的 AI 限额分支，
            # 带 review 附件的大快照会 413，前端拿不到预览就禁用确认按钮，整条导入路径不可用。
            request_limit = MAX_STATE_REQUEST_BYTES
        else:
            request_limit = MAX_AI_REQUEST_BYTES
        if length <= 0 or length > request_limit:
            self.discard_body(length)
            self.send_json(413, {"error": "请求内容为空或过大"})
            return
        try:
            raw_body = self.read_body(length)
            if raw_body is None:
                return
            if len(raw_body) != length:
                raise ValueError("请求体不完整，请重试")
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("请求必须是 JSON 对象")
            if path == "/api/backup":
                action = str(payload.get("action", ""))
                if action == "delete":
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
            elif path == "/api/review/reveal":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("type") or "").strip()
                if not code or kind not in review_content.QUESTION_TYPES:
                    raise ValueError("知识点或题型不正确")
                data = review_storage.reveal(code, kind)
                self.send_json(200, data)
            elif path == "/api/review/answer":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("type") or "").strip()
                today = optional_iso_date(str(payload.get("today") or ""))
                if not today:
                    raise ValueError("today 必须是 YYYY-MM-DD")
                try:
                    grade = int(payload.get("grade") or 0)
                except (TypeError, ValueError):
                    raise ValueError("自评档位必须是 1~5") from None
                schedule = review_storage.apply_grade(
                    code, kind, grade, today=today,
                    answer=str(payload.get("answer") or ""),
                    duration_ms=int(payload.get("durationMs") or 0),
                    session_id=str(payload.get("sessionId") or ""),
                    task_id=str(payload.get("taskId") or ""),
                    project_id=str(payload.get("projectId") or ""))
                self.send_json(200, {"ok": True, "schedule": schedule})
            elif path == "/api/review/session":
                action = str(payload.get("action") or "")
                if action == "start":
                    session_id = review_storage.start_session(int(payload.get("planned") or 0))
                    self.send_json(200, {"ok": True, "sessionId": session_id})
                elif action == "finish":
                    raw_counts = payload.get("gradeCounts") or {}
                    if not isinstance(raw_counts, dict):
                        raise ValueError("gradeCounts 必须是对象")
                    try:
                        grade_counts = {int(k): int(v) for k, v in raw_counts.items()}
                    except (TypeError, ValueError):
                        raise ValueError("gradeCounts 必须是 1~5 档位的次数映射") from None
                    updated = review_storage.finish_session(
                        str(payload.get("sessionId") or ""),
                        answered=int(payload.get("answered") or 0),
                        grade_counts=grade_counts,
                        duration_ms=int(payload.get("durationMs") or 0))
                    if not updated:
                        raise ValueError("会话不存在")
                    self.send_json(200, {"ok": True})
                else:
                    raise ValueError("不支持的会话操作")
            elif path == "/api/review/generate":
                task_id = str(payload.get("taskId") or "").strip()
                if not task_id:
                    raise ValueError("缺少 taskId")
                # 纯元任务（1104/1504）不挂知识点：points_for_task 恒为空会让"len(created) < wanted"
                # 的闸门恒开、remedial 分支更是显式绕过，于是 AI 补充会凭空生成复习项。
                # 绑定约束是元任务不生成复习项，所以在取到 task_id 后立刻早退，remedial 也不例外。
                if task_id in review_storage.META_TASK_IDS:
                    self.send_json(200, {"ok": True, "inserted": 0, "unchanged": 0,
                                         "created": [], "usedAi": False})
                    return
                try:
                    wanted = int(payload.get("count") or 3)
                except (TypeError, ValueError):
                    raise ValueError("count 必须是数字") from None
                # 验收失败时带 remedial=true + gap：针对失败点生成补漏题，并把该任务关联的知识点标弱。
                # 补漏题不受"已有预规划点就不再补"的约束——否则已挂过知识点的任务永远补不了漏。
                remedial = bool(payload.get("remedial"))
                gap = str(payload.get("gap") or "").strip()
                points = review_storage.points_for_task(task_id)
                created = [{"code": point["code"], "title": point["title"]} for point in points[:5]]
                inserted = unchanged = 0
                used_ai = False
                generated = []
                if (remedial or len(created) < wanted) and ai_service.is_configured():
                    generated = ai_service.generate_review_points(
                        task_id=task_id, project_id=str(payload.get("projectId") or ""),
                        task_text=str(payload.get("taskText") or ""),
                        count=wanted, remedial=remedial, gap=gap)
                    if generated:
                        imported = review_storage.import_content(generated, origin="ai")
                        inserted = int(imported.get("inserted") or 0)
                        unchanged = int(imported.get("unchanged") or 0)
                        created.extend({"code": point["code"], "title": point["title"],
                                        "origin": "ai"} for point in generated)
                        used_ai = True
                if remedial:
                    # 只查一次 points_for_task：导入前那一批 + 本次真的生成/导入的补漏题，
                    # 就是"该任务的全部相关知识点"。以前为了标弱在导入之后又查了一遍库：
                    # 白白多一次查询，而且两次读取之间夹着写入，标弱集合和展示集合容易走偏。
                    review_storage.mark_weak([point["code"] for point in points]
                                             + [point["code"] for point in generated])
                self.send_json(200, {"ok": True, "inserted": inserted, "unchanged": unchanged,
                                     "created": created[:5], "usedAi": used_ai})
            elif path == "/api/review/ai-grade":
                code = str(payload.get("code") or "").strip()
                kind = str(payload.get("type") or "").strip()
                if not code or kind not in review_content.QUESTION_TYPES:
                    raise ValueError("知识点或题型不正确")
                if not ai_service.is_configured():
                    self.send_json(503, {"error": "未配置 AI，判分不可用（复习本身不受影响）"})
                    return
                verdict = ai_service.grade_review_answer(
                    code=code, question_type=kind, answer=str(payload.get("answer") or ""),
                    reference=review_storage.reveal(code, kind))
                self.send_json(200, {"ok": True, "verdict": verdict})
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
                revision, summary, spawned = write_project_with_occurrences(project, expected_revision)
                self.send_json(200, {"ok": True, "revision": revision, "summary": summary,
                                     "spawned": spawned})
            elif path == "/api/import/preview":
                projects = payload.get("projects")
                if not isinstance(projects, list):
                    raise ValueError("导入项目格式不正确")
                mode = str(payload.get("mode") or "replace")
                keep_ai = payload.get("keepAiHistory")
                preview = preview_import(projects, mode, keep_ai_history=keep_ai is not False)
                self.send_json(200, {"ok": True, "preview": preview})
            elif path == "/api/import":
                projects = payload.get("projects")
                if not isinstance(projects, list):
                    raise ValueError("导入项目格式不正确")
                mode = str(payload.get("mode") or "replace")
                keep_ai = payload.get("keepAiHistory")
                # 导入前一律留一份完整快照，任何模式都能整体回退
                import_backup_name = create_full_backup("before-import")
                if mode == "replace":
                    storage_service.replace_projects(projects, pre_backup=False)
                    result = {"mode": mode, "projects": read_project_summaries()}
                else:
                    result = import_projects(projects, mode, keep_ai_history=keep_ai is not False)
                # 规格 §10.7：JSON 导出会附带 5 张复习表的 `review` 快照，导入侧必须一起消费，
                # 否则"导出 → 导入"的跨机迁移会静默丢复习进度与作答历史。旧快照没有这个键
                # （payload.get 返回 None）→ import_review_snapshot 原样跳过，向后兼容。
                review_import = import_review_snapshot(payload.get("review"))
                self.send_json(200, {"ok": True, "preview": result.get("preview"),
                                     "projects": result["projects"], "mode": result["mode"],
                                     "backup": import_backup_name, "review": review_import})
            elif path == "/api/node/patch":
                project_id = payload.get("projectId")
                if not project_id:
                    raise ValueError("缺少 projectId")
                expected = payload.get("expectedRevision")
                if expected is not None:
                    try:
                        expected = int(expected)
                    except (TypeError, ValueError):
                        raise ValueError("expectedRevision 格式不正确") from None
                result = patch_project_nodes(str(project_id), expected, payload.get("ops"))
                self.send_json(200, {"ok": True, **result})
            elif path == "/api/node/reorder":
                moved = reorder_node(str(payload.get("projectId") or ""), str(payload.get("nodeId") or ""),
                                     payload.get("parentId"),
                                     payload.get("position"))
                self.send_json(200, {"ok": True, "move": moved, "projects": read_project_summaries()})
            elif path == "/api/node/duplicate":
                created = duplicate_node(
                    str(payload.get("projectId") or ""), str(payload.get("nodeId") or ""),
                    include_children=payload.get("includeChildren") is not False,
                    keep_completion=bool(payload.get("keepCompletion")),
                    keep_assessment=bool(payload.get("keepAssessment")),
                    keep_review=bool(payload.get("keepReview")),
                )
                project = read_project(created["projectId"])
                self.send_json(200, {"ok": True, "node": created["node"],
                                     "project": project[0] if project else None,
                                     "revision": project[1] if project else 0})
            elif path == "/api/project/duplicate":
                created = duplicate_project(
                    str(payload.get("projectId") or ""), name=payload.get("name"),
                    keep_completion=payload.get("keepCompletion") is not False,
                    keep_assessment=payload.get("keepAssessment") is not False,
                    keep_review=payload.get("keepReview") is not False,
                )
                self.send_json(200, {"ok": True, "project": created["project"],
                                     "projects": read_project_summaries()})
            elif path == "/api/project/from-template":
                created = create_project_from_template(str(payload.get("templateId") or ""),
                                                       payload.get("name"))
                self.send_json(200, {"ok": True, "project": created["project"],
                                     "projects": read_project_summaries()})
            elif path == "/api/settings":
                patch = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
                self.send_json(200, {"ok": True, "settings": update_app_settings(
                    {key: value for key, value in patch.items() if key != "ok"})})
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
                    # 存在性只看这一条：以前是 list_trash_items() 全量列一遍再线性查
                    if not trash_id or trash_id not in trash_item_ids([trash_id]):
                        self.send_json(404, {"error": "回收站条目不存在"})
                        return
                    result = restore_trash_item(trash_id)
                    self.send_json(200, {"ok": True, "item": result, "items": list_trash_items(), "projects": read_project_summaries()})
                elif action == "delete":
                    trash_id = str(payload.get("id") or "")
                    if not trash_id or trash_id not in trash_item_ids([trash_id]):
                        self.send_json(404, {"error": "回收站条目不存在"})
                        return
                    delete_trash_item(trash_id)
                    self.send_json(200, {"ok": True, "items": list_trash_items()})
                elif action in {"restore-many", "delete-many"}:
                    ids = payload.get("ids")
                    if not isinstance(ids, list) or not ids:
                        raise ValueError("请先选择要处理的回收站条目")
                    known = trash_item_ids([str(item) for item in ids])
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
        if path not in {"/api/project", "/api/memo"}:
            self.discard_body(self.request_length())
            self.send_json(404, {"error": "接口不存在"})
            return
        # 会话失效(401) 与 来源不允许(403) 是两回事，不能都报"会话已失效"。
        if not valid_session(self):
            self.discard_body(self.request_length())
            self.send_json(401, {"error": "本地页面会话已失效，请重新启动"})
            return
        if not allowed_origin(self.headers.get("Origin")):
            self.discard_body(self.request_length())
            self.send_json(403, {"error": "不允许的请求来源"})
            return
        # 所有分支都在 try 里：参数缺失/非法 → 400，资源不存在 → 404，版本冲突 → 409，
        # 绝不把异常抛到 HTTP 层（那会变成"空回复"）。
        params = query_params(self)
        try:
            if path == "/api/memo":
                memo_id = required_param(params, "id")
                expected_revision = int_param(params, "revision")
                if not memo_storage.read_memo(memo_id):
                    self.send_json(404, {"error": "备忘录不存在"})
                    return
                memo_storage.delete_memo(memo_id, expected_revision)
                self.send_json(200, {"ok": True, "memos": memo_storage.list_memo_summaries(),
                                     "total": memo_storage.count_memos()})
                return
            project_id = required_param(params, "id")
            expected_revision = int_param(params, "revision")
            if read_project(project_id) is None:
                self.send_json(404, {"error": "项目不存在"})
                return
            removed = delete_project(project_id, expected_revision)
            self.send_json(200, {"ok": True, "trashId": (removed or {}).get("trashId", ""),
                                 "projects": read_project_summaries()})
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
    review_count = review_storage.ensure_review_content_ready()
    if review_count is None:
        print("复习知识点未就绪：内置内容文件缺失或损坏（见上方告警），服务继续启动",
              file=sys.stderr)
    elif review_count:
        print(f"复习知识点就绪：新增/更新 {review_count} 个")
    else:
        print("复习知识点就绪：已是最新")
    storage_service.purge_trash_items()
    memo_storage.initialize()
    if not memo_storage.check_integrity():
        raise RuntimeError("备忘录 SQLite 完整性检查失败")
    SESSION_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = partial(TodoHandler, directory=str(APP_DIR))
    # 先 bind 成功再写 token 文件。反过来的话，两个实例几乎同时启动时，抢不到端口的那一个
    # 会在退出前把活实例的 token 覆盖成死进程的 token，启动脚本读到它 → 浏览器全量 401，
    # 而且没有任何自愈路径（只能手工删 token 文件重开）。
    server = ThreadingHTTPServer((HOST, PORT), handler)
    SESSION_TOKEN_FILE.write_text(SESSION_TOKEN, encoding="utf-8")
    SESSION_TOKEN_FILE.chmod(0o600)
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
        raise SystemExit(1) from error
