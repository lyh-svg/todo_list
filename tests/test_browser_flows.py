"""Playwright 浏览器冒烟测试：真 Chromium + 真服务（临时库 + AI mock）。

覆盖使用者要求的关键流程：新建项目 → 添加任务 → 刷新 → 导入 JSON → 恢复备份 → AI 规划项目。
没装 playwright / 浏览器时会自动跳过（`TODO_SKIP_BROWSER=1` 可强制跳过），
所以 `python3 -m unittest discover -s tests` 在任何机器上都能跑。

运行：python3 -m unittest tests.test_browser_flows -v
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
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

try:  # playwright 是可选依赖
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - 取决于开发机是否装了 playwright
    sync_playwright = None

TOKEN = "browser-smoke-token"
TODAY = "2026-09-15"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def importable_project(name: str) -> dict:
    project_id = str(uuid.uuid4())
    return {
        "id": project_id,
        "name": name,
        "description": "由浏览器测试导入",
        "createdAt": TODAY,
        "assessmentEnabled": False,
        "reviewEnabled": False,
        "tree": [{
            "id": f"{project_id}-w1", "type": "week", "text": "第1周：导入", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": f"{project_id}-d1", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": [{
                    "id": f"{project_id}-i1", "type": "item", "text": "导入进来的任务",
                    "completed": False, "completedAt": None, "optional": False,
                    "assessmentRequired": False, "assessmentHistory": 0, "assessment": None,
                    "createdAt": TODAY, "children": [],
                }],
            }],
        }],
    }


class ServerProcess:
    """在临时库上启动真实服务（与 open-ai-list.sh 同一条启动路径）。"""

    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.port = free_port()
        self.log = workdir / "server.log"
        env = dict(os.environ)
        env.update({
            "TODO_SQLITE_FILE": str(workdir / "todo.sqlite3"),
            "TODO_SQLITE_BACKUP_DIR": str(workdir / "backups"),
            "TODO_MEMO_SQLITE_FILE": str(workdir / "memo.sqlite3"),
            "TODO_SUMMARY_SQLITE_FILE": str(workdir / "summary.sqlite3"),
            "TODO_SESSION_TOKEN": TOKEN,
            "TODO_SESSION_TOKEN_FILE": str(workdir / "session.token"),
            "TODO_AI_PORT": str(self.port),
            "TODO_AI_MOCK": "1",
            "DEEPSEEK_API_KEY": "mock-key",
            "TODO_IDLE_SHUTDOWN_SECONDS": "900",
        })
        self.env = env
        self.process: subprocess.Popen | None = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self.handle = self.log.open("wb")
        self.process = subprocess.Popen(
            [sys.executable, "local_server.py"], cwd=str(APP_DIR), env=self.env,
            stdout=self.handle, stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"服务启动即退出：\n{self.log.read_text(encoding='utf-8', errors='replace')[-2000:]}")
            try:
                with urllib.request.urlopen(f"{self.base}/api/health", timeout=1):
                    return
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.2)
        raise RuntimeError("服务 30 秒内没有就绪")

    def api(self, path: str, method: str = "GET", body: dict | None = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"X-Todo-Session": TOKEN,
                                                  "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8") or "{}")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        handle = getattr(self, "handle", None)
        if handle:
            handle.close()


class BrowserServerFixtureTests(unittest.TestCase):
    """先验证"真服务 + 临时库 + token"这一半（不需要浏览器，任何机器都能跑）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="todo-browser-")
        cls.workdir = Path(cls.tmp.name)
        cls.server = ServerProcess(cls.workdir)
        cls.server.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()
        cls.tmp.cleanup()

    def test_server_serves_health_and_index(self) -> None:
        with urllib.request.urlopen(f"{self.server.base}/api/health", timeout=10) as response:
            self.assertEqual(response.status, 200)
        with urllib.request.urlopen(f"{self.server.base}/?token={TOKEN}", timeout=10) as response:
            html = response.read().decode("utf-8")
        self.assertIn('id="newProjectInput"', html)
        self.assertIn("app.js?v=", html)

    def test_api_requires_the_session_token(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.server.base}/api/projects", timeout=10)
        self.assertEqual(ctx.exception.code, 401)

    def test_temp_database_is_used(self) -> None:
        """绝不能在真实 data/ 上跑浏览器测试。"""
        status, payload = self.server.api("/api/projects")
        self.assertEqual(status, 200)
        self.assertTrue((self.workdir / "todo.sqlite3").is_file())
        self.assertNotEqual(Path(self.workdir / "todo.sqlite3"), APP_DIR / "data" / "todo.sqlite3")
        self.assertIsInstance(payload.get("projects"), list)

    def test_mock_ai_plan_endpoint(self) -> None:
        status, payload = self.server.api("/api/project/plan", method="POST",
                                          body={"topic": "浏览器测试", "model": "flash"})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["plan"]["tree"], "mock 模式必须返回可用的计划树")


