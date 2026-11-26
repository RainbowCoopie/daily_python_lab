# 校验规则与执行。
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
