#!/usr/bin/env python3
"""写锁基准：保存大项目的同时答题，量「谁先持锁、另一方要等多久」。

为什么重写口径（Task 16 复审）：旧版在 `thread.start()` 之后立刻 `write_project(...)`，
没有任何同步保证保存先持锁；量到的 ~15ms 其实常常是「答题先抢到锁、保存根本没挡它」，
不能拿来判断「答题要不要等保存」。现在改用一把带信号的锁包住 `storage` 的写锁：
基准等到目标线程**真正拿到锁**再发起另一方，两种顺序都量——

- `answerWaitedForSaveMs`：保存先持锁 → 答题端到端耗时的中位数（含等写锁），
  这才是"答题点确定后要等多久"的真实口径。
- `saveWaitedForAnswerMs`：答题先持锁 → 保存端到端耗时的中位数（含等写锁），反向对照。
- `fullSaveMs`：两个并发顺序下保存耗时合并后的中位数。
- `baselineSaveMs`：同样这棵树、无并发时保存耗时的中位数。

每档 5 轮取中位数；默认跑 10000 节点（最坏情况）与 223 节点（真实项目规模）两档，
两档都给同样四个数字。全部在 /tmp 临时库上跑，不碰 data/。

    python3 scripts/benchmark_review.py                 # 10k + 223
    python3 scripts/benchmark_review.py --tasks 10000    # 只跑一档
"""

from __future__ import annotations

import argparse
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


def assert_temp_databases() -> None:
    """硬性拒绝把基准数据写进仓库 data/（同 benchmark_scale 的事故说明）。"""
    real = (APP_DIR / "data").resolve()
    for env_name in ("TODO_SQLITE_FILE", "TODO_MEMO_SQLITE_FILE", "TODO_SUMMARY_SQLITE_FILE"):
        path = Path(os.environ[env_name]).resolve()
        if path == real or real in path.parents:
            raise SystemExit(f"基准拒绝写入真实数据目录：{path}")


assert_temp_databases()

TODAY = "2026-09-16"
ROUNDS = 5
DEFAULT_TASKS = [10000, 223]
LOCK_WAIT_SECONDS = 30
NOTE = (
    "answerWaitedForSaveMs=保存先持锁时答题端到端耗时（含等写锁，答题真正要等保存多久）；"
    "saveWaitedForAnswerMs=答题先持锁时保存端到端耗时（含等写锁，保存要等答题多久）；"
    "fullSaveMs=两个并发顺序下保存耗时合并后的中位数；"
    "baselineSaveMs=同规模无并发保存耗时中位数。每档 5 轮取中位数，单位 ms。"
)


