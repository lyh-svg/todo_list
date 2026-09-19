#!/usr/bin/env python3
"""规模基线：生成 1000 / 10000 个任务的临时库，量出各操作的耗时与载荷大小。

用途：性能优化前后对比、判断"哪些优化真的有必要"。全部在 /tmp 临时库上跑，不碰 data/。

    python3 scripts/benchmark_scale.py                 # 默认 1000 / 10000
    python3 scripts/benchmark_scale.py --sizes 2000 --repeat 5
    python3 scripts/benchmark_scale.py --json          # 机器可读输出

指标口径：
- 「保存（单节点改动）」= 前端勾选一个复选框后走的那条路：整棵树 JSON 序列化 + 落库；
  同时给出「节点级 patch」的实测值作为对照（`UPDATE nodes ... + revision+1`）。
- 「载荷」= 前端一次全量保存要 POST 的 JSON 字节数（当前架构的固定开销）。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

TODAY = date.today().isoformat()

REAL_DATA_DIR = (APP_DIR / "data").resolve()
WORK = Path(tempfile.mkdtemp(prefix="todo-bench-"))
os.environ["TODO_SQLITE_FILE"] = str(WORK / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(WORK / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(WORK / "memo.sqlite3")


def assert_temp_databases() -> None:
    """硬性拒绝把基准数据写进仓库 data/。

    事故（2026-09-19）：这几个环境变量原本只在 main() 里设置，于是"import 这个模块、
    直接调 build_project() 自己量一把"就会在**没有任何环境变量**的情况下 import storage，
    落到真实 data/todo.sqlite3 上（实测把 10220 个节点的基线项目写进了用户的库）。
    现在环境变量在模块级就设好，并且把这一层断言放在真正写库的入口上。
    """
    for env_name in ("TODO_SQLITE_FILE", "TODO_MEMO_SQLITE_FILE"):
        path = Path(os.environ[env_name]).resolve()
        if path == REAL_DATA_DIR or REAL_DATA_DIR in path.parents:
            raise SystemExit(f"基准拒绝写入真实数据目录：{path}")


def build_project(project_id: str, total: int) -> dict:
    """把 total 个任务铺成 周 → 单元 → 任务，带元数据、部分完成与复习。"""
    weeks = 20 if total > 4000 else 10
    days_per_week = 10
    items_per_day = max(1, total // (weeks * days_per_week))
    index = 0
    tree = []
    for week_no in range(1, weeks + 1):
        week = {"id": f"{project_id}-w{week_no}", "type": "week", "text": f"第{week_no}周",
                "completed": False, "expanded": week_no == 1, "createdAt": TODAY, "children": []}
        for day_no in range(1, days_per_week + 1):
            day = {"id": f"{project_id}-w{week_no}-d{day_no}", "type": "day",
                   "text": f"单元{day_no}", "completed": False, "expanded": False,
                   "createdAt": TODAY, "children": []}
            for _item_no in range(items_per_day):
                index += 1
                if index > total:
                    break
                completed = index % 4 == 0
                item = {
                    "id": f"{project_id}-i{index}", "type": "item", "text": f"任务 {index}：解释并举例",
                    "completed": completed,
                    "completedAt": f"{TODAY}T08:00:00" if completed else None,
                    "optional": index % 7 == 0, "assessmentRequired": False, "assessmentHistory": 0,
                    "assessment": None, "createdAt": TODAY, "children": [],
                    "priority": ["high", "mid", "low", ""][index % 4],
                    "dueDate": (date.today() + timedelta(days=index % 30)).isoformat(),
                    "estimateMinutes": (index % 6) * 15,
                    "tags": ["基线", f"组{index % 5}"],
                    "note": f"第 {index} 个任务的备注" if index % 3 == 0 else "",
                    "links": [{"label": "资料", "url": "https://example.com"}] if index % 5 == 0 else [],
                }
                if completed:
                    item["review"] = {"due": (date.today() + timedelta(days=index % 5)).isoformat(),
                                      "learning": False, "log": [{"at": TODAY, "result": "good"}]}
                day["children"].append(item)
            week["children"].append(day)
        tree.append(week)
    return {"id": project_id, "name": f"基线项目 {total} 任务", "description": "性能基线",
            "createdAt": TODAY, "assessmentEnabled": False, "reviewEnabled": True,
            "archived": False, "tree": tree}


def timed(func, repeat: int) -> float:
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        func()
        samples.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(samples), 1)


def run_size(total: int, repeat: int) -> dict[str, object]:
    import storage  # noqa: PLC0415  必须在环境变量之后导入
    assert_temp_databases()

    db = Path(storage.DATABASE_FILE)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db}{suffix}").unlink(missing_ok=True)
    with storage.open_state_database() as connection:
        connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION}")
    storage.ensure_schema()

    project = build_project("bench", total)
    payload_bytes = len(json.dumps(project, ensure_ascii=False).encode("utf-8"))
    start = time.perf_counter()
    revision, _summary = storage.write_project(project, None)
    insert_ms = round((time.perf_counter() - start) * 1000, 1)

    stored, revision = storage.read_project("bench")
    node_count = len(storage._walk_nodes(stored["tree"]))
    item = stored["tree"][0]["children"][0]["children"][0]

    def toggle_full_save() -> None:
        """当前架构：改一个节点 → 整棵树 POST → 服务端逐行 diff。"""
        live, rev = storage.read_project("bench")
        target = storage._find_node(live["tree"], item["id"])
        target["completed"] = not target["completed"]
        storage.write_project(live, rev)

    def toggle_patch() -> None:
        """节点级 patch 的对照实现：只更新一行 + 项目 revision+1。"""
        with storage.open_state_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE nodes SET completed=?,completed_at=? WHERE project_id=? AND node_id=?",
                (1, f"{TODAY}T09:00:00", "bench", item["id"]))
            connection.execute("UPDATE projects SET revision=revision+1,updated_at=? WHERE project_id=?",
                               (TODAY, "bench"))

    # 直接测新的服务端接口实现（复习队列 / 跨项目搜索），而不是手写对照 SQL
    def review_query() -> None:
        storage.list_review_queue(TODAY)

    def search_query() -> None:
        storage.search_everything("举例")

    import memo_storage  # noqa: PLC0415
    memo_storage.initialize()
    for index in range(200):
        memo_storage.write_memo({"title": f"备忘 {index}", "content": "正文" * 400})

    result = {
        "tasks": total,
        "nodes": node_count,
        "initialInsertMs": insert_ms,
        "fullSaveMs": timed(toggle_full_save, repeat),
        "nodePatchMs": timed(toggle_patch, repeat),
        "readProjectMs": timed(lambda: storage.read_project("bench"), repeat),
        "workbenchMs": timed(lambda: storage.workbench(TODAY), repeat),
        "reviewCountsMs": timed(lambda: storage.review_counts(TODAY), repeat),
        "reviewQueryMs": timed(review_query, repeat),
        "searchQueryMs": timed(search_query, repeat),
        "diagnosticsMs": timed(storage.storage_diagnostics, max(1, repeat // 2)),
        "exportSnapshotMs": timed(storage.export_projects_snapshot, max(1, repeat // 2)),
        "memoListMs": timed(memo_storage.list_memo_summaries, repeat),
        "memoSearchMs": timed(lambda: memo_storage.search_memo_summaries("正文"), repeat),
        "savePayloadBytes": payload_bytes,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="规模基线（临时库，不碰 data/）")
    parser.add_argument("--sizes", default="1000,10000", help="逗号分隔的任务数")
    parser.add_argument("--repeat", type=int, default=3, help="每个操作重复次数（取中位数）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    sizes = [int(part) for part in args.sizes.split(",") if part.strip()]

    work = WORK          # 临时库在模块导入时就设好了（见 assert_temp_databases 的事故说明）
    assert_temp_databases()

    results = []
    try:
        for size in sizes:
            print(f"… 生成并测量 {size} 个任务", file=sys.stderr)
            results.append(run_size(size, args.repeat))
            for suffix in ("", "-wal", "-shm"):
                Path(f"{work}/todo.sqlite3{suffix}").unlink(missing_ok=True)
                Path(f"{work}/memo.sqlite3{suffix}").unlink(missing_ok=True)
                Path(f"{work}/summary.sqlite3{suffix}").unlink(missing_ok=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    labels = [
        ("initialInsertMs", "首次写入整棵树"),
        ("savePayloadBytes", "一次全量保存的 JSON 载荷(字节)"),
        ("fullSaveMs", "保存（改 1 个节点 → 整棵树重写）"),
        ("nodePatchMs", "保存（节点级 patch，仅 1 行 + revision）"),
        ("readProjectMs", "读取整个项目"),
        ("workbenchMs", "今日工作台聚合"),
        ("reviewCountsMs", "复习计数（列表页）"),
        ("reviewQueryMs", "复习队列（GET /api/reviews）"),
        ("searchQueryMs", "全局搜索（GET /api/search）"),
        ("diagnosticsMs", "/api/storage 诊断"),
        ("exportSnapshotMs", "导出快照（全项目）"),
        ("memoListMs", "备忘录列表（200 条）"),
        ("memoSearchMs", "备忘录全文搜索（200 条）"),
    ]
    header = f"{'指标':<40}" + "".join(f"{str(entry['tasks']) + ' 任务':>16}" for entry in results)
    print(header)
    print("-" * len(header))
    for key, label in labels:
        row = f"{label:<40}"
        for entry in results:
            value = entry.get(key, "—")
            row += f"{value:>16}" if isinstance(value, (int, float)) else f"{str(value):>16}"
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
