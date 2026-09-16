#!/usr/bin/env python3
"""写锁基准：保存 1 万任务的同时答题，量复习写入是否会被项目保存拖住。

背景：`storage.write_project()`（整棵树写库）与 `review_storage.apply_grade()`（记一次作答）
共用同一把 `storage.state_lock()`。这个基准就是在临时库上制造最坏情况——
一边整棵树保存 1 万个任务，一边答题，量「答题要等多久才拿到写锁」。

口径：
- `answerWhileSavingMs` = 保存进行中发起的一次 `apply_grade()` 端到端耗时（5 轮的中位数）。
  它包含"等保存让出写锁"的时间；因为它真正反映了用户点「确定」后要等多久，
  所以这个值越高说明答题被项目保存拖得越久。
- `fullSaveWithAnswerMs` = 同一次并发下整棵树保存本身的耗时（5 轮的中位数）。
- `baseline` = 无并发的 10k 任务整棵树保存参考值（脚本内实测，不是抄来的常量）。

全部在 /tmp 临时库上跑，不碰 data/。

    python3 scripts/benchmark_review.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))
WORK = Path(tempfile.mkdtemp(prefix="todo-review-bench-"))
os.environ["TODO_SQLITE_FILE"] = str(WORK / "todo.sqlite3")
os.environ["TODO_SQLITE_BACKUP_DIR"] = str(WORK / "backups")
os.environ["TODO_MEMO_SQLITE_FILE"] = str(WORK / "memo.sqlite3")
os.environ["TODO_SUMMARY_SQLITE_FILE"] = str(WORK / "summary.sqlite3")

import review_storage  # noqa: E402
import storage  # noqa: E402

TODAY = "2026-09-16"
ROUNDS = 5
TOTAL_TASKS = 10000


def build_project(total: int) -> dict:
    """把 total 个任务铺成 周 → 单元 → 任务（与 benchmark_scale.py 同一形状）。

    注意：单元 id 必须带周号。brief 里的 `d{day_no}` 在第 2 周会与第 1 周撞 id，
    `storage._flatten_nodes` 会以「节点 ID 重复」拒绝整棵树（实测，见 Task 16 报告）。
    """
    weeks, index = [], 0
    while index < total:
        week_no = len(weeks) + 1
        days = []
        for day_no in range(1, 11):
            items = []
            for _ in range(max(1, total // 100)):
                index += 1
                if index > total:
                    break
                items.append({"id": f"i{index}", "type": "item", "text": f"任务 {index}",
                              "completed": False, "completedAt": None, "optional": False,
                              "assessmentRequired": False, "assessmentHistory": 0, "assessment": None,
                              "createdAt": TODAY, "children": []})
            if items:
                days.append({"id": f"w{week_no}-d{day_no}", "type": "day", "text": f"单元{day_no}",
                             "completed": False, "expanded": False, "createdAt": TODAY, "children": items})
        weeks.append({"id": f"w{week_no}", "type": "week", "text": f"第{week_no}周",
                      "completed": False, "expanded": False, "createdAt": TODAY, "children": days})
    return {"id": "bench", "name": "规模基准", "description": "", "createdAt": TODAY,
            "assessmentEnabled": False, "tree": weeks}


def timed_save(project: dict, revision: int) -> tuple[float, int]:
    start = time.perf_counter()
    next_revision, _ = storage.write_project(project, revision)
    return (time.perf_counter() - start) * 1000, next_revision


def timed_answer(code: str, round_no: int, answer_ms: list[float], failure: list[BaseException],
                 done: threading.Event) -> None:
    """答题线程主体：量一次 apply_grade 的端到端耗时，异常带出去让主线程抛。

    定义在模块级而不是循环内闭包：ruff B023（函数不绑定循环变量）会把它当成
    "每轮共用一个 done/failure"的隐患——虽然这里每轮都会 join，但还是显式传参更清楚。
    """
    start = time.perf_counter()
    try:
        review_storage.apply_grade(code, "concept", 3, today=TODAY, answer=f"基准 {round_no}")
    except BaseException as error:  # noqa: BLE001 - 线程里的异常必须带回主线程，否则会静默少一轮
        failure.append(error)
    finally:
        answer_ms.append((time.perf_counter() - start) * 1000)
        done.set()


def main() -> int:
    storage.ensure_schema()
    # 基准要答真实的题：先把内置第 1 周内容导入临时库（真实库只读，不被碰）。
    review_storage.ensure_content_imported()
    project = build_project(TOTAL_TASKS)
    # 并发保存同一棵树要带乐观锁版本号；brief 里的 `write_project(project, None)`
    # 只在首次插入合法，第二轮起就会撞 StateConflictError（实测，见 Task 16 报告）。
    revision, _ = storage.write_project(project, None)
    code = review_storage.list_points()["points"][0]["code"]

    # 基线：无并发时整棵树保存耗时，用来判断并发答题有没有把保存本身也拖慢。
    baseline_samples = []
    for _ in range(ROUNDS):
        elapsed, revision = timed_save(project, revision)
        baseline_samples.append(elapsed)
    baseline_ms = statistics.median(baseline_samples)

    answer_ms, save_ms = [], []
    for round_no in range(ROUNDS):
        done = threading.Event()
        failure: list[BaseException] = []
        thread = threading.Thread(target=timed_answer,
                                 args=(code, round_no, answer_ms, failure, done))
        thread.start()
        save_start = time.perf_counter()
        revision, _ = storage.write_project(project, revision)  # 10k 任务整棵树写入，与答题共用同一把写锁
        save_ms.append((time.perf_counter() - save_start) * 1000)
        done.wait(timeout=30)
        thread.join(timeout=30)
        if failure:
            raise failure[0]
        if thread.is_alive():
            raise RuntimeError("答题线程 30 秒内没结束：可能被写锁死等")

    payload = {
        "answerWhileSavingMs": round(statistics.median(answer_ms), 1),
        "fullSaveWithAnswerMs": round(statistics.median(save_ms), 1),
        "baseline": f"10k 任务整棵树保存（无并发）本次实测中位数 {round(baseline_ms, 1)}ms；"
                    "对照 scripts/benchmark_scale.py 的 fullSaveMs",
        "tasks": TOTAL_TASKS,
        "rounds": ROUNDS,
        "samples": {"answerMs": [round(value, 1) for value in answer_ms],
                    "saveMs": [round(value, 1) for value in save_ms],
                    "baselineMs": [round(value, 1) for value in baseline_samples]},
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
