'''声明式配置校验: 一次报出全部问题, 路径给人看, 类型判定严格到 bool。

灵感来源:
- probatio 的配置校验写法: Schema + Required/Optional + Range + In 的声明式组合
  (https://github.com/frenck/probatio/blob/9b70e3889ff60f6fdee716b26a0e592347d6f8ab/docs/src/content/docs/recipes/config-file.md)
- jsonschema 的做法是迭代出全部错误(iter_errors), 而不是遇到第一个就抛
  (https://stackoverflow.com/questions/31706047/python-json-shema-return-all-validation-errors/78948963)
- johnzon 的说明: 默认聚合全部错误, 且先跑便宜的检查(type/length/pattern)再跑递归的
  (https://github.com/apache/johnzon/commit/master#1)
- 一个真实的可用性问题: AJV 把路径里的斜杠转义成 ~1, 用户看不懂, 得自己格式化回来
  (https://www.volcengine.com/article/1887982)

为什么值得单独做一层: 配置错误的特点是"一次只报一个, 改完再跑又是下一个",
来回十几轮才能跑起来。聚合全部错误能把这一串变成一次。另外类型判定必须严格:
Python 里 `True == 1`, 如果不在类型检查里先排除 bool, `"debug": 1` 会被当成合法的布尔值。
路径的呈现也要分两套 —— 机器用 JSON Pointer, 人用点号路径, 混着用两边都难受。
'''

SLUG = "confcheck"
TITLE = "声明式配置校验"
TAGS = ["配置校验", "错误聚合", "类型严格性", "字段路径"]
PKG = "confcheck"
SUMMARY = "用声明式规则校验配置字典: 必填、类型、范围、长度、正则、枚举、嵌套与列表, 一次报出全部问题。"
STACK_NOTES = [
    "一次聚合全部错误, 不做 fail-fast —— 配置错了要一次改完, 而不是改一个跑一次",
    "类型判定严格: bool 不算 int, 但 int 可以当 float 用",
    "机器路径用 JSON Pointer, 人读路径用点号, 两套都提供",
]
NOTES = """
几个刻意的取舍:

**全聚合 vs fail-fast**。校验器默认返回所有问题。fail-fast 适合"输入可能恶意"的场景
(早停省算力), 但配置校验的主体是"我自己写错了", 一次看全才有效率。

**类型严格性**。`type=int` 时 `True` 不算数, 因为 `isinstance(True, int)` 为真;
`type=float` 时整数可以过, 因为 1 是合法的 1.0。这两个方向不对称, 但都符合直觉。

**路径双轨**。`Issue.path` 是给人读的点号路径(`server.port`), `pointer` 属性给出
RFC 6901 的机器路径(`/server/port`)。混用会很难受: 前者能直接贴进报错信息,
后者能直接用来定位 JSON 节点。

**未知键**。默认允许(很多配置允许扩展字段), 但 `allow_unknown=False` 时会把多余键报出来 ——
拼错键名是最常见的配置事故, 而它本身不会报错, 只会让配置静默失效。
"""

