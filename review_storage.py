"""复习内容导入、复习状态与调度、每日队列、作答记录。"""
from __future__ import annotations

import json
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
    """按 code 幂等导入知识点（内容相同则跳过，变化则更新，taskRefs 整体重建）。"""
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
                "origin": origin, "week": week,
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
                    "UPDATE review_points SET title=?,minutes=?,module=?,level=?,origin=?,content_json=?,updated_at=? "
                    "WHERE code=?",
                    (payload["title"], payload["minutes"], payload["module"], payload["level"],
                     origin, content, stamp, code))
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
