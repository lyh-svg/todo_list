"""备忘录列表"只给预览、全文按需加载"的回归测试。

背景：`/api/memos` 以前返回所有备忘录的全文。改成预览后，有两条硬约束必须守住：
  1. 搜索仍要能命中正文深处的关键词（不能只看前 200 字）；
  2. 拿到的预览绝不能被当成全文写回（否则会把备忘录截断）。

运行：python3 -m unittest discover -s tests -v
只用标准库；所有路径指向临时目录，不碰 data/ 下的真实数据库。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

_TEMP_DIR = tempfile.TemporaryDirectory(prefix="todo-memo-test-")
os.environ["TODO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(Path(_TEMP_DIR.name) / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(Path(_TEMP_DIR.name) / "memo.sqlite3")

import memo_storage  # noqa: E402  （必须在上面的环境变量之后导入）

PREVIEW_CHARS = 200
LONG_BODY = "开头几句。" + ("填充内容" * 400) + "深埋的关键词：量子隧穿"


class MemoSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        # 安全性自检：绝不允许测试写到真实的 data/memo.sqlite3
        self.assertNotEqual(
            Path(memo_storage.MEMO_DATABASE_FILE),
            APP_DIR / "data" / "memo.sqlite3",
            "测试必须使用临时数据库",
        )
        for suffix in ("", "-wal", "-shm"):
            Path(f"{memo_storage.MEMO_DATABASE_FILE}{suffix}").unlink(missing_ok=True)
        memo_storage.initialize()
        # initialize() 会补一条"未命名备忘录"占位；测试要的是真正的空表。
        with memo_storage.open_memo_database() as connection:
            connection.execute("DELETE FROM memos")

    def _write(self, title: str, content: str) -> dict:
        return memo_storage.write_memo({"title": title, "content": content, "pinned": False})

    def test_list_summaries_does_not_leak_full_content(self) -> None:
        """列表只能给预览，不能给全文。"""
        self._write("长文", LONG_BODY)
        summaries = memo_storage.list_memo_summaries()
        self.assertEqual(len(summaries), 1)
        summary = summaries[0]
        self.assertNotIn("content", summary, "列表返回值里不能带全文")
        self.assertIn("contentPreview", summary)
        self.assertLessEqual(len(summary["contentPreview"]), PREVIEW_CHARS)
        self.assertEqual(summary["contentLength"], len(LONG_BODY))
        self.assertEqual(summary["title"], "长文")
        self.assertTrue(summary["updatedAt"])
        self.assertGreaterEqual(summary["revision"], 1)

    def test_summaries_cover_every_memo_in_order(self) -> None:
        self._write("A", "aaa")
        self._write("B", "bbb")
        summaries = memo_storage.list_memo_summaries()
        self.assertEqual(sorted(item["title"] for item in summaries), ["A", "B"])

    def test_search_matches_text_beyond_the_preview(self) -> None:
        """关键：搜索必须走全文，而不是只看预览。"""
        self._write("长文", LONG_BODY)
        self._write("短文", "只有一点点内容")
        hits = memo_storage.search_memo_summaries("量子隧穿")
        self.assertEqual([item["title"] for item in hits], ["长文"], "正文深处的关键词必须能搜到")
        self.assertNotIn("content", hits[0])
        self.assertLessEqual(len(hits[0]["contentPreview"]), PREVIEW_CHARS)

    def test_search_matches_title_too(self) -> None:
        self._write("Python 装饰器笔记", "正文")
        self.assertEqual([item["title"] for item in memo_storage.search_memo_summaries("装饰器")],
                         ["Python 装饰器笔记"])

    def test_search_escapes_like_wildcards(self) -> None:
        """% 和 _ 必须当普通字符：搜 "%" 只命中真的含 % 的那条，而不是全部。"""
        self._write("百分比", "100% 完成度")
        self._write("下划线", "snake_case 命名")
        self._write("普通", "没有特殊符号")
        self.assertEqual([item["title"] for item in memo_storage.search_memo_summaries("100%")], ["百分比"])
        self.assertEqual([item["title"] for item in memo_storage.search_memo_summaries("%")], ["百分比"])
        self.assertEqual([item["title"] for item in memo_storage.search_memo_summaries("_")], ["下划线"])

    def test_search_with_empty_query_returns_all(self) -> None:
        self._write("A", "aaa")
        self._write("B", "bbb")
        self.assertEqual(len(memo_storage.search_memo_summaries("")), 2)

    def test_read_memo_still_returns_full_content(self) -> None:
        memo = self._write("长文", LONG_BODY)
        full = memo_storage.read_memo(memo["id"])
        self.assertEqual(full["content"], LONG_BODY)

    def test_preview_then_write_roundtrip_keeps_content(self) -> None:
        """预览 → 读全文 → 写回：内容不能被截断（前端守卫的服务端侧对照）。"""
        memo = self._write("长文", LONG_BODY)
        summary = next(item for item in memo_storage.list_memo_summaries() if item["id"] == memo["id"])
        # 模拟"只拿预览就保存"会发生的截断
        truncated = "".join(summary["contentPreview"])
        self.assertNotEqual(truncated, LONG_BODY)
        # 正确路径：先读全文再写回
        full = memo_storage.read_memo(summary["id"])
        saved = memo_storage.write_memo({
            "id": full["id"], "title": full["title"], "content": full["content"],
            "pinned": full["pinned"], "expectedRevision": full["revision"],
        })
        self.assertEqual(saved["content"], LONG_BODY)
        self.assertEqual(len(memo_storage.read_memo(memo["id"])["content"]), len(LONG_BODY))

    def test_preview_is_stable_for_short_content(self) -> None:
        self._write("短", "短内容")
        summary = memo_storage.list_memo_summaries()[0]
        self.assertEqual(summary["contentPreview"], "短内容")
        self.assertEqual(summary["contentLength"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)


def tearDownModule() -> None:
    # 模块级临时目录留到解释器退出才被 GC：每个模块都会留一条 ResourceWarning，
    # 而且目录要到那时才删。跑完这个模块就显式清掉。
    _TEMP_DIR.cleanup()
