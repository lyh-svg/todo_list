"""统一备份服务（第三阶段 ⑧⑨）。

原来的备份只覆盖 todo.sqlite3，memo 走独立下载，摘要库完全没有备份路径。
这里把三个库打成一个带 manifest 与逐文件 sha256 的 ZIP，并提供：

  - create_full_backup(prefix)  原子生成一份完整备份
  - describe_backup(name)       恢复预览：内容统计 + 校验和是否通过
  - restore_full_backup(name)   校验 → 应急备份 → 原子替换 → 完整性检查 → 失败回滚
  - prune_backups()             保留策略：7 天全留 / 30 天每日 / 90 天每周
  - create_daily_snapshot()     启动时的每日快照

只用标准库（zipfile / hashlib / sqlite3）。
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
import zipfile
from contextlib import ExitStack, closing
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import memo_storage
import storage as storage_service
import summary_storage

BACKUP_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_FILES: dict[str, Path] = {
    "todo.sqlite3": Path(storage_service.DATABASE_FILE),
    "memo.sqlite3": Path(memo_storage.MEMO_DATABASE_FILE),
    "summary.sqlite3": Path(summary_storage.SUMMARY_DATABASE_FILE),
}
BACKUP_DIR = Path(storage_service.BACKUP_DIR)
KEEP_ALL_DAYS = 7
KEEP_DAILY_DAYS = 30
KEEP_WEEKLY_DAYS = 90


def _now() -> datetime:
    return datetime.now()


def _checkpoint_all() -> None:
    storage_service.checkpoint_database()
    memo_storage.checkpoint()
    summary_storage.checkpoint()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_database(source: Path, target: Path) -> None:
    """用 SQLite Online Backup API 复制（比直接 copy 文件安全）。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    # `with sqlite3.connect(...)` 不会关闭连接（只提交事务），这里显式关闭。
    with closing(sqlite3.connect(source, timeout=10)) as source_connection:
        with closing(sqlite3.connect(target)) as destination:
            source_connection.backup(destination)
    try:
        target.chmod(0o600)
    except OSError:
        pass


def _integrity_ok(path: Path) -> bool:
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
        return bool(result and result[0] == "ok")
    except sqlite3.Error:
        return False


