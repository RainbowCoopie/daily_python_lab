# 逐 key 比对: 谁新增、谁消失、谁改了。
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