@unittest.skipUnless(sync_playwright is not None, "未安装 playwright（pip install -r requirements-dev.txt）")
class BrowserFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("TODO_SKIP_BROWSER"):
            raise unittest.SkipTest("TODO_SKIP_BROWSER 已设置，跳过浏览器测试")
        cls.tmp = tempfile.TemporaryDirectory(prefix="todo-browser-")
        cls.workdir = Path(cls.tmp.name)
        cls.server = ServerProcess(cls.workdir)
        cls.server.start()
        # 缺系统 NSS/NSPR 时，scripts/browser-test.sh 会把 deb 解包到 .playwright-libs；
        # 这里自动带上它，这样直接跑 unittest 也能启动浏览器（不需要 sudo）。
        libs = APP_DIR / ".playwright-libs" / "extracted" / "usr" / "lib" / "x86_64-linux-gnu"
        if libs.is_dir():
            existing = os.environ.get("LD_LIBRARY_PATH", "")
            if str(libs) not in existing.split(":"):
                os.environ["LD_LIBRARY_PATH"] = f"{libs}{':' + existing if existing else ''}"
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch()
        except Exception as error:  # 浏览器没下载好等情况
            cls.playwright.stop()
            cls.server.stop()
            raise unittest.SkipTest(
                f"Chromium 不可用（缺系统库时先跑 sudo python3 -m playwright install-deps chromium）：{error}"
            ) from error
        cls.context = cls.browser.new_context(viewport={"width": 1440, "height": 950})
        cls.page = cls.context.new_page()
        cls.page_errors: list[str] = []
        cls.dialogs: list[str] = []
        cls.page.on("pageerror", lambda error: cls.page_errors.append(str(error)))
        cls.page.on("dialog", cls._on_dialog)
        cls.page.goto(f"{cls.server.base}/?token={TOKEN}")

    @classmethod
    def _on_dialog(cls, dialog) -> None:
        cls.dialogs.append(dialog.message)
        dialog.accept()

    @classmethod
    def tearDownClass(cls) -> None:
        for closer in (getattr(cls, "context", None), getattr(cls, "browser", None)):
            try:
                closer and closer.close()
            except Exception:
                pass
        getattr(cls, "playwright", None) and cls.playwright.stop()
        getattr(cls, "server", None) and cls.server.stop()
        cls.tmp.cleanup()

    # ---------- 工具 ----------
    def wait_for_text(self, selector: str, text: str, timeout: float = 8000) -> None:
        self.page.wait_for_function(
            "([selector, text]) => (document.querySelector(selector)?.innerText || '').includes(text)",
            arg=[selector, text], timeout=timeout,
        )

    def open_more_tools(self) -> None:
        self.page.evaluate("document.getElementById('moreTools').open = true")

    # ---------- 流程 ----------
    def test_01_new_project(self) -> None:
        """新建项目：输入名称 → 点按钮 → 卡片出现。"""
        self.page.wait_for_selector("#newProjectInput")
        self.page.fill("#newProjectInput", "浏览器测试项目")
        self.page.click("#createProjectBtn")
        self.wait_for_text("#projectGrid", "浏览器测试项目")
        self.assertIn("浏览器测试项目", self.page.inner_text("#projectGrid"))

    def test_02_quick_add_task_with_preview(self) -> None:
        """添加任务：自然语言 → 先出预览（不直接写入）→ 确认后进收集箱。"""
        self.page.click("#openWorkbenchBtn")
        self.page.wait_for_selector("#workbenchView.active")
        self.page.fill("#quickAddInput", "写周报 #工作 明天 !高 30分钟")
        self.page.click("#quickAddBtn")
        self.page.wait_for_selector("#utilityModal:not([hidden])")
        body = self.page.inner_text("#utilityBody")
        self.assertIn("写周报", body)
        self.assertIn("明天", body, "预览里要显示识别出的截止日期")
        self.page.click("#utilityBody .utility-primary-btn")
        self.page.wait_for_selector("#utilityModal", state="hidden")   # 预览关掉了（hidden 属性）
        self.wait_for_text("#workbenchBody", "写周报")

    def test_03_reload_keeps_data(self) -> None:
        """刷新页面后，项目与刚添加的任务都还在（真的落库了）。"""
        self.page.reload()
        self.page.wait_for_selector("#projectGrid")
        self.wait_for_text("#projectGrid", "浏览器测试项目")
        self.page.click("#openWorkbenchBtn")
        self.page.wait_for_selector("#workbenchView.active")
        self.wait_for_text("#workbenchBody", "写周报")

    def test_04_import_json(self) -> None:
        """导入 JSON：替换现有数据（走真实文件选择框 + 确认弹窗）。"""
        backup = self.workdir / "import-me.json"
        backup.write_text(json.dumps({"schemaVersion": 2, "projects": [importable_project("导入的项目")]},
                                     ensure_ascii=False), encoding="utf-8")
        self.page.click("#workbenchBackBtn")          # 回到项目列表
        self.page.wait_for_selector("#projectsView.active")
        self.open_more_tools()
        self.page.set_input_files("#importInput", str(backup))
        # 第五批之后：导入先出预览（差异报告 + 三种模式），确认后才写库
        self.page.wait_for_selector("#utilityModal:not([hidden])", timeout=15000)
        report = self.page.inner_text("#utilityBody")
        self.assertIn("新增项目", report, f"预览里要有新增项目：{report[:200]}")
        self.assertIn("导入方式", report)
        self.assertIn("AI 历史", report)
        self.page.click("#utilityBody .utility-primary-btn")
        self.page.wait_for_selector("#utilityModal", state="hidden", timeout=20000)
        self.wait_for_text("#projectGrid", "导入的项目")
        self.assertIn("导入的项目", self.page.inner_text("#projectGrid"))
        self.assertNotIn("浏览器测试项目", self.page.inner_text("#projectGrid"), "导入是整体替换")

    def test_05_restore_backup(self) -> None:
        """恢复备份：先用 UI 建备份 → 用 API 改坏数据 → 用 UI 恢复到备份状态。"""
        self.open_more_tools()
        self.page.click("#createDatabaseBackupBtn")
        self.page.wait_for_function(
            "() => !document.getElementById('databaseBackupPickerButton').innerText.includes('还没有')",
            timeout=15000,
        )
        # 改坏：把当前项目删掉（模拟误删）
        status, payload = self.server.api("/api/projects")
        self.assertEqual(status, 200)
        project = next(entry for entry in payload["projects"] if entry["name"] == "导入的项目")
        status, _ = self.server.api(
            f"/api/project?id={project['id']}&revision={project['_revision']}", method="DELETE")
        self.assertEqual(status, 200)
        self.page.reload()
        self.page.wait_for_selector("#projectGrid")
        self.page.wait_for_function(
            "() => !document.getElementById('projectGrid').innerText.includes('导入的项目')", timeout=10000)

        # 用 UI 恢复：打开备份下拉 → 选中刚才那份 → 点恢复（恢复成功后页面会 reload）
        self.open_more_tools()
        self.page.click("#databaseBackupPickerButton")
        self.page.wait_for_selector("#databaseBackupMenu .backup-picker-option")
        self.page.click("#databaseBackupMenu .backup-picker-option")
        with self.page.expect_navigation(timeout=30000):
            self.page.click("#restoreDatabaseBackupBtn")
        self.wait_for_text("#projectGrid", "导入的项目", timeout=20000)
        self.assertTrue(any("恢复" in message for message in self.dialogs), f"应出现恢复确认：{self.dialogs}")

    def test_06_ai_plan_creates_project(self) -> None:
        """AI 规划（mock）：勾选后建项目，应由服务端生成计划树并进入详情页。"""
        self.page.wait_for_selector("#projectsView.active")
        self.page.check("#newProjectPlanToggle")
        self.page.fill("#newProjectInput", "AI 规划项目")
        self.page.click("#createProjectBtn")
        self.page.wait_for_selector("#detailView.active", timeout=15000)
        self.page.wait_for_selector("#treeRoot .node-row", timeout=10000)
        tree_text = self.page.inner_text("#treeRoot")
        self.assertIn("第1周", tree_text)
        self.assertIn("AI 规划项目", self.page.inner_text("#detailTitle"))
        self.page.uncheck("#newProjectPlanToggle") if self.page.is_checked("#newProjectPlanToggle") else None

    def test_07_no_page_errors(self) -> None:
        """整条流程下来不允许有未捕获的前端异常。"""
        self.assertEqual(self.page_errors, [], f"页面出现未捕获异常：{self.page_errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
