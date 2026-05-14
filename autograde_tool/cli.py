from __future__ import annotations

import argparse
import concurrent.futures
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from tqdm import tqdm

from .assignments import discover_assignments, load_assignment, prepare_submission, read_answer
from .config import DEFAULT_MODEL, load_deepseek_config, load_environment
from .deepseek_grader import DeepSeekGrader, GradingOptions
from .exporter import export_reports, summarize_scores
from .roster import load_course_roster
from .similarity import SimilarityChecker


DEFAULT_ASSIGNMENTS_DIR = Path("../assignments")
DEFAULT_EXPORTS = ["excel", "csv", "markdown"]
COURSE_ID = "108137"


def main(argv: Optional[list[str]] = None) -> int:
    load_environment(Path.cwd())
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] not in {"list", "grade", "-h", "--help"} and not argv[0].startswith("-"):
        argv.insert(0, "grade")
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")
    try:
        if args.command == "list":
            return list_assignments(args)
        return grade_command(args)
    except Exception as exc:  # noqa: BLE001
        print(f"错误: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AutoGrade: DeepSeek-powered Python assignment grading",
        epilog="示例: uv run autograde hw_9 | uv run autograde list",
    )
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="WARNING")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="列出可批改作业")
    list_parser.add_argument("--assignments-dir", type=Path, default=DEFAULT_ASSIGNMENTS_DIR)

    grade_parser = subparsers.add_parser("grade", help="批改单个作业；也可直接写 uv run autograde hw_9")
    add_grade_arguments(grade_parser, positional_required=True)
    return parser


def add_grade_arguments(parser: argparse.ArgumentParser, positional_required: bool) -> None:
    parser.add_argument("assignment", nargs=None if positional_required else "?", help="作业号，例如 hw_9 或 9")
    parser.add_argument("--assignments-dir", type=Path, default=DEFAULT_ASSIGNMENTS_DIR, help="作业根目录，默认 ../assignments")
    parser.add_argument("--answer", type=Path, help="手动指定答案文件")
    parser.add_argument("--parallel", "-p", type=int, default=25)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--thinking", action="store_true", help="启用 DeepSeek thinking mode")
    parser.add_argument("--resume", action="store_true", help="兼容参数；当前运行会重新生成报告")
    parser.add_argument("--retry-failed", action="store_true", help="兼容参数；当前运行会重新生成报告")
    parser.add_argument("--no-similarity", action="store_true")
    parser.add_argument("--student", "-s", help="只评分特定学号")
    parser.add_argument("--export", choices=["csv", "excel", "markdown", "all"], action="append", help="默认 excel,csv,markdown")
    parser.add_argument("--cache-dir", type=Path, default=Path(".autograde"))
    parser.add_argument("--course-id", default=COURSE_ID)
    parser.add_argument("--timeout", type=float, default=90.0)


def list_assignments(args: argparse.Namespace) -> int:
    assignments = discover_assignments(args.assignments_dir)
    if not assignments:
        print(f"未在 {args.assignments_dir.resolve()} 找到可批改作业。")
        return 1
    print(f"作业目录: {args.assignments_dir.resolve()}")
    print("作业\t提交文件\t答案文件")
    for assignment in assignments:
        print(f"{assignment.key}\t{assignment.raw_submission_count}\t{assignment.answer_file}")
    return 0


def grade_command(args: argparse.Namespace) -> int:
    assignment_key = args.assignment
    if not assignment_key:
        raise ValueError("请指定作业号，例如: uv run autograde hw_9")

    assignment_load = load_assignment(args.assignments_dir, assignment_key, args.answer)
    selected = assignment_load.selected
    if args.student:
        selected = [item for item in selected if item.student_id == args.student]
        if not selected:
            raise ValueError(f"未找到学生 {args.student} 的有效提交")

    roster = load_course_roster(args.cache_dir, args.course_id)
    answer_content = read_answer(assignment_load.assignment)
    prepared = [prepare_submission(submission) for submission in selected]
    print_header(assignment_load, len(selected), prepared, roster)

    config = load_deepseek_config(model=args.model, timeout=args.timeout)
    grader = DeepSeekGrader(config, GradingOptions(thinking=args.thinking))
    results = grade_prepared_submissions(prepared, answer_content, grader, args.parallel, roster)

    similarity_results = []
    if not args.no_similarity and len(prepared) > 1:
        checker = SimilarityChecker()
        similarity_results = checker.find_similar_submissions([(item.submission.student_id, item.content) for item in prepared])

    stats = summarize_scores(results)
    outputs = export_reports(assignment_load.assignment.path / "reports", results, similarity_results, stats, normalize_exports(args.export))
    print_summary(results, stats, similarity_results, outputs, roster)
    return 0


