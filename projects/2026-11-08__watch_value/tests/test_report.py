from watcher.diff import Change
from watcher.report import format_report


def test_empty_report() -> None:
    assert format_report([]) == ""


def test_report_lines() -> None:
    changes = [
        Change("changed", "price", "100", "120"),
        Change("added", "fresh", None, "y"),
        Change("removed", "gone", "x", None),
    ]
    text = format_report(changes, title="电力价格")
    assert text.splitlines() == [
        "【电力价格】3 项变化",
        "- 改动 price: 100 -> 120",
        "- 新增 fresh: y",
        "- 消失 gone: 原值 x",
    ]