FILES = {
    "confcheck/__init__.py": '''from .rules import Issue, Rule, validate
from .report import format_issues

__all__ = ["Issue", "Rule", "validate", "format_issues"]
''',
    "confcheck/rules.py": '''# 校验规则与执行。
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Issue:
    path: str
    kind: str
    message: str

    @property
    def pointer(self) -> str:
        if not self.path:
            return ""
        return "".join("/" + part.replace("~", "~0").replace("/", "~1") for part in self.path.split("."))

    def render(self) -> str:
        where = self.path or "<root>"
        return f"{where}: {self.message}"


@dataclass(frozen=True)
class Rule:
    type: type | tuple[type, ...] | None = None
    required: bool = True
    min: float | None = None
    max: float | None = None
    min_len: int | None = None
    max_len: int | None = None
    pattern: str | None = None
    choices: tuple[Any, ...] | None = None
    of: "Rule | None" = None
    fields: dict[str, "Rule"] = field(default_factory=dict)
    allow_unknown: bool = True


def _join(prefix: str, key: str | int) -> str:
    return f"{prefix}.{key}" if prefix else str(key)


def _type_ok(value: Any, expected: type | tuple[type, ...]) -> bool:
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected is bool:
        return isinstance(value, bool)
    if isinstance(expected, tuple):
        return any(_type_ok(value, item) for item in expected)
    return isinstance(value, expected)


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if value is None:
        return "null"
    return type(value).__name__


def _check_value(value: Any, rule: Rule, path: str, out: list[Issue]) -> None:
    if rule.type is not None and not _type_ok(value, rule.type):
        expected = getattr(rule.type, "__name__", str(rule.type))
        out.append(Issue(path, "type", f"期望 {expected}, 收到 {_type_name(value)}"))
        return

    if rule.choices is not None and value not in rule.choices:
        out.append(Issue(path, "choice", f"取值必须在 {list(rule.choices)} 之内, 收到 {value!r}"))

    if rule.min is not None or rule.max is not None:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if rule.min is not None and value < rule.min:
                out.append(Issue(path, "range", f"不能小于 {rule.min}, 收到 {value}"))
            if rule.max is not None and value > rule.max:
                out.append(Issue(path, "range", f"不能大于 {rule.max}, 收到 {value}"))

    if rule.min_len is not None or rule.max_len is not None:
        if hasattr(value, "__len__"):
            length = len(value)
            if rule.min_len is not None and length < rule.min_len:
                out.append(Issue(path, "length", f"长度不能小于 {rule.min_len}, 收到 {length}"))
            if rule.max_len is not None and length > rule.max_len:
                out.append(Issue(path, "length", f"长度不能大于 {rule.max_len}, 收到 {length}"))

    if rule.pattern is not None and isinstance(value, str):
        if re.search(rule.pattern, value) is None:
            out.append(Issue(path, "pattern", f"不匹配模式 {rule.pattern!r}: {value!r}"))

    if rule.fields and isinstance(value, dict):
        _check_object(value, rule, path, out)

    if rule.of is not None and isinstance(value, list):
        for index, item in enumerate(value):
            _check_value(item, rule.of, _join(path, index), out)


def _check_object(data: dict, rule: Rule, path: str, out: list[Issue]) -> None:
    for key, child in rule.fields.items():
        child_path = _join(path, key)
        if key not in data:
            if child.required:
                out.append(Issue(child_path, "missing", "必填字段缺失"))
            continue
        _check_value(data[key], child, child_path, out)

    if not rule.allow_unknown:
        for key in sorted(data):
            if key not in rule.fields:
                out.append(Issue(_join(path, key), "unknown", "未定义的字段"))


def validate(data: Any, schema: dict[str, Rule] | Rule) -> list[Issue]:
    """校验数据, 返回全部问题(不 fail-fast)。"""
    issues: list[Issue] = []
    root = schema if isinstance(schema, Rule) else Rule(type=dict, fields=schema)
    # 一律走 _check_value: 根节点类型不对(比如传了列表)也要报出来
    _check_value(data, root, "", issues)
    return issues
''',
    "confcheck/report.py": '''# 错误报告: 给人读的形态。
from __future__ import annotations

from .rules import Issue


def format_issues(issues: list[Issue], title: str = "配置校验") -> str:
    if not issues:
        return f"【{title}】通过"
    lines = [f"【{title}】发现 {len(issues)} 个问题"]
    lines.extend(f"- {issue.render()}" for issue in issues)
    return "\\n".join(lines)
''',
    "tests/test_rules.py": '''import pytest

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
''',
    "tests/test_report.py": '''from confcheck import Rule, format_issues, validate


def test_pass_message() -> None:
    assert format_issues([]) == "【配置校验】通过"


def test_issue_lines() -> None:
    issues = validate({"port": "x"}, {"port": Rule(type=int)})
    text = format_issues(issues)
    lines = text.splitlines()
    assert lines[0] == "【配置校验】发现 1 个问题"
    assert lines[1].startswith("- port: ")


def test_root_rendered_as_root() -> None:
    issues = validate([], {"a": Rule(type=int)})
    assert issues[0].path == ""
    assert "<root>" in format_issues(issues)
''',
}

CHALLENGE = {
    "target": "confcheck/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 confcheck/challenge.py 中实现 check(port=8080, level='info') -> list[str]: "
        "用固定规则(port 为 int 且 1..65535, level 为 str 且取值在 debug/info/warn/error)校验, "
        "返回问题说明列表(用 confcheck.rules.Issue.render), 通过时返回空列表。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from confcheck.challenge import check


def test_valid() -> None:
    assert check() == []


def test_bad_port() -> None:
    issues = check(port=99999)
    assert len(issues) == 1
    assert "port" in issues[0]


def test_bad_level() -> None:
    issues = check(level="fatal")
    assert len(issues) == 1
    assert "level" in issues[0]
''',
}