def grade_prepared_submissions(
    prepared: list,
    answer_content: str,
    grader: DeepSeekGrader,
    parallel: int,
    roster: dict,
) -> list[dict[str, Any]]:
    if parallel <= 1:
        return [build_result(item, grader.grade(item, answer_content), roster) for item in tqdm(prepared, desc="评分进度")]
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(grader.grade, item, answer_content): item for item in prepared}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="评分进度"):
            item = futures[future]
            results.append(build_result(item, future.result(), roster))
    return sorted(results, key=lambda row: row["student_id"])


def build_result(prepared, grade: dict[str, Any], roster: dict) -> dict[str, Any]:
    submission = prepared.submission
    roster_entry = roster.get(submission.student_id)
    warnings = list(submission.warnings)
    if prepared.converted_from_notebook:
        warnings.append("ipynb已转为Python代码评分")
    if not roster_entry:
        warnings.append("未在名单缓存中匹配到姓名，使用文件名回退")
    return {
        "student_id": submission.student_id,
        "name": roster_entry.name if roster_entry else submission.name_from_filename,
        "score": grade.get("score", 0),
        "comment": grade.get("comment", ""),
        "success": grade.get("success", False),
        "source_file": str(submission.source_file),
        "submission_id": submission.submission_id,
        "platform_user_id": submission.platform_user_id,
        "from_roster": bool(roster_entry),
        "warnings": warnings,
        "issues": grade.get("issues", []),
        "strengths": grade.get("strengths", []),
        "confidence": grade.get("confidence", ""),
        "from_cache": grade.get("from_cache", False),
    }


def normalize_exports(values: Optional[list[str]]) -> list[str]:
    if not values:
        return list(DEFAULT_EXPORTS)
    formats: list[str] = []
    for value in values:
        formats.extend(DEFAULT_EXPORTS if value == "all" else [value])
    return list(dict.fromkeys(formats))


def print_header(assignment_load, selected_count: int, prepared: list, roster: dict) -> None:
    notebook_count = sum(1 for item in prepared if item.converted_from_notebook)
    print(f"作业: {assignment_load.assignment.key}")
    print(f"答案: {assignment_load.assignment.answer_file.resolve()}")
    print(f"提交文件: {assignment_load.assignment.raw_submission_count}")
    print(f"有效提交: {selected_count}")
    print(f"重复提交忽略: {len(assignment_load.ignored_duplicates)}")
    print(f"Notebook 转换: {notebook_count}")
    print(f"跳过文件: {len(assignment_load.skipped)}")
    print(f"名单缓存: {len(roster)} 人")


def print_summary(results: list[dict[str, Any]], stats: dict[str, Any], similarity_results: list[dict[str, Any]], outputs: dict[str, Path], roster: dict) -> None:
    success_count = len([row for row in results if row.get("success")])
    unmatched = len([row for row in results if not row.get("from_roster")])
    print("\n评分完成")
    print(f"成功/总数: {success_count}/{len(results)}")
    print(f"平均分: {stats.get('mean', 0)}")
    print(f"最高分: {stats.get('max', 0)}")
    print(f"最低分: {stats.get('min', 0)}")
    print(f"相似作业对: {len(similarity_results)}")
    print(f"名单未匹配: {unmatched} (缓存 {len(roster)} 人)")
    print("输出文件:")
    for name, path in outputs.items():
        print(f"- {name}: {path.resolve()}")


if __name__ == "__main__":
    raise SystemExit(main())