class SignalledLock:
    """包住 `storage` 的写锁：谁先真正持锁，就 set 一次 `entered`。

    基准靠这个信号确定"谁先"，不再靠 sleep 猜。只作上下文管理器用，其余属性委托给内层锁。
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self.entered = threading.Event()

    def reset(self) -> None:
        self.entered.clear()

    def __enter__(self):
        self._inner.acquire()
        self.entered.set()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._inner.release()
        return False

    def __getattr__(self, name):
        return getattr(self._inner, name)


def build_project(project_id: str, total: int) -> dict:
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
    return {"id": project_id, "name": f"规模基准 {total}", "description": "", "createdAt": TODAY,
            "assessmentEnabled": False, "tree": weeks}


def _run_save(project: dict, revision: int, samples: list[float], next_revision: list[int],
              failure: list[BaseException]) -> None:
    start = time.perf_counter()
    try:
        new_revision, _ = storage.write_project(project, revision)
        next_revision.append(new_revision)
    except BaseException as error:  # noqa: BLE001 - 线程里的异常必须带回主线程
        failure.append(error)
    finally:
        samples.append((time.perf_counter() - start) * 1000)


def _run_answer(code: str, answer: str, samples: list[float], failure: list[BaseException],
                done: threading.Event) -> None:
    start = time.perf_counter()
    try:
        review_storage.apply_grade(code, "concept", 3, today=TODAY, answer=answer)
    except BaseException as error:  # noqa: BLE001 - 线程里的异常必须带回主线程
        failure.append(error)
    finally:
        samples.append((time.perf_counter() - start) * 1000)
        done.set()


def measure_scale(tasks: int, code: str, gate: SignalledLock, rounds: int) -> dict:
    project = build_project(f"bench-{tasks}", tasks)
    revision, _ = storage.write_project(project, None)

    baseline: list[float] = []
    for _ in range(rounds):
        start = time.perf_counter()
        revision, _ = storage.write_project(project, revision)
        baseline.append((time.perf_counter() - start) * 1000)

    answer_waited: list[float] = []
    save_when_save_first: list[float] = []
    save_waited: list[float] = []
    for round_no in range(rounds):
        # 顺序 A：保存线程先持锁，主线程再发起答题 —— 答题要等保存。
        gate.reset()
        save_samples: list[float] = []
        next_revision: list[int] = []
        failure: list[BaseException] = []
        saver = threading.Thread(target=_run_save,
                                 args=(project, revision, save_samples, next_revision, failure))
        saver.start()
        if not gate.entered.wait(timeout=LOCK_WAIT_SECONDS):
            raise RuntimeError(f"保存线程 {LOCK_WAIT_SECONDS}s 内没拿到写锁")
        start = time.perf_counter()
        review_storage.apply_grade(code, "concept", 3, today=TODAY, answer=f"基准 {tasks} 保存先 {round_no}")
        answer_waited.append((time.perf_counter() - start) * 1000)
        saver.join(timeout=LOCK_WAIT_SECONDS)
        if saver.is_alive():
            raise RuntimeError("保存线程 30 秒内没结束：可能被写锁死等")
        if failure:
            raise failure[0]
        save_when_save_first.append(save_samples[0])
        revision = next_revision[0]

        # 顺序 B：答题线程先持锁，主线程再发起保存 —— 保存要等答题（反向对照）。
        gate.reset()
        answer_samples: list[float] = []
        failure = []
        done = threading.Event()
        answerer = threading.Thread(target=_run_answer,
                                    args=(code, f"基准 {tasks} 答题先 {round_no}",
                                          answer_samples, failure, done))
        answerer.start()
        if not gate.entered.wait(timeout=LOCK_WAIT_SECONDS):
            raise RuntimeError(f"答题线程 {LOCK_WAIT_SECONDS}s 内没拿到写锁")
        save_start = time.perf_counter()
        revision, _ = storage.write_project(project, revision)
        save_waited.append((time.perf_counter() - save_start) * 1000)
        done.wait(timeout=LOCK_WAIT_SECONDS)
        answerer.join(timeout=LOCK_WAIT_SECONDS)
        if failure:
            raise failure[0]
        if answerer.is_alive():
            raise RuntimeError("答题线程 30 秒内没结束：可能被写锁死等")

    median = statistics.median
    return {
        "tasks": tasks,
        "answerWaitedForSaveMs": round(median(answer_waited), 1),
        "saveWaitedForAnswerMs": round(median(save_waited), 1),
        "fullSaveMs": round(median(save_when_save_first + save_waited), 1),
        "baselineSaveMs": round(median(baseline), 1),
        "samples": {
            "answerWaitedForSaveMs": [round(value, 1) for value in answer_waited],
            "saveWhenSaveHeldFirstMs": [round(value, 1) for value in save_when_save_first],
            "saveWaitedForAnswerMs": [round(value, 1) for value in save_waited],
            "baselineSaveMs": [round(value, 1) for value in baseline],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="复习写锁基准（两口径 + 多规模）")
    parser.add_argument("--tasks", type=int, nargs="+", default=DEFAULT_TASKS,
                        help=f"节点数档位，默认 {DEFAULT_TASKS}")
    parser.add_argument("--rounds", type=int, default=ROUNDS, help=f"每档轮数，默认 {ROUNDS}")
    args = parser.parse_args()

    storage.ensure_schema()
    # 基准要答真实的题：先把内置内容导入临时库（真实库只读，不被碰）。
    review_storage.ensure_content_imported()
    code = review_storage.list_points()["points"][0]["code"]

    inner_lock = storage._database_lock
    gate = SignalledLock(inner_lock)
    storage._database_lock = gate
    try:
        runs = [measure_scale(tasks, code, gate, args.rounds) for tasks in args.tasks]
    finally:
        storage._database_lock = inner_lock

    print(json.dumps({"note": NOTE, "rounds": args.rounds, "runs": runs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
