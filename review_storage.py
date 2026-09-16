"""复习内容导入、复习状态与调度、每日队列、作答记录。"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import review_content
import storage

WEEK1_PATH = Path(__file__).resolve().parent / "content" / "review" / "py-week1.json"
DEFAULT_ORIGIN = "builtin"


def _now() -> str:
    return storage._now()


def _connection():
    return storage.open_state_database()


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


def ensure_content_imported() -> int:
    if not WEEK1_PATH.exists():
        return 0
    loaded = review_content.load_content_file(WEEK1_PATH)
    result = import_content(loaded["points"], week=loaded["week"] or 1)
    return result["inserted"] + result["updated"]


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
    """五档自评 → 下次复习日。grade 1 当天可再来一次（当天已答过就顺延到明天）。"""
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
            interval = min(MAX_INTERVAL_4, max(GRADE_BASE[4], interval_days * 2 if interval_days >= 7 else 14))
        else:
            interval = min(MAX_INTERVAL_5, max(GRADE_BASE[5], interval_days * 2 if interval_days >= 14 else 30))
        due = _add_days(today, interval)
    weak = bool(lapses >= WEAK_LAPSES) if grade <= 2 else bool(lapses >= WEAK_LAPSES)
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
                task_id: str = "", project_id: str = "", ai_verdict: str = "") -> dict[str, Any]:
    """记录一次作答并按五档更新调度；返回下次复习安排。"""
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
            "INSERT INTO review_attempts(id,code,task_id,project_id,question_type,grade,answer,"
            "ai_verdict,reviewed_on,duration_ms,session_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), code, str(task_id or ""), str(project_id or ""), question_type,
             int(grade), str(answer or ""), str(ai_verdict or ""), today,
             max(0, int(duration_ms or 0)), str(session_id or ""), _now()))
        grades = _recent_grades(connection, code, 3)
        weak = schedule["weak"]
        if len([value for value in grades if value <= 2]) >= 2:
            weak = True
        elif len(grades) >= 2 and all(value >= 4 for value in grades[:2]):
            weak = False
        connection.execute(
            "UPDATE review_states SET due=?,interval_days=?,streak=?,lapses=?,last_grade=?,weak=?,"
            "last_reviewed_at=? WHERE code=?",
            (schedule["due"], schedule["intervalDays"], schedule["streak"], schedule["lapses"],
             int(grade), 1 if weak else 0, _now(), code))
        schedule["weak"] = bool(weak)
    return schedule
