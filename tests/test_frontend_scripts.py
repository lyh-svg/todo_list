"""前端断言脚本的统一入口。

这些脚本是纯 Node 脚本（零依赖，只用 vm/fs 从 js/app.js 抽取真实函数来跑，
或像 dom-smoke.js 那样用最小 DOM 桩真实加载并点击页面）。它们以前散落在 /tmp，
现在放进仓库，由这个 unittest 一起跑；没装 node 时自动跳过而不是失败。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

# 顺序只是报告顺序；每个脚本自己负责读取 js/app.js、index.html、css/style.css。
SCRIPTS = [
    "verify-study-tools.js",
    "verify-round1.js",
    "verify-round2.js",
    "verify-round4.js",
    "verify-assessment-sync.js",
    "verify-r2.js",
    "verify-r3.js",
    "verify-r45.js",
    "verify-r6.js",
    "verify-r7.js",
    "verify-r8.js",
    "verify-r9.js",
    "verify-r10.js",
    "verify-reminders.js",
    "dom-smoke.js",
]


class FrontendScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.node = shutil.which("node")

    def test_frontend_assets_exist(self) -> None:
        for relative in ("js/app.js", "js/api-client.js", "js/study-tools.js",
                         "index.html", "css/style.css"):
            self.assertTrue((APP_DIR / relative).is_file(), f"缺少前端文件 {relative}")

    def test_node_scripts(self) -> None:
        if not self.node:
            self.skipTest("未安装 node，跳过前端断言脚本")
        for name in SCRIPTS:
            script = FRONTEND_DIR / name
            self.assertTrue(script.is_file(), f"缺少前端脚本 {name}")
            with self.subTest(script=name):
                result = subprocess.run(
                    [self.node, str(script)],
                    cwd=str(APP_DIR), capture_output=True, text=True, timeout=180,
                )
                self.assertEqual(
                    result.returncode, 0,
                    f"{name} 失败：\n{result.stdout[-4000:]}\n{result.stderr[-2000:]}",
                )

    def test_scripts_reference_the_repo_not_a_hardcoded_path(self) -> None:
        """脚本必须用 __dirname 计算仓库根目录，否则换台机器/换目录就跑不了。"""
        for name in SCRIPTS:
            text = (FRONTEND_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn("/home/lyh", text, f"{name} 里还有写死的绝对路径")
            self.assertIn("__dirname", text, f"{name} 应该用 __dirname 定位仓库根目录")


if __name__ == "__main__":
    unittest.main(verbosity=2)
