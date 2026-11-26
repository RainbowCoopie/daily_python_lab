# 错误报告: 给人读的形态。
from __future__ import annotations

from .rules import Issue


def format_issues(issues: list[Issue], title: str = "配置校验") -> str:
    if not issues:
        return f"【{title}】通过"
    lines = [f"【{title}】发现 {len(issues)} 个问题"]
    lines.extend(f"- {issue.render()}" for issue in issues)
    return "\n".join(lines)
