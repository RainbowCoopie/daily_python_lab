from pathlib import Path

import pytest

from dirdigest import Entry, load, save, scan


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "junk.pyc").write_bytes(b"x")
    return tmp_path


def test_scan_collects_files(tree: Path) -> None:
    entries = scan(tree)
    assert sorted(entries) == ["a.txt", "sub/b.bin"]


def test_scan_skips_ignored_dirs(tree: Path) -> None:
    assert all("__pycache__" not in path for path in scan(tree))


def test_scan_records_size_and_digest(tree: Path) -> None:
    entry = scan(tree)["a.txt"]
    assert entry.size == 5
    assert entry.digest is not None
    assert len(entry.digest) == 64


def test_digest_is_stable(tree: Path) -> None:
    assert scan(tree)["a.txt"].digest == scan(tree)["a.txt"].digest


def test_fast_mode_skips_digest(tree: Path) -> None:
    entries = scan(tree, strict=False)
    assert entries["a.txt"].digest is None
    assert entries["a.txt"].size == 5


def test_identical_content_same_digest(tmp_path: Path) -> None:
    (tmp_path / "x").write_text("same", encoding="utf-8")
    (tmp_path / "y").write_text("same", encoding="utf-8")
    entries = scan(tmp_path)
    assert entries["x"].digest == entries["y"].digest


def test_scan_rejects_non_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "f.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        scan(file_path)


def test_save_and_load_roundtrip(tree: Path, tmp_path: Path) -> None:
    entries = scan(tree)
    out = tmp_path / "manifest.json"
    save(entries, out)
    restored = load(out)
    assert restored == entries


def test_saved_manifest_is_sorted(tree: Path, tmp_path: Path) -> None:
    out = tmp_path / "manifest.json"
    save(scan(tree), out)
    body = out.read_text(encoding="utf-8")
    assert body.index("a.txt") < body.index("sub/b.bin")


def test_entry_is_immutable() -> None:
    entry = Entry(path="a", size=1, mtime_ns=2, digest=None)
    with pytest.raises(Exception):
        entry.size = 3  # type: ignore[misc]
