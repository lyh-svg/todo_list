"""复习内容导入、复习状态与调度、每日队列、作答记录。"""
from __future__ import annotations

import json
import re
import sys
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import review_content
import storage

CONTENT_DIR = Path(__file__).resolve().parent / "content" / "review"
WEEK1_PATH = CONTENT_DIR / "py-week1.json"
DEFAULT_ORIGIN = "builtin"
# 元任务（Task 13 约定的清单/复盘类任务）只做组织工作，不承载可复习的知识点。
META_TASK_IDS = {"1104", "1504"}
# 排序权重：先 `introduces`（这个任务引入了该知识点），再 `exercises`（这个任务练过它）。
INTRODUCE_WEIGHT = 0


def _now() -> str:
    return storage._now()


def _connection():
    return storage.open_state_database()


@contextmanager
def _shared_connection(connection=None):
    """复用调用方给的连接（一个请求只开一次库）；没给就自己开一个。"""
    if connection is not None:
        yield connection
    else:
        with _connection() as own:
            yield own


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def import_content(points: list[dict], *, week: int = 1, origin: str = DEFAULT_ORIGIN) -> dict[str, int]:
    """按 code 幂等导入知识点：只有内容变化才算 updated（内容相同则 unchanged），taskRefs 整体重建。

    `origin`/`week` 是来源元数据而非内容指纹：`week` 不落库，`origin` 只在首次插入时写入，
    重复导入不会覆盖已有行的 `origin`。
    """
    errors = review_content.validate_points(points)
    if errors:
        raise ValueError("内容校验失败：" + "；".join(errors[:5]))
    inserted = updated = unchanged = 0
    stamp = _now()
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for point in points:
            code = str(point["code"])
            payload = {
                "code": code, "title": str(point["title"]), "minutes": int(point["minutes"]),
                "module": str(point.get("module") or ""), "level": str(point.get("level") or "基础"),
                "concept": point["concept"], "predict": point["predict"], "debug": point["debug"],
                "code_task": point["code_task"], "pitfalls": point["pitfalls"],
            }
            content = _json(payload)
            row = connection.execute(
                "SELECT content_json FROM review_points WHERE code=?", (code,)).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO review_points(code,title,minutes,module,level,origin,content_json,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (code, payload["title"], payload["minutes"], payload["module"], payload["level"],
                     origin, content, stamp, stamp))
                connection.execute(
                    "INSERT OR IGNORE INTO review_states(code,due) VALUES(?,'')", (code,))
                inserted += 1
            elif row["content_json"] != content:
                connection.execute(
                    "UPDATE review_points SET title=?,minutes=?,module=?,level=?,content_json=?,updated_at=? "
                    "WHERE code=?",
                    (payload["title"], payload["minutes"], payload["module"], payload["level"],
                     content, stamp, code))
                updated += 1
            else:
                unchanged += 1
            connection.execute("DELETE FROM review_point_tasks WHERE code=?", (code,))
            for ref in point.get("taskRefs") or []:
                connection.execute(
                    "INSERT OR REPLACE INTO review_point_tasks(code,task_id,project_id,relation) VALUES(?,?,?,?)",
                    (code, str(ref["taskId"]), str(ref.get("projectId") or ""), str(ref["relation"])))
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged}


# `py-week<数字>.json`：排序键取文件名里的周编号，纯字典序会把 py-week10 排到 py-week2 前面。
WEEK_FILE_PATTERN = re.compile(r"py-week(\d+)\.json$")


def _week_sort_key(path: Path) -> tuple[int, str]:
    """周编号越小越靠前；文件名里没有数字的（理论上不该有）排到最后，再按文件名兜底。"""
    match = WEEK_FILE_PATTERN.search(path.name)
    return (int(match.group(1)) if match else sys.maxsize, path.name)


def content_paths() -> list[Path]:
    """随仓库发布的课程库文件：`content/review/py-week*.json`，按周编号（数字）排序。

    扫描根取 `WEEK1_PATH` 所在目录：测试把 `WEEK1_PATH` 指到临时目录即可隔离内容。
    用数字键而不是字典序：否则第 10 周会排在第 2 周前面，导入顺序与周次脱节。
    """
    return sorted(WEEK1_PATH.parent.glob("py-week*.json"), key=_week_sort_key)


def ensure_content_imported() -> int:
    """按周编号顺序逐个导入所有周课程库，返回本次 `inserted+updated` 的总和。

    幂等：内容未变的点只计入 `unchanged`，因此重复调用返回 0。
    单个文件缺失/损坏/校验失败时只打印告警并跳过它，其它周照常导入，绝不抛给启动路径。
    """
    total = 0
    for path in content_paths():
        try:
            loaded = review_content.load_content_file(path)
            result = import_content(loaded["points"], week=loaded["week"] or 1)
        except Exception as error:  # noqa: BLE001 - 单个坏文件不能拖垮其它周内容
            print(f"复习知识点导入跳过：{path}：{error}", file=sys.stderr)
            continue
        total += result["inserted"] + result["updated"]
    return total


