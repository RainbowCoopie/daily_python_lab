from watcher.diff import Change
from watcher.rules import Rule, filter_changes

CHANGES = [
    Change("changed", "price", "100", "120"),
    Change("changed", "noise", "1.00", "1.01"),
    Change("added", "fresh", None, "y"),
    Change("removed", "gone", "x", None),
]


def test_key_filter() -> None:
    kept = filter_changes(CHANGES, Rule(keys=("price",)))
    assert [c.key for c in kept] == ["price"]


def test_threshold_suppresses_small_numeric_delta() -> None:
    kept = filter_changes(CHANGES, Rule(min_delta=5))
    assert [c.key for c in kept] == ["price", "fresh", "gone"]


def test_threshold_keeps_non_numeric_values() -> None:
    changes = [Change("changed", "status", "old", "new")]
    assert filter_changes(changes, Rule(min_delta=100)) == changes


def test_added_removed_switches() -> None:
    kept = filter_changes(CHANGES, Rule(notify_added=False, notify_removed=False))
    assert [c.key for c in kept] == ["price", "noise"]
