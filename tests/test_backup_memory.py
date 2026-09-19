"""P10 回归：备份校验与恢复暂存必须流式读，不能把整个库读进内存。

旧实现用 archive.read(name) 把每个成员一次性读成 bytes 再算 sha256 / 写暂存文件：
一个 24.2 MB 的备忘录库实测让 describe_backup 的 Python 分配峰值到 66.6 MB
（110 MB 上限的 state 库会更高）。改法：archive.open(name) 流式读 + hashlib 增量更新。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import tracemalloc
import unittest
import zipfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-backup-memory-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))
os.environ.setdefault("TODO_SUMMARY_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "summary.sqlite3"))

import backup_service  # noqa: E402
import memo_storage  # noqa: E402
import storage  # noqa: E402
import summary_storage  # noqa: E402

CONTENT_BYTES = 8 * 1024 * 1024          # 8 MB 的备忘录正文 → ZIP 成员约 8 MB
PEAK_BUDGET_BYTES = 4 * 1024 * 1024      # 流式读的话峰值 ≪ 8 MB（分块 1 MB）


class BackupMemoryTests(unittest.TestCase):
    def tearDown(self) -> None:
        # 这套测试共用 tests/__init__.py 钉住的临时库：跑完清干净，别把 8 MB 的备忘录和
        # 若干大备份留给后面的模块（否则它们的"memo 计数"之类断言会被带偏）。
        for database in (storage.DATABASE_FILE, memo_storage.MEMO_DATABASE_FILE,
                         summary_storage.SUMMARY_DATABASE_FILE):
            for suffix in ("", "-wal", "-shm"):
                Path(f"{database}{suffix}").unlink(missing_ok=True)
        shutil.rmtree(backup_service.BACKUP_DIR, ignore_errors=True)

    def setUp(self) -> None:
        for database in (storage.DATABASE_FILE, memo_storage.MEMO_DATABASE_FILE,
                         summary_storage.SUMMARY_DATABASE_FILE):
            for suffix in ("", "-wal", "-shm"):
                Path(f"{database}{suffix}").unlink(missing_ok=True)
        storage.ensure_schema()
        memo_storage.initialize()
        summary_storage.initialize()
        storage.write_project({
            "id": "p1", "name": "项目", "description": "", "createdAt": "2026-09-19",
            "assessmentEnabled": False, "tree": [{
                "id": "p1-w", "type": "week", "text": "第1周", "completed": False,
                "expanded": False, "createdAt": "2026-09-19", "children": []}]}, None)
        memo_storage.write_memo({"title": "大备忘录", "content": "x" * CONTENT_BYTES})

    def backup_name(self) -> str:
        name = backup_service.create_full_backup("manual")
        return name["name"] if isinstance(name, dict) else str(name)

    def peak_during(self, func):
        tracemalloc.start()
        try:
            result = func()
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        return result, peak

    def zip_member_sizes(self, name: str) -> dict[str, int]:
        with zipfile.ZipFile(Path(backup_service.BACKUP_DIR) / name) as archive:
            return {info.filename: info.file_size for info in archive.infolist()}

    def test_describe_backup_streams_checksum(self) -> None:
        name = self.backup_name()
        biggest = max(self.zip_member_sizes(name).values())
        self.assertGreater(biggest, 6 * 1024 * 1024, "夹具应该有一个 6 MB 以上的库成员")

        preview, peak = self.peak_during(lambda: backup_service.describe_backup(name))
        self.assertTrue(preview["checksumOk"], "校验结果必须仍然正确")
        self.assertEqual(preview["kind"], "full")
        sizes = self.zip_member_sizes(name)
        for entry in preview["files"]:
            self.assertTrue(entry["ok"], entry)
            self.assertEqual(entry["bytes"], sizes[entry["name"]], entry["name"])
        self.assertLess(peak, PEAK_BUDGET_BYTES,
                        f"describe_backup 峰值 {peak / 1e6:.1f} MB，超过 {PEAK_BUDGET_BYTES / 1e6:.0f} MB —— 又整块读进内存了")

    def test_tampered_member_is_still_detected(self) -> None:
        """流式校验不能变成"永远通过"：改一个字节必须仍然报不匹配。"""
        name = self.backup_name()
        path = Path(backup_service.BACKUP_DIR) / name
        with zipfile.ZipFile(path) as archive:
            entries = {info.filename: archive.read(info.filename) for info in archive.infolist()}
        entries["memo.sqlite3"] = entries["memo.sqlite3"] + b"tampered"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_name, data in entries.items():
                archive.writestr(file_name, data)
        preview = backup_service.describe_backup(name)
        self.assertFalse(preview["checksumOk"])
        broken = [entry for entry in preview["files"] if not entry["ok"]]
        self.assertEqual([entry["name"] for entry in broken], ["memo.sqlite3"])
        self.assertNotEqual(broken[0]["sha256"], broken[0]["expectedSha256"])

    def test_restore_stages_files_without_loading_them(self) -> None:
        name = self.backup_name()
        before = memo_storage.list_memo_summaries()
        # setUp 里 initialize() 会补一条"未命名备忘录"，再加上夹具那条
        self.assertEqual(len(before), 2)
        big = next(entry for entry in before if entry["title"] == "大备忘录")
        self.assertEqual(big["contentLength"], CONTENT_BYTES)

        result, peak = self.peak_during(lambda: backup_service.restore_full_backup(name))
        self.assertEqual(result["name"], name)
        self.assertTrue(result["emergency"], "恢复前应自动留一份应急备份")
        self.assertLess(peak, PEAK_BUDGET_BYTES,
                        f"恢复暂存峰值 {peak / 1e6:.1f} MB —— 又把整库读进内存了")
        memos = memo_storage.list_memo_summaries()
        self.assertEqual(len(memos), 2)
        restored = next(entry for entry in memos if entry["title"] == "大备忘录")
        self.assertEqual(restored["contentLength"], CONTENT_BYTES, "恢复后内容长度不变")
        self.assertEqual(len(storage.read_project_summaries()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
