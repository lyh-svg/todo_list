"""测试包入口：在任何测试模块之前把存储路径钉到临时目录。

事故记录（2026-09-17）：一次手工验证在**未设置** TODO_SQLITE_FILE 的情况下对着真实
`data/` 起过服务，把测试夹具（py.local.extra / “本地独有作答”）写进了用户的库。
真实数据已清理并逐行比对无损，但这类事故必须从机制上堵死：本文件在包导入时兜底，
保证 unittest 无论以何种模块顺序导入，都不可能绑定到真实数据。

另外：模块级 `TemporaryDirectory` 不显式清理时，会在解释器退出时才被 GC，每个模块各留
一条 `ResourceWarning`（几十条噪声会盖住真告警），`_GUARD_DIR` 更是每次跑测试都在 /tmp
留下一个目录（实测攒到 2300 多个）。这里用 atexit 统一收尾。
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

_GUARD_DIR = Path(tempfile.mkdtemp(prefix="todo-tests-guard-"))
os.environ.setdefault("TODO_SQLITE_FILE", str(_GUARD_DIR / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(_GUARD_DIR / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(_GUARD_DIR / "memo.sqlite3"))


def _cleanup_test_tempdirs() -> None:
    """退出前显式清理测试用的临时目录。

    显式 `cleanup()` 会 detach 掉 `TemporaryDirectory` 的 finalizer，所以既删了目录，
    也不会再有"Implicitly cleaning up"的 ResourceWarning。atexit 阶段模块还在，能枚举到。
    """
    for name, module in list(sys.modules.items()):
        if not (name == "tests" or name.startswith("tests.")):
            continue
        try:
            values = list(vars(module).values())
        except TypeError:   # 少数模块的 __dict__ 不是普通映射
            continue
        for value in values:
            if isinstance(value, tempfile.TemporaryDirectory):
                value.cleanup()
    shutil.rmtree(_GUARD_DIR, ignore_errors=True)


atexit.register(_cleanup_test_tempdirs)
