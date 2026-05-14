from __future__ import annotations

from pathlib import Path

from autograde_tool import cli
from autograde_tool.roster import RosterEntry, save_roster_cache


class FakeGrader:
    def __init__(self, config, options):
        self.config = config
        self.options = options

    def grade(self, prepared, answer_content):
        return {
            "score": 96,
            "comment": "功能正确",
            "issues": [],
            "strengths": ["完整"],
            "confidence": "high",
            "success": True,
        }


def test_cli_generates_reports_with_name_column(tmp_path: Path, monkeypatch) -> None:
    assignments = tmp_path / "assignments"
    hw = assignments / "hw_test"
    (hw / "answer").mkdir(parents=True)
    (hw / "submissions").mkdir()
    (hw / "answer" / "answer.py").write_text("print('answer')\n", encoding="utf-8")
    (hw / "submissions" / "22301020014_200490_6669345_朱喆 project.py").write_text("print('student')\n", encoding="utf-8")
    save_roster_cache(
        tmp_path / ".autograde",
        "108137",
        [RosterEntry("22301020014", "朱喆", "test", "now")],
    )

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(cli, "DeepSeekGrader", FakeGrader)

    exit_code = cli.main(
        [
            "grade",
            "hw_test",
            "--assignments-dir",
            str(assignments),
            "--cache-dir",
            str(tmp_path / ".autograde"),
            "--no-similarity",
        ]
    )

    assert exit_code == 0
    csv_files = list((hw / "reports").glob("grading_results_*.csv"))
    assert csv_files
    assert "name" in csv_files[0].read_text(encoding="utf-8-sig").splitlines()[0]
    assert "朱喆" in csv_files[0].read_text(encoding="utf-8-sig")