def database_counts() -> dict[str, int]:
    counts = {"projects": 0, "nodes": 0, "memos": 0, "summaries": 0}
    try:
        with storage_service.open_state_database() as connection:
            counts["projects"] = int(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
            counts["nodes"] = int(connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
    except (OSError, sqlite3.Error, RuntimeError):
        pass
    try:
        with memo_storage.open_memo_database() as connection:
            counts["memos"] = int(connection.execute("SELECT COUNT(*) FROM memos").fetchone()[0])
    except (OSError, sqlite3.Error, RuntimeError):
        pass
    try:
        with summary_storage.open_summary_database() as connection:
            counts["summaries"] = int(connection.execute("SELECT COUNT(*) FROM summaries").fetchone()[0])
    except (OSError, sqlite3.Error, RuntimeError):
        pass
    return counts


def create_full_backup(prefix: str = "manual", *, include_databases: dict[str, Path] | None = None,
                       counts: dict[str, int] | None = None) -> str:
    """生成一份完整备份，返回文件名。先写临时文件再 os.replace，保证不会留下半个 ZIP。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    sources = include_databases or DATABASE_FILES
    stamp = _now().strftime("%Y%m%dT%H%M%S%f")
    target = BACKUP_DIR / f"{prefix}-{stamp}.zip"
    temporary = BACKUP_DIR / f".{target.name}.tmp"
    _checkpoint_all()
    manifest: dict[str, Any] = {
        "format": BACKUP_FORMAT_VERSION,
        "createdAt": _now().isoformat(timespec="seconds"),
        "appSchemaVersion": storage_service.SCHEMA_VERSION,
        "prefix": prefix,
        "counts": counts if counts is not None else database_counts(),
        "files": {},
    }
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, source in sources.items():
                if not Path(source).exists():
                    continue
                staged = BACKUP_DIR / f".{target.name}.{name}"
                try:
                    _snapshot_database(Path(source), staged)
                    manifest["files"][name] = {
                        "sha256": sha256_of(staged),
                        "bytes": staged.stat().st_size,
                    }
                    archive.write(staged, arcname=name)
                finally:
                    staged.unlink(missing_ok=True)
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return target.name


def _valid_name(name: str, suffix: str = ".zip") -> str:
    text = str(name or "")
    # 以点开头的是恢复/回滚过程用的临时文件（.restore-* / .rollback-*），
    # 不能当成用户备份：它们可能是被中断的、内容过期的半个库。
    if Path(text).name != text or text.startswith(".") or not text.endswith(suffix):
        raise ValueError("备份文件名不正确")
    return text


def list_backups() -> list[dict[str, Any]]:
    """列出全部备份；zip 是完整备份，旧的 .sqlite3 仍可见但标记为 legacy。"""
    entries: list[dict[str, Any]] = []
    for pattern, kind in (("*.zip", "full"), ("*.sqlite3", "legacy")):
        for path in BACKUP_DIR.glob(pattern):
            if path.name.startswith("."):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append({
                "name": path.name,
                "kind": kind,
                "bytes": stat.st_size,
                "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "valid": stat.st_size > 0,
            })
    entries.sort(key=lambda item: item["modifiedAt"], reverse=True)
    return entries


def describe_backup(name: str) -> dict[str, Any]:
    """恢复预览：内容统计 + 逐文件校验和核对。"""
    if str(name or "").endswith(".sqlite3"):
        path = BACKUP_DIR / _valid_name(name, ".sqlite3")
        if not path.is_file():
            raise ValueError("备份不存在")
        return {
            "name": path.name, "kind": "legacy", "createdAt": "",
            "counts": {}, "files": [{"name": path.name, "ok": _integrity_ok(path), "bytes": path.stat().st_size}],
            "checksumOk": _integrity_ok(path), "note": "旧格式备份只包含任务数据库（todo.sqlite3）",
        }
    path = BACKUP_DIR / _valid_name(name)
    if not path.is_file():
        raise ValueError("备份不存在")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if MANIFEST_NAME not in names:
            raise ValueError("备份里没有 manifest.json，可能不是本程序生成的")
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        if int(manifest.get("format", 0)) > BACKUP_FORMAT_VERSION:
            raise ValueError(
                f"备份格式版本 {manifest.get('format')} 高于本程序支持的 {BACKUP_FORMAT_VERSION}，请升级程序"
            )
        files = []
        checksum_ok = True
        for file_name, meta in (manifest.get("files") or {}).items():
            if file_name not in names:
                files.append({"name": file_name, "ok": False, "bytes": 0, "reason": "ZIP 内缺少该文件"})
                checksum_ok = False
                continue
            data = archive.read(file_name)
            actual = hashlib.sha256(data).hexdigest()
            ok = actual == meta.get("sha256") and len(data) == int(meta.get("bytes", -1))
            checksum_ok = checksum_ok and ok
            files.append({"name": file_name, "ok": ok, "bytes": len(data),
                          "sha256": actual, "expectedSha256": meta.get("sha256")})
    return {
        "name": path.name,
        "kind": "full",
        "createdAt": manifest.get("createdAt", ""),
        "appSchemaVersion": manifest.get("appSchemaVersion"),
        "counts": manifest.get("counts") or {},
        "files": files,
        "checksumOk": checksum_ok,
    }


def _all_database_locks() -> ExitStack:
    """恢复会整文件替换三个库，必须同时挡住三边的并发写。

    只加 state 库的锁是不够的：恢复期间进来的 memo/summary 写会提交到被 os.replace 换掉的
    旧 inode 上，静默丢数据（.restore-*/.rollback-* 这些固定名临时文件也会互相覆盖）。
    """
    stack = ExitStack()
    for module in (storage_service, memo_storage, summary_storage):
        lock = (getattr(module, "_database_lock", None)
                or getattr(module, "_memo_lock", None)
                or getattr(module, "_summary_lock", None))
        if lock is not None:
            stack.enter_context(lock)
    return stack


def restore_full_backup(name: str, *, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """恢复完整备份：校验 → 应急备份 → 原子替换三个库 → 完整性检查，失败回滚。"""
    if str(name or "").endswith(".sqlite3"):
        storage_service.restore_database_backup(name)
        return {"name": str(name), "kind": "legacy", "restored": ["todo.sqlite3"]}

    path = BACKUP_DIR / _valid_name(name)
    if not path.is_file():
        raise ValueError("备份不存在")
    preview = describe_backup(name)
    if not preview["checksumOk"]:
        raise ValueError("备份校验和不匹配，已拒绝恢复（备份可能损坏）")

    with _all_database_locks():
        return _restore_full_backup_locked(path, progress=progress)


def _restore_full_backup_locked(path: Path, *, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    _checkpoint_all()
    emergency = create_full_backup("before-restore")
    # 临时文件名带唯一后缀：两个并发恢复不能互相覆盖对方的暂存文件。
    token = uuid.uuid4().hex[:12]
    staging: dict[str, Path] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            for file_name in DATABASE_FILES:
                if file_name in archive.namelist():
                    staged = BACKUP_DIR / f".restore-{token}-{file_name}"
                    staged.write_bytes(archive.read(file_name))
                    staged.chmod(0o600)
                    staging[file_name] = staged
                    if progress:
                        progress(f"已解开 {file_name}")
        if not staging:
            raise ValueError("备份里没有任何数据库文件")
        for file_name, staged in staging.items():
            destination = Path(DATABASE_FILES[file_name])
            for suffix in ("-wal", "-shm"):
                Path(f"{destination}{suffix}").unlink(missing_ok=True)
            os.replace(staged, destination)
            if progress:
                progress(f"已恢复 {file_name}")
        storage_service.ensure_schema()
        for file_name, destination in DATABASE_FILES.items():
            if Path(destination).exists() and not _integrity_ok(Path(destination)):
                raise RuntimeError(f"{file_name} 恢复后完整性检查失败")
    except Exception:
        if progress:
            progress("恢复失败，正在回滚到恢复前的应急备份…")
        _restore_from_backup_file(BACKUP_DIR / emergency, token=token)
        raise
    finally:
        for staged in staging.values():
            Path(staged).unlink(missing_ok=True)
    return {"name": path.name, "kind": "full", "restored": sorted(staging), "emergency": emergency}


def _restore_from_backup_file(backup_path: Path, *, token: str | None = None) -> None:
    """把应急备份（zip）里的库写回去，用于恢复失败时的回滚。"""
    suffix_token = token or uuid.uuid4().hex[:12]
    with zipfile.ZipFile(backup_path) as archive:
        for file_name in DATABASE_FILES:
            if file_name not in archive.namelist():
                continue
            destination = Path(DATABASE_FILES[file_name])
            staged = destination.parent / f".rollback-{suffix_token}-{file_name}"
            staged.write_bytes(archive.read(file_name))
            for suffix in ("-wal", "-shm"):
                Path(f"{destination}{suffix}").unlink(missing_ok=True)
            os.replace(staged, destination)


def prune_backups(now: datetime | None = None) -> dict[str, int]:
    """保留策略：≤7 天全留；8~30 天每天留最新一份；31~90 天每周留最新一份；更早删除。"""
    moment = now or _now()
    entries = []
    for path in BACKUP_DIR.glob("*.zip"):
        if path.name.startswith("."):
            continue
        try:
            entries.append((path.stat().st_mtime, path))
        except OSError:
            continue
    entries.sort(reverse=True)
    kept = 0
    removed = 0
    seen_days: set[str] = set()
    seen_weeks: set[str] = set()
    for mtime, path in entries:
        created = datetime.fromtimestamp(mtime)
        age_days = (moment - created).days
        if age_days <= KEEP_ALL_DAYS:
            kept += 1
            continue
        if age_days <= KEEP_DAILY_DAYS:
            key = created.strftime("%Y-%m-%d")
            if key in seen_days:
                path.unlink(missing_ok=True)
                removed += 1
            else:
                seen_days.add(key)
                kept += 1
            continue
        if age_days <= KEEP_WEEKLY_DAYS:
            iso = created.isocalendar()
            key = f"{iso[0]}-{iso[1]}"
            if key in seen_weeks:
                path.unlink(missing_ok=True)
                removed += 1
            else:
                seen_weeks.add(key)
                kept += 1
            continue
        path.unlink(missing_ok=True)
        removed += 1
    return {"kept": kept, "removed": removed}


def create_daily_snapshot() -> str | None:
    """每天最多一份自动快照；已有当天快照就跳过。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = _now().strftime("%Y%m%d")
    marker = BACKUP_DIR / f".daily-{today}"
    if marker.exists():
        return None
    name = create_full_backup("daily")
    try:
        marker.touch(mode=0o600, exist_ok=True)
    except OSError:
        pass
    prune_backups()
    return name


def rename_backup(old_name: str, new_name: str) -> str:
    """重命名备份（.zip 完整备份或旧的 .sqlite3），只改文件名不动内容。"""
    import re as _re
    old = _valid_name(old_name, ".zip") if str(old_name).endswith(".zip") else _valid_name(old_name, ".sqlite3")
    suffix = ".zip" if old.endswith(".zip") else ".sqlite3"
    text = str(new_name or "").strip()
    if not text.endswith(suffix):
        text += suffix
    if (Path(text).name != text or len(text) > 110 or text.startswith(".")
            or not _re.match(r"[\w.\- ()（）\u4e00-\u9fff]+$", text, _re.UNICODE)):
        raise ValueError("新名称只能包含字母、数字、中文、空格、括号、下划线、连字符和点")
    source = BACKUP_DIR / old
    target = BACKUP_DIR / text
    if not source.is_file():
        raise ValueError("备份不存在")
    if target.exists() and target != source:
        raise ValueError("该备份名称已经存在")
    if target != source:
        source.replace(target)
        target.chmod(0o600)
    return text


def delete_backup(name: str) -> None:
    text = str(name or "")
    _valid_name(text, ".zip") if text.endswith(".zip") else _valid_name(text, ".sqlite3")
    target = BACKUP_DIR / text
    if not target.is_file():
        raise ValueError("备份不存在")
    target.unlink()
