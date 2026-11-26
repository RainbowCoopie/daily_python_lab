import pytest

from confcheck import Rule, validate


def test_valid_passes() -> None:
    schema = {"name": Rule(type=str), "port": Rule(type=int, min=1, max=65535)}
    assert validate({"name": "api", "port": 8080}, schema) == []


def test_missing_required() -> None:
    issues = validate({}, {"name": Rule(type=str)})
    assert len(issues) == 1
    assert issues[0].kind == "missing"
    assert issues[0].path == "name"


def test_optional_field_may_be_absent() -> None:
    assert validate({}, {"level": Rule(type=str, required=False)}) == []


def test_missing_is_reported_even_for_optional_when_present_wrong() -> None:
    issues = validate({"level": 3}, {"level": Rule(type=str, required=False)})
    assert issues[0].kind == "type"


def test_type_mismatch() -> None:
    issues = validate({"port": "8080"}, {"port": Rule(type=int)})
    assert issues[0].kind == "type"
    assert "str" in issues[0].message


def test_bool_is_not_int() -> None:
    """Python 里 isinstance(True, int) 为真, 但配置里 true 不能当端口号。"""
    issues = validate({"port": True}, {"port": Rule(type=int)})
    assert issues[0].kind == "type"


def test_bool_field_accepts_bool() -> None:
    assert validate({"debug": True}, {"debug": Rule(type=bool)}) == []


def test_int_accepted_as_float() -> None:
    assert validate({"ratio": 1}, {"ratio": Rule(type=float)}) == []


def test_range_bounds_inclusive() -> None:
    schema = {"n": Rule(type=int, min=1, max=3)}
    assert validate({"n": 1}, schema) == []
    assert validate({"n": 3}, schema) == []
    assert validate({"n": 0}, schema)[0].kind == "range"
    assert validate({"n": 4}, schema)[0].kind == "range"


def test_length_bounds_on_string() -> None:
    schema = {"name": Rule(type=str, min_len=2, max_len=4)}
    assert validate({"name": "abc"}, schema) == []
    assert validate({"name": "a"}, schema)[0].kind == "length"
    assert validate({"name": "abcde"}, schema)[0].kind == "length"


def test_pattern() -> None:
    schema = {"code": Rule(type=str, pattern=r"^[A-Z]{2}$")}
    assert validate({"code": "AB"}, schema) == []
    assert validate({"code": "ab"}, schema)[0].kind == "pattern"
    assert validate({"code": "ABC"}, schema)[0].kind == "pattern"


def test_choices() -> None:
    schema = {"level": Rule(type=str, choices=("debug", "info"))}
    assert validate({"level": "info"}, schema) == []
    assert validate({"level": "warn"}, schema)[0].kind == "choice"


def test_nested_object_paths() -> None:
    schema = {"server": Rule(type=dict, fields={"port": Rule(type=int)})}
    issues = validate({"server": {"port": "x"}}, schema)
    assert issues[0].path == "server.port"


def test_nested_missing() -> None:
    schema = {"server": Rule(type=dict, fields={"host": Rule(type=str)})}
    issues = validate({"server": {}}, schema)
    assert issues[0].path == "server.host"
    assert issues[0].kind == "missing"


def test_list_item_rule() -> None:
    schema = {"tags": Rule(type=list, of=Rule(type=str))}
    assert validate({"tags": ["a", "b"]}, schema) == []
    issues = validate({"tags": ["a", 2]}, schema)
    assert issues[0].path == "tags.1"
    assert issues[0].kind == "type"


def test_all_issues_reported_at_once() -> None:
    """不做 fail-fast: 三个问题一次全报。"""
    schema = {
        "name": Rule(type=str),
        "port": Rule(type=int, max=65535),
        "level": Rule(type=str, choices=("info",)),
    }
    issues = validate({"port": 70000, "level": "warn"}, schema)
    kinds = sorted(issue.kind for issue in issues)
    assert kinds == ["choice", "missing", "range"]
    assert len(issues) == 3


def test_unknown_keys_allowed_by_default() -> None:
    schema = {"a": Rule(type=int)}
    assert validate({"a": 1, "b": 2}, schema) == []


def test_unknown_keys_reported_when_disallowed() -> None:
    schema = Rule(type=dict, fields={"a": Rule(type=int)}, allow_unknown=False)
    issues = validate({"a": 1, "typo": 2}, schema)
    assert issues[0].kind == "unknown"
    assert issues[0].path == "typo"


def test_root_type_mismatch() -> None:
    issues = validate([1, 2], {"a": Rule(type=int)})
    assert issues[0].kind == "type"


def test_empty_schema_accepts_anything() -> None:
    assert validate({"anything": 1}, {}) == []


def test_pointer_property_escapes() -> None:
    rule = Rule(type=dict, fields={"a/b": Rule(type=int)})
    issues = validate({"a/b": "x"}, rule)
    assert issues[0].path == "a/b"
    assert issues[0].pointer == "/a~1b"
