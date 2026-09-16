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
