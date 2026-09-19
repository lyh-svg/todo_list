"""测试包入口：在任何测试模块之前把存储路径钉到临时目录。

事故记录（2026-09-17）：一次手工验证在**未设置** TODO_SQLITE_FILE 的情况下对着真实
`data/` 起过服务，把测试夹具（py.local.extra / “本地独有作答”）写进了用户的库。
真实数据已清理并逐行比对无损，但这类事故必须从机制上堵死：本文件在包导入时兜底，
保证 unittest 无论以何种模块顺序导入，都不可能绑定到真实数据。
"""
import os
import tempfile
from pathlib import Path

_GUARD_DIR = Path(tempfile.mkdtemp(prefix="todo-tests-guard-"))
os.environ.setdefault("TODO_SQLITE_FILE", str(_GUARD_DIR / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(_GUARD_DIR / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(_GUARD_DIR / "memo.sqlite3"))
