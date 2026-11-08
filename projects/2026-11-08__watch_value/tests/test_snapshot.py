from pathlib import Path

from watcher.snapshot import digest, load_snapshot, normalize, save_snapshot


def test_normalize_strips_and_stringifies() -> None:
    assert normalize({"a": "  x  y ", "b": 3, "c": None}) == {"a": "x y", "b": "3", "c": ""}


def test_digest_stable_regardless_of_order() -> None:
    assert digest({"a": "1", "b": "2"}) == digest({"b": "2", "a": "1"})


def test_digest_changes_when_value_changes() -> None:
    assert digest({"a": "1"}) != digest({"a": "2"})


def test_digest_ignores_whitespace_noise() -> None:
    assert digest({"a": "  1  "}) == digest({"a": "1"})


def test_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    assert load_snapshot(path) == {}
    sha = save_snapshot(path, {"a": " 1 ", "b": 2})
    assert sha == digest({"a": "1", "b": "2"})
    assert load_snapshot(path) == {"a": "1", "b": "2"}
