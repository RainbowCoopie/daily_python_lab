# 比对两份清单: 先认内容, 再谈路径。
from __future__ import annotations

import posixpath
from dataclasses import dataclass, field

from .scan import Entry


@dataclass
class Changes:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)
    moved: list[tuple[str, str]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.modified or self.renamed or self.moved)

    @property
    def total(self) -> int:
        return (
            len(self.added)
            + len(self.removed)
            + len(self.modified)
            + len(self.renamed)
            + len(self.moved)
        )


def _changed(old: Entry, new: Entry) -> bool:
    if old.digest is not None and new.digest is not None:
        return old.digest != new.digest
    return old.size != new.size or old.mtime_ns != new.mtime_ns


def diff(old: dict[str, Entry], new: dict[str, Entry]) -> Changes:
    old_paths, new_paths = set(old), set(new)
    changes = Changes(
        added=sorted(new_paths - old_paths),
        removed=sorted(old_paths - new_paths),
        modified=sorted(
            path for path in old_paths & new_paths if _changed(old[path], new[path])
        ),
    )

    # 按摘要把"消失的"和"出现的"配成对, 剩下的才算真增删
    gone_by_digest: dict[str, list[str]] = {}
    for path in changes.removed:
        digest = old[path].digest
        if digest:
            gone_by_digest.setdefault(digest, []).append(path)

    came_by_digest: dict[str, list[str]] = {}
    for path in changes.added:
        digest = new[path].digest
        if digest:
            came_by_digest.setdefault(digest, []).append(path)

    matched_old: set[str] = set()
    matched_new: set[str] = set()
    for digest in sorted(set(gone_by_digest) & set(came_by_digest)):
        for before, after in zip(gone_by_digest[digest], came_by_digest[digest]):
            matched_old.add(before)
            matched_new.add(after)
            pair = (before, after)
            if posixpath.dirname(before) == posixpath.dirname(after):
                changes.renamed.append(pair)
            else:
                changes.moved.append(pair)

    changes.removed = [p for p in changes.removed if p not in matched_old]
    changes.added = [p for p in changes.added if p not in matched_new]
    changes.renamed.sort()
    changes.moved.sort()
    return changes


def format_report(changes: Changes, title: str = "清单比对") -> str:
    if changes.is_empty:
        return f"【{title}】没有变化"
    lines = [
        f"【{title}】共 {changes.total} 处变化 "
        f"(新增 {len(changes.added)} / 删除 {len(changes.removed)} / "
        f"修改 {len(changes.modified)} / 改名 {len(changes.renamed)} / 移动 {len(changes.moved)})"
    ]
    lines.extend(f"+ {path}" for path in changes.added)
    lines.extend(f"- {path}" for path in changes.removed)
    lines.extend(f"~ {path}" for path in changes.modified)
    lines.extend(f"R {before} -> {after}" for before, after in changes.renamed)
    lines.extend(f"M {before} -> {after}" for before, after in changes.moved)
    return "\n".join(lines)