def ensure_review_content_ready() -> int | None:
    """启动路径调用：按 code 幂等导入随仓库发布的多周课程库。

    返回本次导入/更新的条数：`0` 表示内容已是最新（或所有文件都被跳过），`>0` 表示本次写入的条数。
    一个课程库文件都没有时打印明确告警并返回 `None`；单个文件损坏只告警跳过，不阻断启动
    （复习库为空也能用），也不会把“内容缺失/损坏”谎报成“已是最新”。
    """
    if not content_paths():
        print(f"复习知识点导入失败：内容文件不存在：{WEEK1_PATH}", file=sys.stderr)
        return None
    try:
        return ensure_content_imported()
    except Exception as error:  # noqa: BLE001 - 内容文件坏损不能拖垮启动
        print(f"复习知识点导入失败：{error}", file=sys.stderr)
        return None


def points_for_task(task_id: str) -> list[dict[str, Any]]:
    """完成任务后要生成的复习项来源：先 introduces，再 exercises；元任务与未知任务返回空。

    返回值已带展示所需字段（title/minutes/module/level），并保留 relation/projectId
    供调用方判断来源与归属；`task_id` 为空或落在 `META_TASK_IDS` 时直接返回空。
    """
    task_key = str(task_id or "").strip()
    if not task_key or task_key in META_TASK_IDS:
        return []
    with _connection() as connection:
        rows = connection.execute(
            "SELECT p.code,p.title,p.minutes,p.module,p.level,t.relation,t.project_id "
            "FROM review_point_tasks t JOIN review_points p ON p.code=t.code "
            f"WHERE t.task_id=? ORDER BY CASE t.relation WHEN 'introduces' THEN {INTRODUCE_WEIGHT} ELSE 1 END, p.code",
            (task_key,)).fetchall()
    return [{"code": row["code"], "title": row["title"], "minutes": int(row["minutes"]),
             "module": row["module"], "level": row["level"], "relation": row["relation"],
             "projectId": row["project_id"] or ""} for row in rows]


def mark_weak(codes: list[str]) -> int:
    """把给定 code 的 `review_states.weak` 置 1、`lapses` 抬到薄弱阈值（不存在则忽略），返回影响行数。

    验收失败时用它把该任务关联的知识点推进薄弱点列表；不新建状态行——
    "知识点存在但还没学过"与"这个 code 根本不存在"都不该被凭空标弱。

    只置 `weak=1` 稳不住：下一次任意 grade 3 的复习会按 `lapses<2` 把 weak 归 False。
    因此同时把 `lapses` 抬到至少 `WEAK_LAPSES`，让它一直留在薄弱点列表，直到连续两次 ≥4
    的复习按既有规则同时把 weak 与 lapses 清零。
    """
    keys: list[str] = []
    seen: set[str] = set()
    for code in codes or []:
        text = str(code or "").strip()
        if text and text not in seen:
            seen.add(text)
            keys.append(text)
    if not keys:
        return 0
    placeholders = ",".join("?" for _ in keys)
    with storage.state_lock(), _connection() as connection:
        cursor = connection.execute(
            f"UPDATE review_states SET weak=1, lapses=MAX(lapses,{WEAK_LAPSES}) "
            f"WHERE code IN ({placeholders})", keys)
        return int(cursor.rowcount)


