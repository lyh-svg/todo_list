"""两个 SQLite 库（todo / memo）共用的连接基类与时间戳工具。

单独成模块，而不是让 memo_storage 去 import storage：两个库的生命周期互不相干
（memo_storage 的定位就是 standalone）。但"with 块必须真正关连接"这件事两边必须一致 ——
之前两个模块各抄了一份一模一样的连接类与 `_now()`，改一处忘另一处就会分叉。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime


class ManagedConnection(sqlite3.Connection):
    """with 块结束时真正关闭连接。

    sqlite3 的上下文管理器只负责提交/回滚，不关闭连接；不关会留下未释放的句柄
    （表现为 ResourceWarning）。这里统一在 __exit__ 里关闭。
    """

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc, tb))
        finally:
            self.close()


def now_iso() -> str:
    """记录时间戳的统一格式：秒级精度、本地时区的 ISO 串。"""
    return datetime.now().isoformat(timespec="seconds")
