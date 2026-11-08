# 告警文本: 一行一条, 便于直接丢进邮件/机器人。
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
    return "\n".join(lines)