def list_points(*, module: str = "", level: str = "", query: str = "",
                limit: int = 200, offset: int = 0) -> dict[str, Any]:
    where, params = ["1=1"], []
    if module:
        where.append("p.module=?")
        params.append(module)
    if level:
        where.append("p.level=?")
        params.append(level)
    if query:
        where.append("(p.title LIKE ? OR p.code LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    clause = " AND ".join(where)
    limit = max(1, min(500, int(limit)))
    offset = max(0, int(offset))
    with _connection() as connection:
        total = int(connection.execute(
            f"SELECT COUNT(*) FROM review_points p WHERE {clause}", params).fetchone()[0])
        rows = connection.execute(
            f"SELECT p.code,p.title,p.minutes,p.module,p.level,p.origin,p.content_json,"
            f"COALESCE(s.due,'') AS due,COALESCE(s.weak,0) AS weak,COALESCE(s.last_grade,0) AS last_grade "
            f"FROM review_points p LEFT JOIN review_states s ON s.code=p.code "
            f"WHERE {clause} ORDER BY p.module,p.code LIMIT ? OFFSET ?",
            (*params, limit, offset)).fetchall()
    points = []
    for row in rows:
        content = json.loads(row["content_json"])
        points.append({
            "code": row["code"], "title": row["title"], "minutes": int(row["minutes"]),
            "module": row["module"], "level": row["level"], "origin": row["origin"],
            "due": row["due"], "weak": bool(row["weak"]), "lastGrade": int(row["last_grade"]),
            "pitfalls": content.get("pitfalls") or [],
        })
    return {"points": points, "total": total, "limit": limit, "offset": offset}


GRADE_BASE = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MAX_INTERVAL_4 = 60
MAX_INTERVAL_5 = 90
WEAK_LAPSES = 2


def _add_days(day: str, days: int) -> str:
    base = date.fromisoformat(day)
    return (base + timedelta(days=max(0, int(days)))).isoformat()


def next_schedule(grade: int, *, interval_days: int, streak: int, lapses: int,
                  today: str, answered_today: bool) -> dict[str, Any]:
    """五档自评 → 下次复习日。grade 1 当天可再来一次（当天已答过就顺延到明天）。

    `lapses` 由 `apply_grade` 维护：连续两次 grade ≥ 4 时会被归零并持久化，
    使薄弱点恢复后不会被历史失误重新标记。
    """
    grade = int(grade)
    if grade not in GRADE_BASE:
        raise ValueError("自评档位必须是 1~5")
    interval_days = max(0, int(interval_days or 0))
    streak = max(0, int(streak or 0))
    lapses = max(0, int(lapses or 0))
    if grade <= 2:
        interval = GRADE_BASE[grade]
        streak = 0
        lapses = lapses + 1 if grade == 1 else lapses
        due = today if (grade == 1 and not answered_today) else _add_days(today, interval)
        if grade == 1 and not answered_today:
            interval = 0
    else:
        streak += 1
        if grade == 3:
            interval = GRADE_BASE[3]
        elif grade == 4:
            interval = min(MAX_INTERVAL_4, max(GRADE_BASE[4], int(interval_days * 1.5)))
        else:
            interval = min(MAX_INTERVAL_5, max(GRADE_BASE[5], interval_days * 2 if interval_days >= 14 else 30))
        due = _add_days(today, interval)
    weak = bool(lapses >= WEAK_LAPSES)
    return {"due": due, "intervalDays": interval, "streak": streak, "lapses": lapses,
            "weak": weak, "lastGrade": grade}


def read_state(code: str) -> dict[str, Any] | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT code,due,interval_days,streak,lapses,last_grade,weak,last_reviewed_at "
            "FROM review_states WHERE code=?", (str(code),)).fetchone()
    if row is None:
        return None
    return {"code": row["code"], "due": row["due"], "intervalDays": int(row["interval_days"]),
            "streak": int(row["streak"]), "lapses": int(row["lapses"]),
            "lastGrade": int(row["last_grade"]), "weak": bool(row["weak"]),
            "lastReviewedAt": row["last_reviewed_at"]}


def _recent_grades(connection, code: str, limit: int = 3) -> list[int]:
    rows = connection.execute(
        "SELECT grade FROM review_attempts WHERE code=? ORDER BY created_at DESC LIMIT ?",
        (code, limit)).fetchall()
    return [int(row["grade"]) for row in rows]


def apply_grade(code: str, question_type: str, grade: int, *, today: str,
                answer: str = "", duration_ms: int = 0, session_id: str = "",
                task_id: str = "", project_id: str = "", ai_verdict: str = "",
                question_ref: str = "") -> dict[str, Any]:
    """记录一次作答并按五档更新调度；返回下次复习安排。

    `question_ref` 为空表示固定题；非空时是收藏的 AI 题 id（不校验存在性：
    题可能已被删，历史作答仍要留）。
    """
    code = str(code or "").strip()
    if not code:
        raise ValueError("缺少知识点 code")
    if int(grade) not in GRADE_BASE:
        raise ValueError("自评档位必须是 1~5")
    if question_type not in review_content.QUESTION_TYPES:
        raise ValueError("题型不正确")
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT due,interval_days,streak,lapses,weak FROM review_states WHERE code=?", (code,)).fetchone()
        if row is None:
            raise ValueError("知识点不存在")
        answered_today = bool(connection.execute(
            "SELECT 1 FROM review_attempts WHERE code=? AND reviewed_on=? LIMIT 1",
            (code, today)).fetchone())
        schedule = next_schedule(int(grade), interval_days=int(row["interval_days"]),
                                 streak=int(row["streak"]), lapses=int(row["lapses"]),
                                 today=today, answered_today=answered_today)
        connection.execute(
            "INSERT INTO review_attempts(id,code,task_id,project_id,question_type,question_ref,grade,answer,"
            "ai_verdict,reviewed_on,duration_ms,session_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), code, str(task_id or ""), str(project_id or ""), question_type,
             str(question_ref or ""), int(grade), str(answer or ""), str(ai_verdict or ""), today,
             max(0, int(duration_ms or 0)), str(session_id or ""), _now()))
        grades = _recent_grades(connection, code, 3)
        weak = schedule["weak"]
        lapses = schedule["lapses"]
        if len([value for value in grades if value <= 2]) >= 2:
            weak = True
        elif len(grades) >= 2 and all(value >= 4 for value in grades[:2]):
            weak = False
            lapses = 0
        connection.execute(
            "UPDATE review_states SET due=?,interval_days=?,streak=?,lapses=?,last_grade=?,weak=?,"
            "last_reviewed_at=? WHERE code=?",
            (schedule["due"], schedule["intervalDays"], schedule["streak"], lapses,
             int(grade), 1 if weak else 0, _now(), code))
        schedule["weak"] = bool(weak)
        schedule["lapses"] = lapses
    return schedule


