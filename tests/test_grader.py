from __future__ import annotations

from autograde_tool.deepseek_grader import parse_grading_json


def test_parse_grading_json_normalizes_fields() -> None:
    result = parse_grading_json('{"score": 101, "comment": "好", "issues": "无", "strengths": ["完整"], "confidence": "HIGH"}')
    assert result["score"] == 100
    assert result["issues"] == ["无"]
    assert result["strengths"] == ["完整"]
    assert result["confidence"] == "high"
    assert result["success"] is True


def test_parse_grading_json_accepts_fenced_json() -> None:
    result = parse_grading_json('```json\n{"score": 96, "comment": "清晰"}\n```')
    assert result["score"] == 96
    assert result["comment"] == "清晰"

