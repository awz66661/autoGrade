from __future__ import annotations

from pathlib import Path

from autograde_tool.roster import load_course_roster, load_roster_cache, load_static_roster, parse_roster_html, save_roster_cache


def test_parse_roster_html_extracts_student_name_pairs() -> None:
    html = """
    <html><body>
      <tr><td>张三</td><td>22301020014</td></tr>
      <tr><td>李四</td><td>25303080031</td></tr>
    </body></html>
    """
    roster = {item.student_id: item.name for item in parse_roster_html(html)}
    assert roster == {"22301020014": "张三", "25303080031": "李四"}


def test_save_and_load_roster_cache(tmp_path: Path) -> None:
    entries = parse_roster_html("<span>王五</span><span>22300110017</span>")
    save_roster_cache(tmp_path, "108137", entries)
    loaded = load_roster_cache(tmp_path, "108137")
    assert loaded["22300110017"].name == "王五"


def test_static_roster_is_available() -> None:
    roster = load_static_roster("108137")
    assert roster["21300270019"].name == "白展铭"


def test_course_roster_allows_cache_override(tmp_path: Path) -> None:
    entries = parse_roster_html("<span>王五</span><span>21300270019</span>")
    save_roster_cache(tmp_path, "108137", entries)
    roster = load_course_roster(tmp_path, "108137")
    assert roster["21300270019"].name == "王五"
