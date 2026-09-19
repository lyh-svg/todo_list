"""整项目全量保存的写放大回归（P1）。

背景（实测）：`_upsert_project` 对每个节点无条件发一条 upsert，`_write_assessment` 对没有验收的
节点也发一条 DELETE、对有验收的节点逐条 upsert 每条对话消息。1000 节点 + 1.2 万条对话的
项目，即使内容一个字都没变，重写一次也要发出约 1.6 万条 SQL（其中 1.2 万条是"写了等于没写"的
对话 upsert），耗时 167 ms。

这里用 **SQL 语句计数** 做断言而不是耗时：计数是确定性的，不受机器负载影响。
"""

from __future__ import annotations

import copy
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-write-amp-test-")
os.environ.setdefault("TODO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "todo.sqlite3"))
os.environ.setdefault("TODO_SQLITE_BACKUP_DIR", str(Path(_TEMP_DIR.name) / "backups"))
os.environ.setdefault("TODO_MEMO_SQLITE_FILE", str(Path(_TEMP_DIR.name) / "memo.sqlite3"))

import storage  # noqa: E402

TODAY = "2026-09-16"

NODE_WRITES = ("INSERT INTO NODES", "UPDATE NODES", "DELETE FROM NODES")
ASSESSMENT_WRITES = ("INSERT INTO ASSESSMENTS", "UPDATE ASSESSMENTS", "DELETE FROM ASSESSMENTS")
CONVERSATION_WRITES = ("INSERT INTO CONVERSATIONS", "UPDATE CONVERSATIONS", "DELETE FROM CONVERSATIONS")


class SqlLog:
    """记录写入型 SQL 语句（trace callback）。"""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def __call__(self, statement: str) -> None:
        self.statements.append(" ".join(statement.split()).upper())

    def count(self, prefixes: tuple[str, ...]) -> int:
        return sum(1 for statement in self.statements if statement.startswith(prefixes))

    @property
    def node_writes(self) -> int:
        return self.count(NODE_WRITES)

    @property
    def assessment_writes(self) -> int:
        return self.count(ASSESSMENT_WRITES)

    @property
    def conversation_writes(self) -> int:
        return self.count(CONVERSATION_WRITES)

    @property
    def row_writes(self) -> int:
        return self.node_writes + self.assessment_writes + self.conversation_writes


@contextmanager
def traced_database():
    """把 storage 打开的连接都挂上 trace callback。"""
    log = SqlLog()
    original = storage.open_state_database

    def traced():
        connection = original()
        connection.set_trace_callback(log)
        return connection

    storage.open_state_database = traced
    try:
        yield log
    finally:
        storage.open_state_database = original


def conversations_for(seed: str) -> list[list[dict[str, str]]]:
    return [
        [{"role": "user", "content": f"{seed} 第1题回答"},
         {"role": "assistant", "content": f"{seed} 第1题点评"}],
        [{"role": "user", "content": f"{seed} 第2题回答"},
         {"role": "assistant", "content": f"{seed} 第2题点评"}],
    ]


def assessment_for(seed: str) -> dict:
    return {
        "stage": "implementation",
        "passed": True,
        "score": 90,
        "summary": "通过",
        "questionSet": ["q1", "q2"],
        "questionIndex": 2,
        "questionPassed": True,
        "questionAnswers": ["a1", "a2"],
        "questionConversations": conversations_for(seed),
        "questionResults": [{"index": 0, "passed": True, "score": 90}],
    }


def make_project(item_count: int = 3, with_assessment: bool = True, project_id: str = "p1") -> dict:
    items = []
    for index in range(1, item_count + 1):
        item = {
            "id": f"{project_id}-i{index}", "type": "item", "text": f"任务 {index}",
            "completed": False, "optional": False, "assessmentRequired": True,
            "assessmentHistory": 0, "createdAt": TODAY, "children": [],
        }
        if with_assessment:
            item["assessment"] = assessment_for(f"任务{index}")
        items.append(item)
    return {
        "id": project_id,
        "name": "写放大项目",
        "description": "",
        "createdAt": TODAY,
        "assessmentEnabled": True,
        "reviewEnabled": False,
        "tree": [{
            "id": f"{project_id}-w", "type": "week", "text": "第1周", "completed": False,
            "expanded": False, "createdAt": TODAY, "children": [{
                "id": f"{project_id}-d", "type": "day", "text": "单元1", "completed": False,
                "expanded": False, "createdAt": TODAY, "children": items,
            }],
        }],
    }


def stored_project() -> dict:
    return storage.read_project("p1")[0]


def find_item(project: dict, node_id: str) -> dict:
    return storage._find_node(project["tree"], node_id)


class WriteAmplificationTests(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{storage.DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        storage.ensure_schema()
        storage.write_project(make_project(), None)

    def rewrite(self, project: dict) -> SqlLog:
        revision = storage.read_project("p1")[1]
        with traced_database() as log:
            storage.write_project(project, revision)
        return log

    # ---- 写放大本身 ----

    def test_unchanged_rewrite_issues_no_row_writes(self) -> None:
        """内容一个字都没变时，节点/验收/对话三张表都不该收到写语句。"""
        live = stored_project()
        log = self.rewrite(live)
        self.assertEqual(
            log.row_writes, 0,
            f"内容未变却写了 {log.row_writes} 条（节点 {log.node_writes} / "
            f"验收 {log.assessment_writes} / 对话 {log.conversation_writes}）",
        )

    def test_single_node_change_writes_only_that_row(self) -> None:
        """只改一个任务的完成态：只应写一行节点，验收与对话不动。"""
        live = stored_project()
        find_item(live, "p1-i2")["completed"] = True
        find_item(live, "p1-i2")["completedAt"] = f"{TODAY}T10:00:00"
        log = self.rewrite(live)
        self.assertEqual(log.node_writes, 1)
        self.assertEqual(log.assessment_writes, 0)
        self.assertEqual(log.conversation_writes, 0)

    def test_changed_message_writes_only_that_message(self) -> None:
        """只改一条对话消息：只应写那一行对话，不重写其余 3 条。"""
        live = stored_project()
        find_item(live, "p1-i1")["assessment"]["questionConversations"][0][0]["content"] = "改过的回答"
        log = self.rewrite(live)
        self.assertEqual(log.node_writes, 0)
        self.assertEqual(log.assessment_writes, 0)
        self.assertEqual(log.conversation_writes, 1)

    def test_reordered_node_writes_only_that_row(self) -> None:
        """拖拽/移动会改 parent_id 与 position：必须被指纹认出来并写回。"""
        live = stored_project()
        children = live["tree"][0]["children"][0]["children"]
        moved = children.pop()          # p1-i3 挪到最前面
        children.insert(0, moved)
        log = self.rewrite(live)
        self.assertEqual(log.node_writes, 3)   # 三个任务的下标都变了，各写一行（其余节点不动）
        after = stored_project()["tree"][0]["children"][0]["children"]
        self.assertEqual([node["id"] for node in after], ["p1-i3", "p1-i1", "p1-i2"])

    def test_added_and_renamed_nodes_are_written(self) -> None:
        live = stored_project()
        find_item(live, "p1-i1")["text"] = "改名后的任务"
        live["tree"][0]["children"][0]["children"].append({
            "id": "p1-i4", "type": "item", "text": "新任务", "completed": False,
            "optional": False, "assessmentRequired": False, "assessmentHistory": 0,
            "createdAt": TODAY, "children": [],
        })
        log = self.rewrite(live)
        self.assertEqual(log.node_writes, 2)   # 改名 1 行 + 新增 1 行
        after = stored_project()["tree"][0]["children"][0]["children"]
        self.assertEqual([node["id"] for node in after], ["p1-i1", "p1-i2", "p1-i3", "p1-i4"])
        self.assertEqual(after[0]["text"], "改名后的任务")

    def test_first_write_still_persists_everything(self) -> None:
        """优化不能把首次写入写漏：节点/验收/对话 rows 都要齐。"""
        with traced_database() as log:
            storage.write_project(make_project(item_count=4, project_id="p2"), None)
        self.assertEqual(log.node_writes, 6)           # 1 周 + 1 单元 + 4 任务
        self.assertEqual(log.assessment_writes, 4)
        self.assertEqual(log.conversation_writes, 4 * 2 * 2)  # 4 个任务 × 2 题 × 2 条消息

    # ---- 差集删除的语义必须原样保留 ----

    def test_removed_node_is_deleted_with_its_assessment(self) -> None:
        live = stored_project()
        live["tree"][0]["children"][0]["children"] = [
            node for node in live["tree"][0]["children"][0]["children"] if node["id"] != "p1-i2"
        ]
        log = self.rewrite(live)
        # 开了 foreign_keys 时级联会把父语句重复回调，所以只断言"发生了删除"+ 落库状态
        self.assertGreaterEqual(log.count(("DELETE FROM NODES",)), 1)
        self.assertIsNone(find_item(stored_project(), "p1-i2"))

    def test_clearing_assessment_deletes_only_that_row(self) -> None:
        live = stored_project()
        find_item(live, "p1-i3")["assessment"] = None
        log = self.rewrite(live)
        self.assertEqual(log.assessment_writes, 1)
        self.assertEqual(log.count(("DELETE FROM ASSESSMENTS",)), 1)
        self.assertIsNone(find_item(stored_project(), "p1-i3").get("assessment"))

    def test_explicit_empty_conversations_delete_them(self) -> None:
        live = stored_project()
        find_item(live, "p1-i1")["assessment"]["questionConversations"] = []
        log = self.rewrite(live)
        self.assertEqual(log.count(("DELETE FROM CONVERSATIONS",)), 4)
        stored = find_item(stored_project(), "p1-i1")
        self.assertEqual(stored["assessment"].get("questionConversations"), [])

    def test_missing_conversations_key_keeps_them(self) -> None:
        """局部写入只带 passed：不能删已有逐题对话（历史数据丢失的那个坑）。"""
        live = stored_project()
        find_item(live, "p1-i1")["assessment"] = {"passed": True}
        log = self.rewrite(live)
        self.assertEqual(log.count(("DELETE FROM CONVERSATIONS",)), 0)
        stored = find_item(stored_project(), "p1-i1")
        self.assertEqual(len(stored["assessment"]["questionConversations"]), 2)
        self.assertEqual(
            stored["assessment"]["questionConversations"][0][0]["content"], "任务1 第1题回答"
        )

    def test_shortened_conversations_delete_the_extra_messages(self) -> None:
        live = stored_project()
        dropped = find_item(live, "p1-i1")["assessment"]["questionConversations"][0][1]
        find_item(live, "p1-i1")["assessment"]["questionConversations"][0] = [
            {"role": "user", "content": dropped["content"]},
        ]
        log = self.rewrite(live)
        self.assertEqual(log.count(("DELETE FROM CONVERSATIONS",)), 1)
        stored = find_item(stored_project(), "p1-i1")
        self.assertEqual(len(stored["assessment"]["questionConversations"][0]), 1)

    # ---- 往返一致性 ----

    def test_unchanged_rewrite_round_trips(self) -> None:
        live = stored_project()
        self.rewrite(copy.deepcopy(live))
        after = stored_project()
        self.assertEqual(after["tree"][0]["children"][0]["children"], live["tree"][0]["children"][0]["children"])
        self.assertEqual(len(after["tree"][0]["children"][0]["children"]), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
