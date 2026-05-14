from __future__ import annotations

from pathlib import Path

from autograde_tool.exporter import export_markdown


def test_markdown_exports_sorted_by_student_id(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    results = [
        {"student_id": "22301020014", "name": "张三", "score": 100, "comment": "好", "success": True, "source_file": "a.py"},
        {"student_id": "21300270019", "name": "李四", "score": 90, "comment": "可", "success": True, "source_file": "b.py"},
    ]

    export_markdown(path, results, [], {"count": 2, "mean": 95, "max": 100, "min": 90})

    text = path.read_text(encoding="utf-8")
    assert text.index("21300270019") < text.index("22301020014")

