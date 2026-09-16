import json
import tempfile
import unittest
from pathlib import Path

import review_content

GOOD_POINT = {
    "code": "py.mutability.default-arg",
    "title": "可变默认参数与求值时机",
    "minutes": 20,
    "module": "函数",
    "level": "基础",
    "taskRefs": [{"taskId": "1103", "relation": "introduces"}],
    "concept": {"prompt": "默认参数什么时候求值？", "answer": ["函数定义时求值一次", "可变对象会在调用间共享"]},
    "predict": {"prompt": "写出输出并解释",
                "code": "def add(item, items=[]):\n    items.append(item)\n    return items\nprint(add(1))\nprint(add(2))",
                "expected": ["[1]", "[1, 2]"], "explain": "第二次调用复用了定义时创建的同一个列表"},
    "debug": {"prompt": "找出 bug", "code": "def cache(k, store={}):\n    return store.setdefault(k, [])",
              "rootCause": "store 在函数定义时创建一次，被所有调用共享",
              "fix": "改成 store=None，函数体内 store = {} if store is None else store"},
    "code_task": {"prompt": "用 None 哨兵重写",
                  "acceptance": ["多次调用互不影响", "带一个 unittest 用例"],
                  "reference": "def add(item, items=None):\n    items = [] if items is None else items\n    items.append(item)\n    return items"},
    "pitfalls": ["默认值是可变对象", "把默认值当每次新建", "调用侧共享同一列表"],
}


class ReviewContentTests(unittest.TestCase):
    def test_validate_points_accepts_good_point(self) -> None:
        self.assertEqual(review_content.validate_points([GOOD_POINT]), [])

    def test_validate_points_reports_missing_predict_output(self) -> None:
        broken = json.loads(json.dumps(GOOD_POINT))
        broken["predict"]["expected"] = []
        errors = review_content.validate_points([broken])
        self.assertTrue(any("predict" in error for error in errors), errors)

    def test_validate_points_reports_bad_minutes_and_code(self) -> None:
        broken = json.loads(json.dumps(GOOD_POINT))
        broken["minutes"] = 90
        broken["code"] = "default-arg"
        errors = review_content.validate_points([broken])
        self.assertTrue(any("minutes" in error for error in errors), errors)
        self.assertTrue(any("code" in error for error in errors), errors)

    def test_validate_points_rejects_duplicate_code(self) -> None:
        errors = review_content.validate_points([GOOD_POINT, dict(GOOD_POINT)])
        self.assertTrue(any("重复" in error for error in errors), errors)

    def test_validate_points_rejects_unknown_relation(self) -> None:
        broken = json.loads(json.dumps(GOOD_POINT))
        broken["taskRefs"] = [{"taskId": "1103", "relation": "touches"}]
        errors = review_content.validate_points([broken])
        self.assertTrue(any("relation" in error for error in errors), errors)

    def test_normalize_points_fills_defaults_and_passes_the_gate(self) -> None:
        draft = {
            "code": "py.ai.1202.1",
            "title": "AI 补充点",
            "minutes": "15",
            "taskRefs": [{"taskId": "1202", "relation": "introduces"}],
            "concept": {"prompt": "解释机制", "answer": ["要点"]},
            "predict": {"prompt": "写出输出", "code": "print(1)", "expected": ["1"], "explain": "因为"},
            "debug": {"prompt": "找错", "code": "x =", "rootCause": "语法错误", "fix": "改成 x = 1"},
            "code_task": {"prompt": "写函数", "acceptance": ["能跑"], "reference": "def f(): return 1"},
            "pitfalls": ["边界输入"],
        }
        normalized = review_content.normalize_points([draft])
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["minutes"], 15)
        self.assertEqual(normalized[0]["module"], "AI 补充")
        self.assertEqual(normalized[0]["level"], "基础")
        self.assertEqual(normalized[0]["taskRefs"], [{"taskId": "1202", "projectId": "", "relation": "introduces"}])
        self.assertEqual(review_content.validate_points(normalized), [])

    def test_normalize_points_drops_illegal_items(self) -> None:
        normalized = review_content.normalize_points([
            "不是对象", None, 5, {}, {"code": "   "}, {"code": 123},
            {"code": "py.ai.1", "taskRefs": [{"relation": "introduces"},
                                             {"taskId": "1202", "relation": "unknown"},
                                             {"taskId": "   "}]},
            {"code": "py.ai.1", "title": "重复 code"},
        ])
        self.assertEqual([point["code"] for point in normalized], ["py.ai.1"])
        self.assertEqual(normalized[0]["taskRefs"], [])
        self.assertEqual(normalized[0]["title"], "py.ai.1")
        for bad in (None, "x", {}, 5):
            self.assertEqual(review_content.normalize_points(bad), [])

    def test_load_content_file_round_trip(self) -> None:
        payload = {"schemaVersion": 1, "week": 1, "level": "基础", "points": [GOOD_POINT]}
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "py-week1.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            loaded = review_content.load_content_file(path)
        self.assertEqual(loaded["week"], 1)
        self.assertEqual(len(loaded["points"]), 1)

    def test_load_content_file_rejects_bad_json(self) -> None:
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                review_content.load_content_file(path)

    def test_real_week1_file_is_valid(self) -> None:
        loaded = review_content.load_content_file(Path("content/review/py-week1.json"))
        self.assertEqual(review_content.validate_points(loaded["points"]), [])

    def test_real_week1_file_has_40_unique_points(self) -> None:
        loaded = review_content.load_content_file(Path("content/review/py-week1.json"))
        codes = [point["code"] for point in loaded["points"]]
        self.assertEqual(len(codes), 40)
        self.assertEqual(len(set(codes)), 40, "知识点 code 必须唯一")


if __name__ == "__main__":
    unittest.main()
