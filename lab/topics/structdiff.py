'''JSON 结构比对: 按 RFC 6901 的 JSON Pointer 定位, 分 add/remove/replace/type_change 四类。

灵感来源:
- RFC 6902 定义 JSON Patch 的三种改动语义(add/remove/replace), 位置用 RFC 6901 的 JSON Pointer
  (https://datatracker.ietf.org/doc/html/rfc6902)
- 一篇把语义讲透的中文文章: 对象忽略成员顺序; 数组按索引比较, 顺序变化算变化;
  缺失字段与值为 null 不等价; 字符串 "1" 与数字 1 不等价; 键里的 / 要转成 ~1, ~ 转成 ~0;
  根节点的 Pointer 是空字符串而不是 "/"
  (https://bbs.huaweicloud.com/blogs/497838)
- 一个真实 issue: 接口返回的数组按某字段排序, 一旦后端换了排序, diff 就变成满屏噪声
  (https://github.com/RexSkz/json-diff-kit/issues/49)

为什么值得单独做一层: 直接比字符串会把缩进、换行、键顺序全算成变化; 而随手写的递归比较
又总在几个地方出错 —— 缺失与 null 混淆、True 与 1 被当成相等(Python 里 `True == 1` 为真)、
1 与 1.0 被当成不同。这些边界必须显式写下来, 否则对账时会得出"配置没变"的错误结论。
'''

SLUG = "structdiff"
TITLE = "JSON 结构比对"
TAGS = ["JSON Pointer", "RFC 6902", "配置对比", "边界语义"]
PKG = "structdiff"
SUMMARY = "两份 JSON 的结构差异: 按 JSON Pointer 报出 add/remove/replace/type_change, 语义边界逐条固定。"
STACK_NOTES = [
    "对象忽略键顺序, 数组按索引比较 —— 顺序变化就算变化, 这是刻意的",
    "缺失与 null 不等价; True 与 1 不等价; 1 与 1.0 按数值比较视为相等",
    "路径按 RFC 6901 转义: 键里的 ~ 记作 ~0, / 记作 ~1, 根节点是空字符串",
]
NOTES = """
四条容易写错的语义, 都在测试里钉住了:

1. **缺失 ≠ null**。`{"a": null}` 与 `{}` 的差别是"有值且为空"和"根本没有", 前者是 replace,
   后者是 remove。很多实现把两者都当 None, 于是报"没变化"。
2. **True ≠ 1**。Python 里 `True == 1` 为真、`isinstance(True, int)` 也为真,
   所以比较时必须先判 bool。接口里 `"flag": true` 变成 `1` 是要报警的。
3. **1 == 1.0**。JSON 只有一种数字类型, RFC 6902 也按数值比较, 所以 `1` 与 `1.0` 视为相等。
   这和上一条方向相反, 但两者都符合各自的规范。
4. **数组按索引**。`[1,2]` 与 `[2,1]` 是两处 replace, 而不是"顺序变了"。要做"忽略顺序"的
   集合比较得由上层按业务键先归一化 —— 那是另一个问题, 混进来会让 diff 结果不可预测。

根节点的 Pointer 是空字符串, 不是 "/" —— "/" 表示"键名为空字符串的成员"。
"""

FILES = {
    "structdiff/__init__.py": '''from .compare import Change, diff, format_changes
from .pointer import pointer

__all__ = ["Change", "diff", "format_changes", "pointer"]
''',
    "structdiff/pointer.py": '''# RFC 6901 JSON Pointer。
from __future__ import annotations

from typing import Iterable


def escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def pointer(parts: Iterable[str | int]) -> str:
    """把路径片段拼成 JSON Pointer; 根节点是空字符串。"""
    return "".join("/" + escape(str(part)) for part in parts)
''',
    "structdiff/compare.py": '''# 结构比对: 先判类型, 再逐层比。
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
    return "\\n".join(lines)
''',
    "tests/test_pointer.py": '''from structdiff import pointer
from structdiff.pointer import escape


def test_root_is_empty_string() -> None:
    assert pointer([]) == ""


def test_simple_path() -> None:
    assert pointer(["a", "b"]) == "/a/b"
    assert pointer([0, "name"]) == "/0/name"


def test_escape_slash_then_tilde() -> None:
    """顺序很重要: 先转 ~ 再转 /, 否则 / 会变成 ~1 里的 ~ 被二次转义。"""
    assert escape("a/b") == "a~1b"
    assert escape("m~n") == "m~0n"
    assert escape("a~/b") == "a~0~1b"


def test_pointer_escapes_keys() -> None:
    assert pointer(["a/b"]) == "/a~1b"
    assert pointer(["m~n"]) == "/m~0n"


def test_pointer_empty_key_is_single_slash() -> None:
    """空键名与根节点不同: 前者是 '/', 后者是 ''。"""
    assert pointer([""]) == "/"
    assert pointer([]) == ""


def test_pointer_unicode_key() -> None:
    assert pointer(["名称"]) == "/名称"
''',
    "tests/test_compare.py": '''import pytest

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
''',
}

CHALLENGE = {
    "target": "structdiff/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 structdiff/challenge.py 中实现 summarise(old, new) -> dict[str, int]: "
        "用 structdiff.compare.diff 统计各 op 的次数, 返回 {'add': n, 'remove': n, 'replace': n, 'type_change': n}; "
        "没有变化时全为 0。不得修改其他模块。"
    ),
    "tests_content": '''from structdiff.challenge import summarise


def test_counts() -> None:
    got = summarise({"a": 1, "b": 2}, {"a": 9, "c": 3})
    assert got == {"add": 1, "remove": 1, "replace": 1, "type_change": 0}


def test_no_change() -> None:
    assert summarise({"a": 1}, {"a": 1}) == {"add": 0, "remove": 0, "replace": 0, "type_change": 0}
''',
}
