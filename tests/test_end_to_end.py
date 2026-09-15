"""端到端验证入口：临时库 + 随机端口 + TODO_AI_MOCK 起真实服务跑 140 项检查。

脚本 tests/e2e-verify.sh 不触碰 data/ 下的真实数据库（全部路径走临时目录），
没装 bash/python3 时自动跳过。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
SCRIPT = Path(__file__).resolve().parent / "e2e-verify.sh"


class EndToEndTests(unittest.TestCase):
    def test_e2e_script_exists(self) -> None:
        self.assertTrue(SCRIPT.is_file(), "缺少 tests/e2e-verify.sh")
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("/home/lyh", text, "脚本里还有写死的绝对路径")
        self.assertIn("TODO_SQLITE_FILE=", text, "脚本必须在临时库里跑，不能碰 data/")

    def test_e2e_script_passes(self) -> None:
        if os.environ.get("TODO_SKIP_E2E"):
            self.skipTest("TODO_SKIP_E2E 已设置，跳过端到端脚本")
        if not shutil.which("bash"):
            self.skipTest("未安装 bash，跳过端到端脚本")
        if not sys.executable:
            self.skipTest("找不到 python3，跳过端到端脚本")
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=str(APP_DIR), capture_output=True, text=True, timeout=600,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"端到端脚本失败：\n{output[-5000:]}")
        self.assertIn("失败 0 项", output, f"端到端脚本有失败项：\n{output[-5000:]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
