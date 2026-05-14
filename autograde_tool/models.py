from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Assignment:
    key: str
    path: Path
    answer_file: Path
    submissions_dir: Path
    raw_submission_count: int


@dataclass(frozen=True)
class Submission:
    student_id: str
    platform_user_id: str
    submission_id: int
    name_from_filename: str
    source_file: Path
    suffix: str
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PreparedSubmission:
    submission: Submission
    content: str
    converted_from_notebook: bool = False


@dataclass(frozen=True)
class SkippedSubmission:
    source_file: Path
    reason: str
    student_id: str = ""


@dataclass(frozen=True)
class AssignmentLoad:
    assignment: Assignment
    selected: list[Submission]
    ignored_duplicates: list[Submission]
    skipped: list[SkippedSubmission]

