from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from .models import Assignment, AssignmentLoad, PreparedSubmission, SkippedSubmission, Submission


SUPPORTED_SUFFIXES = {".py", ".ipynb"}
SUBMISSION_RE = re.compile(
    r"^(?P<student_id>\d{8,12})_(?P<platform_user_id>\d+)_(?P<submission_id>\d+)_(?P<trailing>.+)$"
)
NAME_RE = re.compile(r"[\u4e00-\u9fff·]{2,8}")


def normalize_assignment_key(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"\d+", value):
        return f"hw_{value}"
    if re.fullmatch(r"hw_[A-Za-z0-9_-]+", value):
        return value
    raise ValueError(f"作业名必须形如 hw_9 或 9，收到: {value}")


def discover_assignments(assignments_dir: Path) -> list[Assignment]:
    assignments = []
    for path in sorted(assignments_dir.glob("hw_*"), key=_assignment_sort_key):
        if not path.is_dir():
            continue
        submissions_dir = path / "submissions"
        if not submissions_dir.is_dir():
            continue
        try:
            answer_file = find_answer_file(path)
        except FileNotFoundError:
            continue
        raw_count = len([p for p in submissions_dir.iterdir() if p.is_file()])
        assignments.append(
            Assignment(
                key=path.name,
                path=path,
                answer_file=answer_file,
                submissions_dir=submissions_dir,
                raw_submission_count=raw_count,
            )
        )
    return assignments


def find_assignment(assignments_dir: Path, assignment_key: str, answer: Optional[Path] = None) -> Assignment:
    key = normalize_assignment_key(assignment_key)
    path = assignments_dir / key
    if not path.is_dir():
        raise FileNotFoundError(f"未找到作业目录: {path}")
    submissions_dir = path / "submissions"
    if not submissions_dir.is_dir():
        raise FileNotFoundError(f"未找到 submissions 目录: {submissions_dir}")
    answer_file = answer if answer else find_answer_file(path)
    if not answer_file.is_file():
        raise FileNotFoundError(f"未找到答案文件: {answer_file}")
    raw_count = len([p for p in submissions_dir.iterdir() if p.is_file()])
    return Assignment(key=key, path=path, answer_file=answer_file, submissions_dir=submissions_dir, raw_submission_count=raw_count)


def find_answer_file(assignment_dir: Path) -> Path:
    answer_dir = assignment_dir / "answer"
    if not answer_dir.is_dir():
        raise FileNotFoundError(f"未找到 answer 目录: {answer_dir}")
    project_match = answer_dir / f"project{_assignment_number(assignment_dir.name)}.py"
    if project_match.is_file():
        return project_match
    py_files = sorted(answer_dir.glob("*.py"))
    if len(py_files) == 1:
        return py_files[0]
    if not py_files:
        raise FileNotFoundError(f"answer 目录中没有 Python 答案文件: {answer_dir}")
    names = ", ".join(p.name for p in py_files)
    raise ValueError(f"answer 目录中有多个 Python 文件，请用 --answer 指定: {names}")


def load_assignment(assignments_dir: Path, assignment_key: str, answer: Optional[Path] = None) -> AssignmentLoad:
    assignment = find_assignment(assignments_dir, assignment_key, answer)
    parsed: list[Submission] = []
    skipped: list[SkippedSubmission] = []
    for path in sorted(p for p in assignment.submissions_dir.iterdir() if p.is_file()):
        if path.name == ".DS_Store":
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            skipped.append(SkippedSubmission(source_file=path, reason=f"不支持的文件类型: {path.suffix or '(none)'}"))
            continue
        try:
            parsed.append(parse_submission_filename(path))
        except ValueError as exc:
            skipped.append(SkippedSubmission(source_file=path, reason=str(exc)))

    selected, ignored = choose_latest_submissions(parsed)
    return AssignmentLoad(assignment=assignment, selected=selected, ignored_duplicates=ignored, skipped=skipped)


def parse_submission_filename(path: Path) -> Submission:
    match = SUBMISSION_RE.match(path.name)
    if not match:
        raise ValueError("文件名不符合 学号_平台用户ID_提交ID_姓名+文件名 格式")
    trailing = match.group("trailing")
    name_match = NAME_RE.search(trailing)
    name = name_match.group(0) if name_match else ""
    warnings = tuple([] if name else ["无法从文件名解析姓名"])
    return Submission(
        student_id=match.group("student_id"),
        platform_user_id=match.group("platform_user_id"),
        submission_id=int(match.group("submission_id")),
        name_from_filename=name,
        source_file=path,
        suffix=path.suffix.lower(),
        warnings=warnings,
    )


def choose_latest_submissions(submissions: Iterable[Submission]) -> tuple[list[Submission], list[Submission]]:
    grouped: dict[str, list[Submission]] = defaultdict(list)
    for submission in submissions:
        grouped[submission.student_id].append(submission)
    selected: list[Submission] = []
    ignored: list[Submission] = []
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: (item.submission_id, item.source_file.name), reverse=True)
        selected.append(ordered[0])
        ignored.extend(ordered[1:])
    return sorted(selected, key=lambda item: item.student_id), sorted(ignored, key=lambda item: (item.student_id, item.submission_id))


def read_answer(assignment: Assignment) -> str:
    return assignment.answer_file.read_text(encoding="utf-8")


def prepare_submission(submission: Submission) -> PreparedSubmission:
    if submission.suffix == ".py":
        content = submission.source_file.read_text(encoding="utf-8", errors="ignore")
        return PreparedSubmission(submission=submission, content=content)
    if submission.suffix == ".ipynb":
        return PreparedSubmission(submission=submission, content=notebook_to_python(submission.source_file), converted_from_notebook=True)
    raise ValueError(f"不支持的文件类型: {submission.source_file}")


def notebook_to_python(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[str] = []
    for cell in data.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        chunks.append("".join(source) if isinstance(source, list) else str(source))
    return "\n\n".join(chunks).strip()


def _assignment_number(key: str) -> str:
    match = re.search(r"(\d+)$", key)
    return match.group(1) if match else ""


def _assignment_sort_key(path: Path) -> tuple[int, str]:
    number = _assignment_number(path.name)
    return (int(number) if number else 10**9, path.name)
