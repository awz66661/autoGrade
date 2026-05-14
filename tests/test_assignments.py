from __future__ import annotations

import json
from pathlib import Path

from autograde_tool.assignments import (
    choose_latest_submissions,
    discover_assignments,
    load_assignment,
    notebook_to_python,
    parse_submission_filename,
)


def make_assignment(root: Path, key: str = "hw_1") -> Path:
    hw = root / key
    (hw / "answer").mkdir(parents=True)
    (hw / "submissions").mkdir()
    (hw / "answer" / "project1.py").write_text("print('answer')\n", encoding="utf-8")
    return hw


def test_discover_assignments(tmp_path: Path) -> None:
    make_assignment(tmp_path, "hw_1")
    assignments = discover_assignments(tmp_path)
    assert [item.key for item in assignments] == ["hw_1"]
    assert assignments[0].answer_file.name == "project1.py"


def test_parse_submission_filename_with_chinese_name_and_spaces(tmp_path: Path) -> None:
    path = tmp_path / "22301020014_200490_6669345_朱喆 project1.py"
    path.write_text("print(1)", encoding="utf-8")
    submission = parse_submission_filename(path)
    assert submission.student_id == "22301020014"
    assert submission.platform_user_id == "200490"
    assert submission.submission_id == 6669345
    assert submission.name_from_filename == "朱喆"


def test_choose_latest_submission_by_submission_id(tmp_path: Path) -> None:
    old = parse_submission_filename(tmp_path / "22301020014_200490_6669344_朱喆 old.py")
    new = parse_submission_filename(tmp_path / "22301020014_200490_6669345_朱喆 new.py")
    selected, ignored = choose_latest_submissions([old, new])
    assert selected == [new]
    assert ignored == [old]


def test_load_assignment_selects_latest_and_skips_unsupported(tmp_path: Path) -> None:
    hw = make_assignment(tmp_path, "hw_1")
    submissions = hw / "submissions"
    (submissions / "22301020014_200490_6669344_朱喆 old.py").write_text("print('old')", encoding="utf-8")
    (submissions / "22301020014_200490_6669345_朱喆 new.py").write_text("print('new')", encoding="utf-8")
    (submissions / "bad.txt").write_text("bad", encoding="utf-8")

    loaded = load_assignment(tmp_path, "hw_1")

    assert len(loaded.selected) == 1
    assert loaded.selected[0].submission_id == 6669345
    assert len(loaded.ignored_duplicates) == 1
    assert len(loaded.skipped) == 1


def test_notebook_to_python_extracts_code_cells_only(tmp_path: Path) -> None:
    path = tmp_path / "notebook.ipynb"
    path.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_type": "markdown", "source": ["# title"]},
                    {"cell_type": "code", "source": ["x = 1\n", "print(x)\n"]},
                    {"cell_type": "code", "source": "y = 2"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert notebook_to_python(path) == "x = 1\nprint(x)\n\n\ny = 2"

