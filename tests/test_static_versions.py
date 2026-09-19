"""入口 HTML 的资源版本号必须跟着文件走。

背景（2026-09-19 实际事故）：静态资源用 `Cache-Control: public, max-age=86400` 缓存，
缓存击穿靠 index.html 里手写的 `?v=37`；改了 css/js 忘了改这个数字，浏览器 24 小时都拿旧文件，
用户看到的是"改了但页面没变"。现在版本号由 `asset_version()` 按文件 mtime+大小实时生成，
这里锁住三件事：

1. 每个版本化资源在入口 HTML 里的 `?v=` 都等于当前文件的版本号；
2. 版本号只由数字组成（`?v=\\d+` 这条约定在 e2e / 前端脚本里也被依赖）；
3. 用 HTTP 真的发一次入口 HTML，确认发出去的就是替换过的版本。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import http.client
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from functools import partial
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-static-version-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import local_server  # noqa: E402


def tearDownModule() -> None:  # pragma: no cover - 资源清理
    _TEMP_DIR.cleanup()


class StaticVersionTests(unittest.TestCase):
    def test_entry_html_versions_track_asset_files(self) -> None:
        html = local_server.versioned_html((APP_DIR / "index.html").read_text(encoding="utf-8"))
        for path in sorted(local_server.VERSIONED_STATIC_PATHS):
            relative = path.lstrip("/")
            expected = f"{relative}?v={local_server.asset_version(relative)}"
            self.assertIn(expected, html, f"{relative} 的缓存版本号没跟着文件走")

    def test_stale_version_in_source_is_replaced(self) -> None:
        """源码里写死的旧版本号必须被替换掉（这正是本次事故的形态）。"""
        html = local_server.versioned_html('<link rel="stylesheet" href="css/style.css?v=1" />')
        self.assertNotIn('href="css/style.css?v=1"', html)
        self.assertRegex(html, r"css/style\.css\?v=\d+")

    def test_asset_version_is_digits_and_tracks_mtime_and_size(self) -> None:
        version = local_server.asset_version("css/style.css")
        self.assertRegex(version, r"^\d+$")
        stat = (APP_DIR / "css" / "style.css").stat()
        self.assertEqual(version, f"{int(stat.st_mtime)}{stat.st_size:07d}")
        self.assertEqual(local_server.asset_version("不存在/的文件.css"), "0")

    def test_served_html_carries_fresh_versions(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     partial(local_server.TodoHandler, directory=str(APP_DIR)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", "/")
            response = connection.getresponse()
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            css_version = local_server.asset_version("css/style.css")
            self.assertIn(f"css/style.css?v={css_version}", body)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
