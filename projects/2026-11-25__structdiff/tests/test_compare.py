import pytest

from structdiff import Change, diff, format_changes


def test_identical_is_empty() -> None:
    assert diff({"a": 1}, {"a": 1}) == []


def test_add_and_remove() -> None:
    changes = diff({"a": 1}, {"b": 2})
    assert changes == [
        Change("remove", "/a", 1, None),
        Change("add", "/b", None, 2),
    ]


def test_replace() -> None:
    assert diff({"a": 1}, {"a": 2}) == [Change("replace", "/a", 1, 2)]


def test_type_change() -> None:
    changes = diff({"a": "1"}, {"a": 1})
    assert changes[0].op == "type_change"
    assert changes[0].path == "/a"


def test_missing_is_not_null() -> None:
    """{} 与 {"a": None} 的差别是 remove, 不是"没变化"。"""
    assert diff({}, {"a": None}) == [Change("add", "/a", None, None)]
    assert diff({"a": None}, {}) == [Change("remove", "/a", None, None)]


def test_null_vs_zero_is_type_change() -> None:
    assert diff({"a": None}, {"a": 0})[0].op == "type_change"


def test_bool_is_not_int() -> None:
    """Python 里 True == 1, 但 JSON 里 true 和 1 是不同类型, 必须报警。"""
    changes = diff({"flag": True}, {"flag": 1})
    assert changes[0].op == "type_change"


def test_int_and_float_are_equal() -> None:
    """JSON 只有一种数字类型, 1 与 1.0 视为相同。"""
    assert diff({"a": 1}, {"a": 1.0}) == []


def test_nested_path() -> None:
    changes = diff({"a": {"b": {"c": 1}}}, {"a": {"b": {"c": 2}}})
    assert changes == [Change("replace", "/a/b/c", 1, 2)]


def test_key_order_ignored() -> None:
    assert diff({"a": 1, "b": 2}, {"b": 2, "a": 1}) == []


def test_array_append_and_truncate() -> None:
    assert diff([1, 2], [1, 2, 3]) == [Change("add", "/2", None, 3)]
    assert diff([1, 2, 3], [1, 2]) == [Change("remove", "/2", 3, None)]


def test_array_element_replace() -> None:
    assert diff([1, 2], [1, 9]) == [Change("replace", "/1", 2, 9)]


def test_array_reorder_is_reported_as_changes() -> None:
    """按索引比较: 换顺序会被报成多处 replace, 这是刻意的。"""
    changes = diff([1, 2], [2, 1])
    assert [c.op for c in changes] == ["replace", "replace"]


def test_root_type_change() -> None:
    changes = diff({"a": 1}, [1])
    assert changes == [Change("type_change", "", {"a": 1}, [1])]


def test_escaping_in_paths() -> None:
    changes = diff({"a/b": 1}, {"a/b": 2})
    assert changes[0].path == "/a~1b"


def test_unicode_keys() -> None:
    assert diff({"名称": "甲"}, {"名称": "乙"})[0].path == "/名称"


def test_empty_containers() -> None:
    assert diff({}, {}) == []
    assert diff([], []) == []


def test_format_no_change() -> None:
    assert "没有变化" in format_changes([])


def test_format_lines() -> None:
    text = format_changes(diff({"a": 1, "b": 2}, {"a": 9, "c": 3}))
    lines = text.splitlines()
    assert lines[0] == "【结构比对】共 3 处变化"
    assert any(line.startswith("~ /a") for line in lines)
    assert any(line.startswith("- /b") for line in lines)
    assert any(line.startswith("+ /c") for line in lines)


def test_change_render_for_type_change() -> None:
    change = Change("type_change", "/x", "1", 1)
    assert "类型变化" in change.render()