def pick_questions(connection, codes: list[str], forced_type: str = "") -> dict[str, dict[str, str]]:
    """批量挑题：两段式。

    ① 选题型：仍是"这个知识点最近最少用过的题型"（从未用过优先，并列按声明顺序）——
       没有收藏 AI 题时结果与旧版逐字节一致；
    ② 选题：在该题型的候选（固定题 `''` + 该题型下已收藏的 AI 题）里挑最近最少用过的一道；
       都没用过时固定题优先，其次 question_id 升序 → 结果确定、可复现。
    """
    wanted = [str(code) for code in codes]
    if not wanted:
        return {}
    variants: dict[tuple[str, str], list[str]] = {}
    for start in range(0, len(wanted), storage.SQL_PARAM_CHUNK):
        chunk = wanted[start:start + storage.SQL_PARAM_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        for row in connection.execute(
                "SELECT question_id,code,question_type FROM review_ai_questions "
                f"WHERE code IN ({placeholders}) ORDER BY created_at,question_id", chunk):
            variants.setdefault((str(row["code"]), str(row["question_type"])), []).append(
                str(row["question_id"]))
    last_used: dict[tuple[str, str, str], str] = {}
    type_last: dict[tuple[str, str], str] = {}
    # 指定题型且一道 AI 候选都没有时，题型内只剩固定题，"最近用没用过"影响不了结果：
    # 这条轮换查询可以直接跳过（与旧行为一致：指定题型不查 review_attempts）。
    if variants or not forced_type:
        for start in range(0, len(wanted), storage.SQL_PARAM_CHUNK):
            chunk = wanted[start:start + storage.SQL_PARAM_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            for row in connection.execute(
                    "SELECT code,question_type,question_ref,MAX(created_at) AS last_at FROM review_attempts "
                    f"WHERE code IN ({placeholders}) GROUP BY code,question_type,question_ref", chunk):
                code = str(row["code"])
                kind = str(row["question_type"])
                ref = str(row["question_ref"] or "")
                last_at = str(row["last_at"])
                last_used[(code, kind, ref)] = last_at
                if last_at > type_last.get((code, kind), ""):
                    type_last[(code, kind)] = last_at
    kinds = review_content.QUESTION_TYPES
    picked: dict[str, dict[str, str]] = {}
    for code in wanted:
        kind = forced_type or min(
            kinds, key=lambda candidate: (type_last.get((code, candidate), ""), kinds.index(candidate)))
        candidates = [""] + variants.get((code, kind), [])
        question_ref = min(
            candidates,
            key=lambda ref: (last_used.get((code, kind, ref), ""), 0 if ref == "" else 1, ref))
        picked[code] = {"questionType": kind, "questionRef": question_ref}
    return picked


def pick_question_type(code: str, today: str) -> str:
    """题型轮换：优先选这个知识点最近最少用过的题型（都没用过就按 QUESTION_TYPES 声明顺序）。

    单点入口（测试/外部调用）保留；队列构建走 `pick_questions()` 的批量版。
    """
    with _connection() as connection:
        picked = pick_questions(connection, [str(code)]).get(str(code), {})
    return picked.get("questionType", review_content.QUESTION_TYPES[0])

def build_queue(today: str, limit: int = 10, *, code: str = "", module: str = "", level: str = "",
                project_id: str = "", task_id: str = "", question_type: str = "",
                new_per_day: int = 2) -> dict[str, Any]:
    """每日队列：逾期 → 今日 → 薄弱 → 新知识点（限量）→ 即将到期。上限硬约束，绝不一次全塞。

    `total` 是本次实际返回的条数（等于 `len(items)`，已被 `limit` 截断）。
    `truncated` 只表示"候选超过 limit 被截断"，**不**包含 `new_per_day` 主动丢弃的新知识点：
    `new_per_day` 是每日配额而非截断，配额丢弃不会让 `truncated` 变成 True。
    `question_type` 显式传入时必须是 `review_content.QUESTION_TYPES` 之一，否则抛 `ValueError("题型不正确")`。
    """
    limit = max(1, min(50, int(limit or 10)))
    new_per_day = max(0, min(5, int(new_per_day or 0)))
    if question_type and question_type not in review_content.QUESTION_TYPES:
        raise ValueError("题型不正确")
    where, params = ["1=1"], []
    if code:
        where.append("p.code=?")
        params.append(str(code))
    if module:
        where.append("p.module=?")
        params.append(module)
    if level:
        where.append("p.level=?")
        params.append(level)
    if task_id:
        where.append("EXISTS (SELECT 1 FROM review_point_tasks t WHERE t.code=p.code AND t.task_id=?)")
        params.append(str(task_id))
    if project_id:
        where.append("EXISTS (SELECT 1 FROM review_point_tasks t WHERE t.code=p.code AND t.project_id=?)")
        params.append(str(project_id))
    clause = " AND ".join(where)
    with _connection() as connection:
        rows = connection.execute(
            f"SELECT p.code,p.title,p.minutes,p.module,p.level,COALESCE(s.due,'') AS due,"
            f"COALESCE(s.weak,0) AS weak,COALESCE(s.interval_days,0) AS interval_days,"
            f"(SELECT task_id FROM review_point_tasks t WHERE t.code=p.code "
            f"ORDER BY relation, task_id LIMIT 1) AS task_id,"
            f"(SELECT project_id FROM review_point_tasks t WHERE t.code=p.code "
            f"ORDER BY relation, task_id LIMIT 1) AS project_id "
            f"FROM review_points p LEFT JOIN review_states s ON s.code=p.code WHERE {clause}",
            params).fetchall()
        buckets: dict[str, list[dict]] = {"overdue": [], "today": [], "weak": [], "new": [], "upcoming": []}
        for row in rows:
            due = str(row["due"] or "")
            item = {"code": row["code"], "title": row["title"], "minutes": int(row["minutes"]),
                    "module": row["module"], "level": row["level"], "due": due,
                    "taskId": row["task_id"] or "", "projectId": row["project_id"] or ""}
            if not due:
                buckets["new"].append(dict(item, reason="new"))
            elif due < today:
                buckets["overdue"].append(dict(item, reason="overdue"))
            elif due == today:
                buckets["today"].append(dict(item, reason="today"))
            elif row["weak"]:
                buckets["weak"].append(dict(item, reason="weak"))
            else:
                buckets["upcoming"].append(dict(item, reason="upcoming"))
        buckets["overdue"].sort(key=lambda entry: (entry["due"], entry["code"]))
        buckets["today"].sort(key=lambda entry: (entry["due"], entry["code"]))
        buckets["weak"].sort(key=lambda entry: (entry["due"], entry["code"]))
        buckets["upcoming"].sort(key=lambda entry: (entry["due"], entry["code"]))
        buckets["new"].sort(key=lambda entry: entry["code"])
        ordered = (buckets["overdue"] + buckets["today"] + buckets["weak"]
                   + buckets["new"][:new_per_day] + buckets["upcoming"])
        truncated = len(ordered) > limit
        chosen = ordered[:limit]
        # 题型与题面一次查完：以前每个条目 3 次查询（题型轮换还各自开一次库），
        # limit=50 时实测 51 次开库 / 406 条 SQL / 26.8 ms。
        chosen_codes = [str(item["code"]) for item in chosen]
        picked = pick_questions(connection, chosen_codes, forced_type=question_type)
        content_by_code: dict[str, Any] = {}
        for start in range(0, len(chosen_codes), storage.SQL_PARAM_CHUNK):
            chunk = chosen_codes[start:start + storage.SQL_PARAM_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            for row in connection.execute(
                    f"SELECT code,content_json FROM review_points WHERE code IN ({placeholders})", chunk):
                content_by_code[str(row["code"])] = json.loads(row["content_json"])
        ai_content: dict[str, Any] = {}
        ai_refs = sorted({plan["questionRef"] for plan in picked.values() if plan["questionRef"]})
        for start in range(0, len(ai_refs), storage.SQL_PARAM_CHUNK):
            chunk = ai_refs[start:start + storage.SQL_PARAM_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            for row in connection.execute(
                    f"SELECT question_id,content_json FROM review_ai_questions "
                    f"WHERE question_id IN ({placeholders})", chunk):
                ai_content[str(row["question_id"])] = json.loads(row["content_json"])
        for item in chosen:
            plan = picked.get(str(item["code"]), {})
            kind = plan.get("questionType", review_content.QUESTION_TYPES[0])
            question_ref = plan.get("questionRef", "")
            item["questionType"] = kind
            item["questionRef"] = question_ref
            # prompt 与 body（predict/debug 要预测或排查的代码片段）都是**题面**的一部分：
            # 用户必须看到才能作答；expected/explain/rootCause/fix 等参考答案只在 reveal() 里给。
            if question_ref:
                block = ai_content.get(question_ref) or {}
            else:
                block = (content_by_code.get(str(item["code"])) or {}).get(kind) or {}
            item["prompt"] = str(block.get("prompt") or "")
            item["body"] = str(block.get("code") or "")
    return {"items": chosen, "total": len(chosen), "truncated": truncated, "limit": limit}


def start_session(planned: int) -> str:
    session_id = str(uuid.uuid4())
    with storage.state_lock(), _connection() as connection:
        connection.execute(
            "INSERT INTO review_sessions(id,started_at,planned) VALUES(?,?,?)",
            (session_id, _now(), max(0, int(planned or 0))))
    return session_id


REVIEW_DAILY_LIMIT_RANGE = (5, 15)
REVIEW_NEW_PER_DAY_RANGE = (0, 5)


def _settings(connection=None) -> dict[str, Any]:
    """复习相关的应用设置（内部契约，供 HTTP 层复用）：只有缺失才用默认值，显式 0 表示"关闭每日新知识点"。

    仅当键缺失（`None`）时才回落默认值（`reviewDailyLimit`=10、`reviewNewPerDay`=2）；
    显式 `reviewNewPerDay=0`（或 `"0"`）是合法设置，表示关闭每日新知识点，不会退化成默认 2；
    非数字等损坏值同样回落默认值，最后夹到合法区间。
    Task 9 之前 `read_app_settings()` 还没有 `reviewDailyLimit`/`reviewNewPerDay` 两个键，
    此时两个键都缺失，因此本任务返回 `{"limit": 10, "newPerDay": 2}`。
    """
    settings = storage.read_app_settings(connection) or {}
    raw_limit = settings.get("reviewDailyLimit")
    raw_new = settings.get("reviewNewPerDay")
    try:
        limit = 10 if raw_limit is None else int(raw_limit)
    except (TypeError, ValueError):
        limit = 10
    try:
        new_per_day = 2 if raw_new is None else int(raw_new)
    except (TypeError, ValueError):
        new_per_day = 2
    return {"limit": max(REVIEW_DAILY_LIMIT_RANGE[0], min(REVIEW_DAILY_LIMIT_RANGE[1], limit)),
            "newPerDay": max(REVIEW_NEW_PER_DAY_RANGE[0], min(REVIEW_NEW_PER_DAY_RANGE[1], new_per_day))}


def streak_days(today: str, connection=None) -> int:
    """连续复习天数：从 `today` 往回数连续的 `reviewed_on` 日期，遇到第一个断链停止。

    `today` 当天没有作答时返回 0（不把"昨天及以前"当作未断的连续段）。
    """
    with _shared_connection(connection) as connection:
        rows = connection.execute(
            "SELECT DISTINCT reviewed_on FROM review_attempts ORDER BY reviewed_on DESC LIMIT 400").fetchall()
    days = [str(row["reviewed_on"]) for row in rows]
    streak = 0
    cursor = date.fromisoformat(today)
    for day in days:
        if day == cursor.isoformat():
            streak += 1
            cursor = cursor - timedelta(days=1)
        elif day < cursor.isoformat():
            break
    return streak


def summary(today: str) -> dict[str, Any]:
    """复习页顶部统计：`due` 非空视为已学（learned），按 overdue/dueToday/upcoming 分桶。"""
    # 以前这里一条请求开 5 次连接（settings / 主查询 / streak / 两次 recent_attempts），
    # 每次都重放一遍 DDL；现在整段统计共用同一个连接。
    with _connection() as connection:
        settings = _settings(connection)
        total = int(connection.execute("SELECT COUNT(*) FROM review_points").fetchone()[0])
        rows = connection.execute(
            "SELECT COALESCE(s.due,'') AS due, COALESCE(s.weak,0) AS weak FROM review_points p "
            "LEFT JOIN review_states s ON s.code=p.code").fetchall()
        answered_today = int(connection.execute(
            "SELECT COUNT(*) FROM review_attempts WHERE reviewed_on=?", (today,)).fetchone()[0])
        streak = streak_days(today, connection)
        recent_wrong = recent_attempts("wrong", today, connection=connection)
        recent_mastered = recent_attempts("mastered", today, connection=connection)
    due_today = overdue = upcoming = weak = learned = 0
    for row in rows:
        due = str(row["due"] or "")
        if row["weak"]:
            weak += 1
        if not due:
            continue
        learned += 1
        if due < today:
            overdue += 1
        elif due == today:
            due_today += 1
        else:
            upcoming += 1
    # 最近答错/最近掌握是真实的作答记录（复用 recent_attempts），不是 points.lastGrade：
    # 前者能给出"哪一次作答、写了什么、什么题型"，后者只是知识点的最新档位。
    return {"dueToday": due_today, "overdue": overdue, "upcoming": upcoming, "weak": weak,
            "total": total, "learned": learned, "answeredToday": answered_today,
            "streakDays": streak, "recentWrong": recent_wrong, "recentMastered": recent_mastered,
            **settings}


def recent_attempts(kind: str, today: str, limit: int = 10, connection=None) -> list[dict[str, Any]]:
    """最近答错（grade<=2）/ 已掌握（grade>=4）的作答记录，按作答时间倒序。

    `kind` 只区分 `wrong` 与其他值（其他值即 `mastered` 语义）；`today` 由调用方传入以便测试固定时钟。
    """
    condition = "grade<=2" if kind == "wrong" else "grade>=4"
    with _shared_connection(connection) as connection:
        rows = connection.execute(
            f"SELECT a.id,a.code,a.question_type,a.grade,a.answer,a.reviewed_on,p.title,p.module "
            f"FROM review_attempts a LEFT JOIN review_points p ON p.code=a.code "
            f"WHERE {condition} ORDER BY a.created_at DESC LIMIT ?", (max(1, min(50, int(limit))),)).fetchall()
    return [{"id": row["id"], "code": row["code"], "title": row["title"] or row["code"],
             "module": row["module"] or "", "questionType": row["question_type"], "grade": int(row["grade"]),
             "answer": row["answer"], "reviewedOn": row["reviewed_on"]} for row in rows]


def _history_detail(code: str, limit: int = 20) -> tuple[dict[str, Any], dict[str, Any]]:
    """一次查询返回 (内容 JSON, 历史详情)，供 history/reveal 复用同一份解析结果。"""
    with _connection() as connection:
        point = connection.execute(
            "SELECT title,content_json,module,level,minutes FROM review_points WHERE code=?",
            (str(code),)).fetchone()
        if point is None:
            raise ValueError("知识点不存在")
        rows = connection.execute(
            "SELECT question_type,grade,answer,ai_verdict,reviewed_on,duration_ms FROM review_attempts "
            "WHERE code=? ORDER BY created_at DESC LIMIT ?", (str(code), max(1, min(100, int(limit))))).fetchall()
    content = json.loads(point["content_json"])
    detail = {"code": str(code), "title": point["title"], "module": point["module"],
              "level": point["level"], "minutes": int(point["minutes"]),
              "pitfalls": content.get("pitfalls") or [],
              "attempts": [{"questionType": row["question_type"], "grade": int(row["grade"]),
                            "answer": row["answer"], "aiVerdict": row["ai_verdict"],
                            "reviewedOn": row["reviewed_on"], "durationMs": int(row["duration_ms"])}
                           for row in rows],
              "state": read_state(str(code))}
    return content, detail


def history(code: str, limit: int = 20) -> dict[str, Any]:
    """单个知识点的详情：内容元数据 + 易错点 + 最近作答 + 当前调度状态；code 不存在抛 ValueError。"""
    return _history_detail(code, limit)[1]


def reveal(code: str, question_type: str, question_ref: str = "") -> dict[str, Any]:
    """揭示答案：这是唯一会返回参考答案/历史答案的入口。

    题型自带字段（含 predict/debug 要预测或排查的 `code` 题面片段）原样保留；
    知识点 code 改用 `pointCode` 单独暴露，避免覆盖题面片段。
    `question_ref` 非空时给的是收藏的 AI 题自己的参考解；题已删/不匹配则回退固定题并标记。
    """
    if question_type not in review_content.QUESTION_TYPES:
        raise ValueError("题型不正确")
    ref = str(question_ref or "")
    if ref:
        stored = read_ai_question(ref)
        if stored and stored["pointCode"] == str(code) and stored["questionType"] == question_type:
            content, detail = _history_detail(str(code), 20)
            block = dict(stored.get("reference") or {})
            block.update({"code": str(stored.get("code") or ""), "pointCode": str(code),
                          "type": question_type, "title": detail["title"],
                          "pitfalls": detail["pitfalls"], "history": detail["attempts"],
                          "state": detail["state"], "questionRef": ref, "source": "ai",
                          "prompt": str(stored.get("prompt") or ""),
                          "focus": str(stored.get("focus") or "")})
            return block
        fallback = reveal(str(code), question_type)
        fallback["questionRefFallback"] = True
        return fallback
    content, detail = _history_detail(str(code), 20)
    block = dict(content.get(question_type) or {})
    block.update({"pointCode": str(code), "type": question_type, "title": detail["title"],
                  "pitfalls": detail["pitfalls"], "history": detail["attempts"],
                  "state": detail["state"], "questionRef": ""})
    return block


# ---------- AI 现场出题（临时加练 + 收藏库） ----------

AI_QUESTION_HISTORY_LIMIT = 5


def ai_question_context(code: str) -> dict[str, Any]:
    """出题上下文：知识点内容（含四种题型的"题面"，**不含答案**）+ 最近 5 条作答 + 薄弱标记。"""
    with _connection() as connection:
        point = connection.execute(
            "SELECT title,content_json,module,level,minutes FROM review_points WHERE code=?",
            (str(code),)).fetchone()
        if point is None:
            raise ValueError("知识点不存在")
        rows = connection.execute(
            "SELECT question_type,grade,answer,reviewed_on FROM review_attempts "
            "WHERE code=? ORDER BY created_at DESC LIMIT ?",
            (str(code), AI_QUESTION_HISTORY_LIMIT)).fetchall()
        state = connection.execute(
            "SELECT due,weak FROM review_states WHERE code=?", (str(code),)).fetchone()
    content = json.loads(point["content_json"])
    prompts = {
        kind: str((content.get(kind) or {}).get("prompt") or "").strip()
        for kind in review_content.QUESTION_TYPES
    }
    return {
        "code": str(code), "title": point["title"], "module": point["module"],
        "level": point["level"], "minutes": int(point["minutes"]),
        "pitfalls": [str(item) for item in (content.get("pitfalls") or [])],
        "existingPrompts": prompts,
        "weak": bool(state["weak"]) if state else False,
        "due": str(state["due"]) if state else "",
        "history": [{"questionType": str(row["question_type"]), "grade": int(row["grade"]),
                     "answer": str(row["answer"])[:200], "reviewedOn": str(row["reviewed_on"])}
                    for row in rows],
    }


def collect_ai_question(code: str, question_type: str, prompt: str, question_code: str = "",
                        focus: str = "", reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """把 AI 现场出的题收进题库：校验 → 规范化 → 落库（完全相同的题复用已有行，防连点重复）。"""
    question = review_content.normalize_ai_question({
        "questionType": question_type, "prompt": prompt, "code": question_code,
        "focus": focus, "reference": reference or {},
    })
    errors = review_content.validate_ai_question(question, require_reference=True)
    if errors:
        raise ValueError("AI 题不合法：" + "；".join(errors[:3]))
    payload = _json(question)
    stamp = _now()
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM review_points WHERE code=?", (str(code),)).fetchone() is None:
            raise ValueError("知识点不存在")
        existing = connection.execute(
            "SELECT question_id,created_at FROM review_ai_questions WHERE code=? AND content_json=?",
            (str(code), payload)).fetchone()
        if existing is not None:
            return {"id": str(existing["question_id"]), "code": str(code),
                    "questionType": question["questionType"],
                    "createdAt": str(existing["created_at"]), "duplicated": True}
        question_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO review_ai_questions(question_id,code,question_type,content_json,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (question_id, str(code), question["questionType"], payload, stamp, stamp))
    return {"id": question_id, "code": str(code), "questionType": question["questionType"],
            "createdAt": stamp, "duplicated": False}


def list_ai_questions(code: str | None = None) -> list[dict[str, Any]]:
    """已收藏的 AI 题：只给题面与考察点，参考答案走 reveal（列表绝不吐 reference）。"""
    sql = ("SELECT question_id,code,question_type,content_json,created_at "
           "FROM review_ai_questions")
    params: tuple[Any, ...] = ()
    if code:
        sql += " WHERE code=?"
        params = (str(code),)
    sql += " ORDER BY created_at,question_id"
    items: list[dict[str, Any]] = []
    with _connection() as connection:
        for row in connection.execute(sql, params):
            content = json.loads(row["content_json"])
            items.append({"id": str(row["question_id"]), "code": str(row["code"]),
                          "questionType": str(row["question_type"]),
                          "prompt": str(content.get("prompt") or ""),
                          "questionCode": str(content.get("code") or ""),
                          "focus": str(content.get("focus") or ""),
                          "createdAt": str(row["created_at"])})
    return items


def read_ai_question(question_id: Any) -> dict[str, Any] | None:
    """读一道收藏题的完整内容（含 reference）；不存在返回 None。

    列里的 `code` 是**知识点** code，content 里的 `code` 是**题面代码**：两者不能同名，
    所以知识点改用 `pointCode` 返回，否则题面片段会被覆盖掉。
    """
    with _connection() as connection:
        row = connection.execute(
            "SELECT question_id,code,question_type,content_json,created_at "
            "FROM review_ai_questions WHERE question_id=?", (str(question_id),)).fetchone()
    if row is None:
        return None
    content = json.loads(row["content_json"])
    return {"id": str(row["question_id"]), "pointCode": str(row["code"]),
            "questionType": str(row["question_type"]), "createdAt": str(row["created_at"]),
            **content}


def delete_ai_question(question_id: Any) -> dict[str, Any]:
    """删除一道收藏题，返回 {code, items}（该点删除后的剩余列表）；未知 id 抛 ValueError。"""
    with storage.state_lock(), _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT code FROM review_ai_questions WHERE question_id=?",
                                 (str(question_id),)).fetchone()
        if row is None:
            raise ValueError("AI 题不存在")
        code = str(row["code"])
        connection.execute("DELETE FROM review_ai_questions WHERE question_id=?",
                           (str(question_id),))
    return {"code": code, "items": list_ai_questions(code)}


def finish_session(session_id: str, *, answered: int, grade_counts: dict[int, int],
                   duration_ms: int) -> int:
    """标记会话结束并返回受影响行数：0 表示 sessionId 不存在，调用方应据此报错。"""
    with storage.state_lock(), _connection() as connection:
        cursor = connection.execute(
            "UPDATE review_sessions SET finished_at=?,answered=?,grade_counts_json=?,duration_ms=? WHERE id=?",
            (_now(), max(0, int(answered or 0)), _json({str(k): int(v) for k, v in (grade_counts or {}).items()}),
             max(0, int(duration_ms or 0)), str(session_id)))
        return int(cursor.rowcount)
