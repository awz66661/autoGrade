from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


REPORT_COLUMNS = [
    "student_id",
    "name",
    "score",
    "comment",
    "success",
    "source_file",
    "submission_id",
    "platform_user_id",
    "from_roster",
    "warnings",
    "issues",
    "strengths",
    "confidence",
]


def summarize_scores(results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [int(item["score"]) for item in results if item.get("success")]
    if not scores:
        return {"count": 0, "mean": 0, "min": 0, "max": 0}
    return {"count": len(scores), "mean": round(sum(scores) / len(scores), 2), "min": min(scores), "max": max(scores)}


def export_reports(
    reports_dir: Path,
    results: list[dict[str, Any]],
    similarity_results: list[dict[str, Any]],
    stats: dict[str, Any],
    formats: list[str],
) -> dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outputs: dict[str, Path] = {}
    if "csv" in formats:
        outputs["csv"] = export_csv(reports_dir / f"grading_results_{timestamp}.csv", results)
    if "excel" in formats:
        outputs["excel"] = export_excel(reports_dir / f"grading_report_{timestamp}.xlsx", results, similarity_results, stats)
    if "markdown" in formats:
        outputs["markdown"] = export_markdown(reports_dir / f"grading_report_{timestamp}.md", results, similarity_results, stats)
    return outputs


def export_csv(path: Path, results: list[dict[str, Any]]) -> Path:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_fieldnames(results))
        writer.writeheader()
        for row in results:
            writer.writerow(_flatten(row))
    return path


def export_excel(path: Path, results: list[dict[str, Any]], similarity_results: list[dict[str, Any]], stats: dict[str, Any]) -> Path:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([_flatten(row) for row in results], columns=_fieldnames(results)).to_excel(writer, sheet_name="评分结果", index=False)
        pd.DataFrame(similarity_results).to_excel(writer, sheet_name="相似度检测", index=False)
        pd.DataFrame([{"metric": key, "value": value} for key, value in stats.items()]).to_excel(writer, sheet_name="统计摘要", index=False)
    return path


def export_markdown(path: Path, results: list[dict[str, Any]], similarity_results: list[dict[str, Any]], stats: dict[str, Any]) -> Path:
    lines = [
        "# 作业评分报告",
        "",
        "## 统计摘要",
        "",
        f"- 有效评分人数: {stats.get('count', 0)}",
        f"- 平均分: {stats.get('mean', 0)}",
        f"- 最高分: {stats.get('max', 0)}",
        f"- 最低分: {stats.get('min', 0)}",
        f"- 相似作业对: {len(similarity_results)}",
        "",
        "## 评分详情",
        "",
        "| 学号 | 姓名 | 分数 | 评语 | 状态 | 文件 |",
        "|---|---|---:|---|---|---|",
    ]
    for row in sorted(results, key=lambda item: str(item.get("student_id", ""))):
        status = "成功" if row.get("success") else "失败"
        lines.append(
            f"| {row.get('student_id', '')} | {row.get('name', '')} | {row.get('score', 0)} | "
            f"{row.get('comment', '')} | {status} | {Path(row.get('source_file', '')).name} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fieldnames(results: list[dict[str, Any]]) -> list[str]:
    fields = list(REPORT_COLUMNS)
    for row in results:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (list, tuple)):
            flattened[key] = "; ".join(str(item) for item in value)
        else:
            flattened[key] = value
    return flattened
