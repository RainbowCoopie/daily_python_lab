from watcher.diff import diff_values


def test_detects_all_three_kinds() -> None:
    old = {"price": "100", "stock": "5", "drop": "x"}
    new = {"price": "120", "stock": "5", "fresh": "y"}
    changes = {(c.kind, c.key): (c.old, c.new) for c in diff_values(old, new)}
    assert changes[("changed", "price")] == ("100", "120")
    assert changes[("removed", "drop")] == ("x", None)
    assert changes[("added", "fresh")] == (None, "y")
    assert ("changed", "stock") not in changes


def test_no_change_returns_empty() -> None:
    assert diff_values({"a": "1"}, {"a": " 1 "}) == []


def test_output_is_sorted_by_key() -> None:
    changes = diff_values({"b": "1", "a": "1"}, {"b": "2", "a": "2"})
    assert [c.key for c in changes] == ["a", "b"]
