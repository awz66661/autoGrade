from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from importlib import resources
from pathlib import Path


STUDENT_ID_RE = re.compile(r"\b\d{8,12}\b")
CHINESE_NAME_RE = re.compile(r"[\u4e00-\u9fff·]{2,8}")


@dataclass(frozen=True)
class RosterEntry:
    student_id: str
    name: str
    source: str
    synced_at: str


def cache_path_for_course(cache_dir: Path, course_id: str) -> Path:
    return cache_dir / "rosters" / f"course_{course_id}.json"


def course_id_from_url(url: str) -> str:
    match = re.search(r"/courses/(\d+)", url)
    if not match:
        raise ValueError(f"无法从 URL 提取课程 ID: {url}")
    return match.group(1)


def load_roster_cache(cache_dir: Path, course_id: str) -> dict[str, RosterEntry]:
    path = cache_path_for_course(cache_dir, course_id)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["student_id"]: RosterEntry(
            student_id=item["student_id"],
            name=item["name"],
            source=item.get("source", "cache"),
            synced_at=item.get("synced_at", ""),
        )
        for item in data.get("students", [])
    }


def load_static_roster(course_id: str = "108137") -> dict[str, RosterEntry]:
    resource_name = f"course_{course_id}_roster.json"
    try:
        with resources.files("autograde_tool.data").joinpath(resource_name).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    return {
        item["student_id"]: RosterEntry(
            student_id=item["student_id"],
            name=item["name"],
            source=item.get("source", "static"),
            synced_at=item.get("synced_at", ""),
        )
        for item in data.get("students", [])
    }


def load_course_roster(cache_dir: Path, course_id: str = "108137") -> dict[str, RosterEntry]:
    roster = load_static_roster(course_id)
    roster.update(load_roster_cache(cache_dir, course_id))
    return roster


def save_roster_cache(cache_dir: Path, course_id: str, entries: list[RosterEntry]) -> Path:
    path = cache_path_for_course(cache_dir, course_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "course_id": course_id,
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "students": [entry.__dict__ for entry in sorted(entries, key=lambda item: item.student_id)],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_roster_html(html: str, source: str = "elearning") -> list[RosterEntry]:
    text = html_to_text(html)
    now = datetime.now().isoformat(timespec="seconds")
    entries: dict[str, RosterEntry] = {}
    for match in STUDENT_ID_RE.finditer(text):
        student_id = match.group(0)
        window = text[max(0, match.start() - 80) : min(len(text), match.end() + 80)]
        names = [name for name in CHINESE_NAME_RE.findall(window) if not _looks_like_label(name)]
        if not names:
            continue
        name = min(names, key=lambda item: abs(window.find(item) - window.find(student_id)))
        entries[student_id] = RosterEntry(student_id=student_id, name=name, source=source, synced_at=now)
    return list(entries.values())


def html_to_text(html: str) -> str:
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style\b.*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    html = unescape(html)
    return re.sub(r"\s+", " ", html)


def _looks_like_label(value: str) -> bool:
    return value in {"登录", "密码", "课程", "成员", "学生", "教师", "姓名", "学号", "用户"}
