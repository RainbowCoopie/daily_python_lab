# 结构比对: 先判类型, 再逐层比。
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .pointer import pointer

MISSING = object()


@dataclass(frozen=True)
class Change:
    op: str
    path: str
    old: Any = None
    new: Any = None

    def render(self) -> str:
        if self.op == "add":
            return f"+ {self.path or '<root>'} = {self.new!r}"
        if self.op == "remove":
            return f"- {self.path or '<root>'} (原值 {self.old!r})"
        if self.op == "type_change":
            return f"! {self.path or '<root>'} 类型变化 {type(self.old).__name__} -> {type(self.new).__name__}"
        return f"~ {self.path or '<root>'} {self.old!r} -> {self.new!r}"


def kind(value: Any) -> str:
    """JSON 的类型类别。bool 必须先于 int 判断。"""
    if isinstance(value, bool):
        return "bool"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "other"


def _diff(old: Any, new: Any, path: tuple[str | int, ...], out: list[Change]) -> None:
    left, right = kind(old), kind(new)
    if left != right:
        out.append(Change("type_change", pointer(path), old, new))
        return

    if left == "object":
        for key in sorted(set(old) | set(new), key=str):
            if key not in old:
                out.append(Change("add", pointer((*path, key)), None, new[key]))
            elif key not in new:
                out.append(Change("remove", pointer((*path, key)), old[key], None))
            else:
                _diff(old[key], new[key], (*path, key), out)
        return

    if left == "array":
        for index in range(max(len(old), len(new))):
            if index >= len(old):
                out.append(Change("add", pointer((*path, index)), None, new[index]))
            elif index >= len(new):
                out.append(Change("remove", pointer((*path, index)), old[index], None))
            else:
                _diff(old[index], new[index], (*path, index), out)
        return

    if old != new:
        out.append(Change("replace", pointer(path), old, new))


def diff(old: Any, new: Any) -> list[Change]:
    changes: list[Change] = []
    _diff(old, new, (), changes)
    return changes


def format_changes(changes: list[Change], title: str = "结构比对") -> str:
    if not changes:
        return f"【{title}】没有变化"
    lines = [f"【{title}】共 {len(changes)} 处变化"]
    lines.extend(change.render() for change in changes)
    return "\n".join(lines)
