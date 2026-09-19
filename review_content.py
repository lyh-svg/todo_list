"""课程库 JSON 的读取与校验（纯函数，不碰数据库）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

QUESTION_TYPES = ("concept", "predict", "debug", "code_task")
LEVELS = ("基础", "实用", "进阶")
RELATIONS = ("introduces", "exercises")
MIN_MINUTES = 5
MAX_MINUTES = 30
# AI 生成的知识点必须落在这个命名空间里：否则模型返回一个和内置 code 相同的值，
# `import_content` 会把它当成"更新"直接覆盖内置内容。
AI_CODE_PREFIX = "py.ai."


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (_text(entry) for entry in value) if item]


def validate_points(points: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(points, list):
        return ["points 必须是数组"]
    seen: set[str] = set()
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            errors.append(f"第 {index + 1} 个知识点：不是对象")
            continue
        code = _text(point.get("code"))
        where = f"知识点 {code or index + 1}"
        if not code:
            errors.append(f"{where}：缺少 code")
        elif not code.startswith("py.") or code.count(".") < 2:
            errors.append(f"{where}：code 应形如 py.<主题>.<点>")
        elif code in seen:
            errors.append(f"{where}：code 重复")
        seen.add(code)
        if not _text(point.get("title")):
            errors.append(f"{where}：缺少 title")
        try:
            minutes = int(point.get("minutes"))
        except (TypeError, ValueError):
            minutes = 0
        if not MIN_MINUTES <= minutes <= MAX_MINUTES:
            errors.append(f"{where}：minutes 必须在 {MIN_MINUTES}~{MAX_MINUTES} 之间")
        if _text(point.get("level")) not in LEVELS:
            errors.append(f"{where}：level 必须是 基础/实用/进阶 之一")
        for slot in QUESTION_TYPES:
            block = point.get(slot)
            if not isinstance(block, dict) or not _text(block.get("prompt")):
                errors.append(f"{where}：缺少 {slot} 题面")
                continue
            if slot == "concept" and not _text_list(block.get("answer")):
                errors.append(f"{where}：concept 缺少 answer 要点")
            if slot == "predict":
                if not _text(block.get("code")):
                    errors.append(f"{where}：predict 缺少 code")
                if not _text_list(block.get("expected")):
                    errors.append(f"{where}：predict 缺少 expected 输出")
                if not _text(block.get("explain")):
                    errors.append(f"{where}：predict 缺少 explain")
            if slot == "debug":
                if not _text(block.get("rootCause")):
                    errors.append(f"{where}：debug 缺少 rootCause")
                if not _text(block.get("fix")):
                    errors.append(f"{where}：debug 缺少 fix")
            if slot == "code_task":
                if not _text_list(block.get("acceptance")):
                    errors.append(f"{where}：code_task 缺少 acceptance 验收要点")
                if not _text(block.get("reference")):
                    errors.append(f"{where}：code_task 缺少 reference 参考实现")
        if not _text_list(point.get("pitfalls")):
            errors.append(f"{where}：缺少 pitfalls 易错点")
        refs = point.get("taskRefs")
        if not isinstance(refs, list):
            errors.append(f"{where}：taskRefs 必须是数组（可以为空）")
        else:
            for ref in refs:
                if not isinstance(ref, dict) or not _text(ref.get("taskId")):
                    errors.append(f"{where}：taskRefs 里缺少 taskId")
                elif _text(ref.get("relation")) not in RELATIONS:
                    errors.append(f"{where}：taskRefs 的 relation 只能是 introduces/exercises")
    return errors


def _int_or(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_refs(value: Any) -> list[dict[str, str]]:
    """taskRefs 的轻量清洗：relation 不在白名单或缺 taskId 的引用直接丢弃。"""
    if not isinstance(value, list):
        return []
    refs = []
    for ref in value:
        if not isinstance(ref, dict):
            continue
        task_id = _text(ref.get("taskId"))
        relation = _text(ref.get("relation"))
        if not task_id or relation not in RELATIONS:
            continue
        refs.append({"taskId": task_id, "projectId": _text(ref.get("projectId")), "relation": relation})
    return refs


def normalize_points(value: Any) -> list[dict[str, Any]]:
    """AI 返回内容的轻量清洗：补齐缺省字段、丢弃非法项（非对象、无 code、code 重复）。

    只接受 `AI_CODE_PREFIX`（`py.ai.`）命名空间里的 code：模型若返回内置 code，
    在这里就被丢掉，绝不会走到 `import_content` 去覆盖内置知识点。

    这里只是把模型输出整理成"形状正确"的草稿；内容是否合格仍由 `validate_points` 做最终闸门
    （`import_content` 会再校验一次，不合格的生成内容不会入库）。
    """
    if not isinstance(value, list):
        return []
    points = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        raw_code = item.get("code")
        code = raw_code.strip() if isinstance(raw_code, str) else ""
        if not code or not code.startswith(AI_CODE_PREFIX) or code in seen:
            continue
        seen.add(code)
        level = _text(item.get("level"))
        points.append({
            "code": code,
            "title": _text(item.get("title")) or code,
            "minutes": max(MIN_MINUTES, min(MAX_MINUTES, _int_or(item.get("minutes"), 15))),
            "module": _text(item.get("module")) or "AI 补充",
            "level": level if level in LEVELS else "基础",
            "taskRefs": _normalize_refs(item.get("taskRefs")),
            "concept": item.get("concept") if isinstance(item.get("concept"), dict) else {},
            "predict": item.get("predict") if isinstance(item.get("predict"), dict) else {},
            "debug": item.get("debug") if isinstance(item.get("debug"), dict) else {},
            "code_task": item.get("code_task") if isinstance(item.get("code_task"), dict) else {},
            "pitfalls": _text_list(item.get("pitfalls")),
        })
    return points


def normalize_ai_question(value: Any) -> dict[str, Any]:
    """清洗 AI 现场出的题：题面 + （作答后才有）参考解。

    与固定题的关系：`reference` 的键刻意与 `review_storage.reveal()` 返回的字段同名，
    收藏之后前端「看答案」面板不用改就能渲染。
    """
    source = value if isinstance(value, dict) else {}
    raw_reference = source.get("reference") if isinstance(source.get("reference"), dict) else {}
    return {
        "questionType": _text(source.get("questionType")),
        "prompt": _text(source.get("prompt"))[:4000],
        "code": _text(source.get("code"))[:4000],
        "focus": _text(source.get("focus"))[:300],
        "reference": {
            "answer": _text_list(raw_reference.get("answer"))[:12],
            "expected": _text_list(raw_reference.get("expected"))[:12],
            "explain": _text(raw_reference.get("explain"))[:2000],
            "rootCause": _text(raw_reference.get("rootCause"))[:2000],
            "fix": _text(raw_reference.get("fix"))[:2000],
            "reference": _text(raw_reference.get("reference"))[:4000],
            "pitfalls": _text_list(raw_reference.get("pitfalls"))[:12],
        },
    }


def validate_ai_question(question: Any, *, require_reference: bool = False) -> list[str]:
    """AI 题的闸门：题型必须是四种之一、题面必须有 prompt；收藏时参考解至少一项有内容。"""
    errors: list[str] = []
    if not isinstance(question, dict):
        return ["AI 题必须是对象"]
    if _text(question.get("questionType")) not in QUESTION_TYPES:
        errors.append("题型必须是 " + "/".join(QUESTION_TYPES) + " 之一")
    if not _text(question.get("prompt")):
        errors.append("缺少题面 prompt")
    if require_reference:
        reference = question.get("reference") if isinstance(question.get("reference"), dict) else {}
        filled = any(
            _text(reference.get(key)) or _text_list(reference.get(key))
            for key in ("reference", "answer", "expected", "explain")
        )
        if not filled:
            errors.append("参考解至少要有示范解/要点/期望输出/解释之一")
    return errors


def load_content_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"课程库文件不存在：{file_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"课程库文件不是合法 JSON：{file_path}（{error}）") from error
    if not isinstance(payload, dict):
        raise ValueError(f"课程库根节点必须是对象：{file_path}")
    points = payload.get("points")
    errors = validate_points(points)
    if errors:
        raise ValueError("课程库校验失败：" + "；".join(errors[:5]))
    return {
        "schemaVersion": int(payload.get("schemaVersion") or 1),
        "week": int(payload.get("week") or 0),
        "level": _text(payload.get("level")) or "基础",
        "points": points,
    }
