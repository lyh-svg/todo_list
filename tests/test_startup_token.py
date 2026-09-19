"""B3 回归：并发启动时，token 文件必须属于真正在监听的那个实例。

旧启动顺序是"先写 token 文件、再 bind"：两个实例几乎同时启动时，抢不到端口的那一个
会先把自己的 token 覆盖进文件、然后才因 EADDRINUSE 退出。启动脚本（open-ai-list.sh）
随后从文件里读到的就是**死进程的 token**，浏览器带着它访问活实例 → 全量 401，
而且没有任何自愈路径（只能手工删 token 文件重开）。

这里用真实进程复现，顺序是确定的：
1. 起 A（占住端口），确认它的 token 能被活实例接受；
2. 再起 B（同端口、同 token 文件、自己的 token）→ B 必然 bind 失败退出；
3. 断言 token 文件里仍是 A 的 token，活实例仍然接受 A、拒绝 B。

第 3 步在旧实现下必失败（文件被 B 覆盖）。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
TOKEN_A = "token-for-instance-a"
TOKEN_B = "token-for-instance-b"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class StartupTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="todo-startup-token-test-")
        root = Path(self._temp.name)
        self.port = free_port()
        # 文件名与 open-ai-list.sh 推导出来的路径一致（脚本的 TOKEN_FILE 是 ${TMPDIR}/todo-list-ai-${PORT}.token），
        # 这样最后一个用例才能拿真实脚本走一遍"读 token → 打开页面"。
        self.token_file = root / f"todo-list-ai-{self.port}.token"
        self.url = f"http://127.0.0.1:{self.port}"
        self.processes: list[subprocess.Popen] = []
        self.env = dict(os.environ)
        self.env.update({
            "TODO_AI_PORT": str(self.port),
            "TODO_SESSION_TOKEN_FILE": str(self.token_file),
            "TODO_SQLITE_FILE": str(root / "todo.sqlite3"),
            "TODO_SQLITE_BACKUP_DIR": str(root / "backups"),
            "TODO_MEMO_SQLITE_FILE": str(root / "memo.sqlite3"),
            "TMPDIR": str(root),
            "PYTHONUNBUFFERED": "1",
        })

    def tearDown(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            if process.stdout is not None:
                process.stdout.close()
        self._temp.cleanup()

    # ---------- 工具 ----------

    def start_server(self, token: str) -> subprocess.Popen:
        env = dict(self.env)
        env["TODO_SESSION_TOKEN"] = token
        process = subprocess.Popen(
            [sys.executable, "local_server.py"], cwd=str(APP_DIR), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.processes.append(process)
        return process

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/health", timeout=1) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def wait_until_healthy(self, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.healthy():
                return
            time.sleep(0.05)
        self.fail("本地服务在超时内没有起来")

    def call_projects(self, token: str) -> int:
        request = urllib.request.Request(
            f"{self.url}/api/projects", headers={"X-Todo-Session": token})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                json.loads(response.read().decode("utf-8"))
                return int(response.status)
        except urllib.error.HTTPError as error:
            try:
                error.read()
                return int(error.code)
            finally:
                error.close()

    def read_token_file(self) -> str:
        return self.token_file.read_text(encoding="utf-8").strip()

    # ---------- 用例 ----------

    def test_losing_instance_must_not_hijack_token_file(self) -> None:
        winner = self.start_server(TOKEN_A)
        self.wait_until_healthy()
        self.assertTrue(self.token_file.exists(), "活实例启动后必须写下自己的 token")
        self.assertEqual(self.read_token_file(), TOKEN_A)
        self.assertEqual(self.call_projects(TOKEN_A), 200)

        loser = self.start_server(TOKEN_B)
        try:
            returncode = loser.wait(timeout=20)
        except subprocess.TimeoutExpired:
            loser.kill()
            output = loser.stdout.read().decode("utf-8", "replace") if loser.stdout else ""
            self.fail(f"抢不到端口的实例本该立刻退出，却一直在跑：\n{output}")
        self.assertNotEqual(returncode, 0, "抢不到端口的实例必须以非 0 退出")
        self.assertIsNone(winner.poll(), "赢的实例必须还活着")

        self.assertEqual(self.read_token_file(), TOKEN_A,
                         "token 文件被抢不到端口的实例覆盖了：脚本会读到死进程的 token → 全量 401")
        self.assertEqual(self.call_projects(TOKEN_B), 401, "活实例不能接受输家的 token")
        self.assertEqual(self.call_projects(TOKEN_A), 200, "活实例必须继续接受自己的 token")

    def test_token_file_only_written_after_bind(self) -> None:
        """更直接的一条：端口被占、自己 bind 失败时，根本不碰 token 文件。"""
        self.token_file.write_text("stale-token-from-previous-run", encoding="utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as squatter:
            squatter.bind(("127.0.0.1", self.port))
            squatter.listen(5)
            loser = self.start_server(TOKEN_B)
            returncode = loser.wait(timeout=20)
        self.assertNotEqual(returncode, 0, "端口被占时必须以非 0 退出")
        self.assertEqual(self.read_token_file(), "stale-token-from-previous-run",
                         "bind 失败就不该写 token 文件")


    def test_launcher_reads_token_the_live_server_accepts(self) -> None:
        """B3 的另一半：脚本读到的 token 必须能被活实例接受（否则就是那个 401 死锁）。

        活实例已经在跑时，open-ai-list.sh 只做健康检查 + 读 token 文件，不该另起进程。
        """
        self.start_server(TOKEN_A)
        self.wait_until_healthy()
        env = dict(self.env)
        env["TODO_NO_BROWSER"] = "1"
        env.pop("TODO_SESSION_TOKEN", None)
        result = subprocess.run(["sh", "open-ai-list.sh"], cwd=str(APP_DIR), env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        printed = result.stdout.strip().splitlines()[-1]
        self.assertIn("#token=", printed, printed)
        self.assertNotIn("?token=", printed, "token 不能再拼进查询串（会进访问日志）")
        token = printed.split("#token=", 1)[1].strip()
        self.assertEqual(token, TOKEN_A, "脚本从 token 文件读到的不是活实例的 token")
        self.assertEqual(self.call_projects(token), 200,
                         "脚本打印的 token 被活实例拒绝 → 浏览器打开就是 401")

    def test_startup_url_and_access_log_do_not_leak_the_token(self) -> None:
        """token 改走 fragment（浏览器不发 # 之后的内容），旧式 ?token= 请求行必须打码。"""
        process = self.start_server(TOKEN_A)
        self.wait_until_healthy()
        # 旧式 URL：token 真的出现在请求行里，服务端日志必须把它抹掉
        with urllib.request.urlopen(f"{self.url}/?token={TOKEN_A}", timeout=10) as response:
            response.read()
        process.terminate()
        process.wait(timeout=10)
        output = process.stdout.read().decode("utf-8", "replace") if process.stdout else ""

        startup_lines = [line for line in output.splitlines() if "Todo AI running at" in line]
        self.assertTrue(startup_lines, output)
        self.assertIn("#token=", startup_lines[0], "启动打印必须用 fragment 形式")
        self.assertNotIn("?token=", startup_lines[0], "启动打印不能再出现 ?token=")

        access = "\n".join(line for line in output.splitlines() if "Todo AI running at" not in line)
        self.assertIn("token=***", access, f"旧式 ?token= 请求行没有被打码：{access}")
        self.assertNotIn(TOKEN_A, access, f"token 明文出现在访问日志里：{access}")

    def test_sigterm_shuts_down_cleanly(self) -> None:
        """后台启动（nohup … &）拿不到 Ctrl+C，SIGTERM 必须走完同一套收尾。

        旧实现下 SIGTERM 是默认动作直接死掉：没有 Stopping 日志、token 文件也不删，
        下一个启动脚本会读到一个死进程的 token。
        """
        process = self.start_server(TOKEN_A)
        self.wait_until_healthy()
        self.assertTrue(self.token_file.exists(), "活实例启动后必须写下 token 文件")

        process.terminate()   # SIGTERM
        process.wait(timeout=10)
        output = process.stdout.read().decode("utf-8", "replace") if process.stdout else ""

        self.assertIn("Stopping Todo AI.", output, f"SIGTERM 没有走收尾路径：\n{output}")
        self.assertFalse(self.token_file.exists(), "SIGTERM 收尾没有删掉 token 文件")


if __name__ == "__main__":
    unittest.main()
