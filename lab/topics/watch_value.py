'''监控预警类工作的内核: 抓值 -> 存快照 -> 比对 -> 只在真变化时告警。纯标准库。'''

SLUG = "watch_value"
TITLE = "取值监控与变更告警"
TAGS = ["监控预警", "快照比对", "RPA 场景", "stdlib"]
PKG = "watcher"
SUMMARY = "把网页/接口/报表里的值抽成快照, 下次运行比对出新增、消失、改动, 再按规则决定要不要告警。"
STACK_NOTES = [
    "快照用排序后的 JSON 做 sha256, 值没变就不告警, 避免刷屏",
    "diff 区分 added / removed / changed 三类, 每条都带旧值与新值",
    "规则支持按 key 过滤和数值阈值, 阈值内的抖动不打扰人",
]
NOTES = """
监控类项目最常见的失败不是抓不到数据, 是**告警太多**。这里的做法是:
先把值规范化成 dict -> 用摘要判断"整体有没有变" (一层粗筛),
变了再做逐 key 的 diff (二层细筛), 最后用规则过滤 (三层),
三层都过了才发告警。抓取层不在本模块, 只约定输入是 dict[str, str],
这样换成 requests / DrissionPage / Excel 读出来都能接。
"""

FILES = {
    "watcher/__init__.py": '''from .diff import Change, diff_values
from .report import format_report
from .snapshot import digest, load_snapshot, normalize, save_snapshot
from .rules import Rule, filter_changes

__all__ = [
    "Change",
    "diff_values",
    "format_report",
    "digest",
    "normalize",
    "load_snapshot",
    "save_snapshot",
    "Rule",
    "filter_changes",
]
''',
    "watcher/snapshot.py": '''# 快照: 规范化 + 摘要 + 落盘。
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def normalize(values: dict[str, object]) -> dict[str, str]:
    """值统一成去空白的字符串; 空值收敛成空串, 方便比较。"""
    out: dict[str, str] = {}
    for key, value in values.items():
        text = "" if value is None else str(value)
        out[str(key)] = " ".join(text.split())
    return out


def digest(values: dict[str, object]) -> str:
    """排序后序列化再摘要: 同样的值永远得到同样的摘要。"""
    payload = json.dumps(normalize(values), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_snapshot(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_snapshot(path: str | Path, values: dict[str, object]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = normalize(values)
    p.write_text(json.dumps(clean, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return digest(clean)
''',
    "watcher/diff.py": '''# 逐 key 比对: 谁新增、谁消失、谁改了。
from __future__ import annotations

from dataclasses import dataclass

from .snapshot import normalize


@dataclass(frozen=True)
class Change:
    kind: str  # added | removed | changed
    key: str
    old: str | None
    new: str | None


def diff_values(old: dict[str, str], new: dict[str, str]) -> list[Change]:
    """按 key 求差; 结果按 key 排序, 保证输出稳定可 diff。"""
    a = normalize(old)
    b = normalize(new)
    changes: list[Change] = []
    for key in sorted(set(a) | set(b)):
        if key not in a:
            changes.append(Change("added", key, None, b[key]))
        elif key not in b:
            changes.append(Change("removed", key, a[key], None))
        elif a[key] != b[key]:
            changes.append(Change("changed", key, a[key], b[key]))
    return changes
''',
    "watcher/rules.py": '''# 告警规则: 按 key 过滤 + 数值阈值, 压掉无意义抖动。
from __future__ import annotations

from dataclasses import dataclass

from .diff import Change


@dataclass(frozen=True)
class Rule:
    """min_delta 只对有数值意义的 changed 生效; None 表示不做阈值过滤。"""

    keys: tuple[str, ...] = ()
    min_delta: float | None = None
    notify_removed: bool = True
    notify_added: bool = True


def _as_number(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def filter_changes(changes: list[Change], rule: Rule) -> list[Change]:
    kept: list[Change] = []
    for change in changes:
        if rule.keys and change.key not in rule.keys:
            continue
        if change.kind == "added" and not rule.notify_added:
            continue
        if change.kind == "removed" and not rule.notify_removed:
            continue
        if change.kind == "changed" and rule.min_delta is not None:
            old_num, new_num = _as_number(change.old), _as_number(change.new)
            if old_num is not None and new_num is not None:
                if abs(new_num - old_num) < rule.min_delta:
                    continue
        kept.append(change)
    return kept
''',
    "watcher/report.py": '''# 告警文本: 一行一条, 便于直接丢进邮件/机器人。
from __future__ import annotations

from .diff import Change

LABEL = {"added": "新增", "removed": "消失", "changed": "改动"}


def format_report(changes: list[Change], title: str = "监控告警") -> str:
    if not changes:
        return ""
    lines = [f"【{title}】{len(changes)} 项变化"]
    for change in changes:
        tag = LABEL.get(change.kind, change.kind)
        if change.kind == "added":
            lines.append(f"- {tag} {change.key}: {change.new}")
        elif change.kind == "removed":
            lines.append(f"- {tag} {change.key}: 原值 {change.old}")
        else:
            lines.append(f"- {tag} {change.key}: {change.old} -> {change.new}")
    return "\\n".join(lines)
''',
    "tests/test_snapshot.py": '''from pathlib import Path

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
''',
    "tests/test_diff.py": '''from watcher.diff import diff_values


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
''',
    "tests/test_rules.py": '''from watcher.diff import Change
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
''',
    "tests/test_report.py": '''from watcher.diff import Change
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
''',
}

CHALLENGE = {
    "target": "watcher/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 watcher/challenge.py 中实现 watch(old: dict[str, str], new: dict[str, str], rule=None) -> str: "
        "用 watcher.diff.diff_values 求差, 用 watcher.rules.filter_changes 过滤(rule 为 None 时不过滤), "
        "再用 watcher.report.format_report 渲染; 没有变化时返回空字符串。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from watcher.challenge import watch
from watcher.rules import Rule


def test_no_change_is_empty() -> None:
    assert watch({"a": "1"}, {"a": "1"}) == ""


def test_change_rendered() -> None:
    text = watch({"a": "1"}, {"a": "2"})
    assert "a: 1 -> 2" in text


def test_rule_filters() -> None:
    assert watch({"a": "1"}, {"a": "1.1"}, Rule(min_delta=5)) == ""
''',
}
