from pathlib import Path

import pytest

from dirdigest import diff, format_report, scan


def make(tmp_path: Path, name: str, files: dict[str, str], *, strict: bool = True) -> dict:
    root = tmp_path / name
    root.mkdir()
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return scan(root, strict=strict)


def test_no_change(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    after = make(tmp_path, "v2", {"a.txt": "x"})
    changes = diff(before, after)
    assert changes.is_empty is True
    assert changes.total == 0


def test_added_and_removed(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    after = make(tmp_path, "v2", {"b.txt": "y"})
    changes = diff(before, after)
    assert changes.added == ["b.txt"]
    assert changes.removed == ["a.txt"]


def test_modified(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    after = make(tmp_path, "v2", {"a.txt": "xx"})
    changes = diff(before, after)
    assert changes.modified == ["a.txt"]
    assert changes.added == [] and changes.removed == []


def test_rename_same_directory(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "same"})
    after = make(tmp_path, "v2", {"b.txt": "same"})
    changes = diff(before, after)
    assert changes.renamed == [("a.txt", "b.txt")]
    assert changes.added == [] and changes.removed == []


def test_move_across_directories(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "same"})
    after = make(tmp_path, "v2", {"sub/a.txt": "same"})
    changes = diff(before, after)
    assert changes.moved == [("a.txt", "sub/a.txt")]


def test_content_change_is_not_a_rename(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "one"})
    after = make(tmp_path, "v2", {"b.txt": "two"})
    changes = diff(before, after)
    assert changes.renamed == []
    assert changes.added == ["b.txt"]
    assert changes.removed == ["a.txt"]


def test_duplicate_content_pairs_one_to_one(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "dup", "b.txt": "dup"})
    after = make(tmp_path, "v2", {"c.txt": "dup"})
    changes = diff(before, after)
    assert len(changes.renamed) == 1
    assert len(changes.removed) == 1


def test_report_empty(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    assert "没有变化" in format_report(diff(before, before))


def test_report_lines(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"keep.txt": "k", "gone.txt": "old-content", "edit.txt": "v1"})
    after = make(tmp_path, "v2", {"keep.txt": "k", "fresh.txt": "new-content", "edit.txt": "v2"})
    text = format_report(diff(before, after))
    lines = text.splitlines()
    assert lines[0].startswith("【清单比对】共 3 处变化")
    assert "+ fresh.txt" in lines
    assert "- gone.txt" in lines
    assert "~ edit.txt" in lines


def test_two_different_files_never_pair_as_rename(tmp_path: Path) -> None:
    """摘要不同就不能配成改名, 否则会把"改内容 + 换名字"误报告成一次改名。"""
    before = make(tmp_path, "v1", {"a.txt": "one"})
    after = make(tmp_path, "v2", {"b.txt": "two"})
    text = format_report(diff(before, after))
    assert "R a.txt -> b.txt" not in text


def test_fast_mode_detects_size_change(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"}, strict=False)
    after = make(tmp_path, "v2", {"a.txt": "xxx"}, strict=False)
    assert diff(before, after).modified == ["a.txt"]


def test_fast_mode_cannot_detect_rename(tmp_path: Path) -> None:
    """fast 模式没有摘要, 改名只能退化报成 删除 + 新增 —— 这就是它快的代价。"""
    before = make(tmp_path, "v1", {"a.txt": "same"}, strict=False)
    after = make(tmp_path, "v2", {"b.txt": "same"}, strict=False)
    changes = diff(before, after)
    assert changes.renamed == []
    assert changes.added == ["b.txt"]
    assert changes.removed == ["a.txt"]
