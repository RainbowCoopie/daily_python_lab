# 告警规则: 按 key 过滤 + 数值阈值, 压掉无意义抖动。
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
