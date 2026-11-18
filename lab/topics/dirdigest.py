'''目录清单对账: 扫描 -> 摘要 -> 比对, 分别报出新增/删除/修改/改名/移动。

灵感来源:
- digup 的定位: 维护一份摘要文件, 跑完之后告诉你哪些文件 new/updated/modified/renamed/deleted
  (https://manpages.debian.org/unstable/digup/digup.1.en.html)
- rsync 的默认取舍: 平时只比 大小 + 修改时间(quick check), 加 -c 才逐文件算校验和
  (https://cloud.tencent.cn/developer/ask/sof/117165580) —— 这个"快检 vs 严格"的分层直接抄进接口
- shatag 用 xattr 缓存 SHA-256, 说明摘要值天然可以跨路径复用
  (https://manpages.org/shatag/1)

为什么值得单独做一层: 归档、备份、交付这三类活每天都要回答同一个问题 ——
"这两份东西到底差在哪"。只比文件名会漏掉内容被改, 只比内容会把"改名"误报成"删一个加一个"。
真正的难点是**用内容摘要把改名和移动认出来**, 而这正是纯字符串比对做不到的部分。
'''

SLUG = "dirdigest"
TITLE = "目录清单对账（新增/删除/修改/改名/移动）"
TAGS = ["文件清单", "SHA-256", "改名检测", "归档校验"]
PKG = "dirdigest"
SUMMARY = "扫描目录生成摘要清单, 比对两份清单并用内容指纹认出改名与移动, 而不是误报成删除加新增。"
STACK_NOTES = [
    "两种模式: fast 只记大小与时间, strict 才算 SHA-256 —— 对应 rsync 的 quick check 与 -c",
    "改名/移动靠摘要反查: 同摘要、同目录算改名, 同摘要、跨目录算移动, 一对一配对",
    "清单可存成 JSON 再读回, 于是'上周的归档'和'这周的交付'能直接对账",
]
NOTES = """
判定的优先级是**先认内容, 再谈路径**:

1. 路径两边都有 → 比摘要(或大小+时间), 不同就是"修改"。
2. 路径只在旧清单里 / 只在新清单里 → 先挂起, 不急着报增删。
3. 对挂起的部分按摘要配对: 旧清单里消失的 a 和新清单里出现的 b 摘要相同,
   就判定为改名(同目录)或移动(跨目录)。配完对剩下的才真正算"删除"和"新增"。

这条顺序很关键。反过来(先报增删再想办法补救)会把一次改名说成"删了 1 个、加了 1 个",
对账的人得自己脑补。而重复文件(多个文件内容相同)配对时按路径排序一对一,
保证同样的输入永远得到同样的报告 —— 报告能进 git 才行。
"""

FILES = {
    "dirdigest/__init__.py": '''from .compare import Changes, diff, format_report
from .scan import Entry, load, save, scan

__all__ = ["Entry", "scan", "save", "load", "Changes", "diff", "format_report"]
''',
    "dirdigest/scan.py": '''# 扫描目录生成清单: 相对路径 + 大小 + 修改时间 + (可选)摘要。
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_IGNORE = (".git", "__pycache__", ".pytest_cache", ".venv")
CHUNK = 1 << 20


@dataclass(frozen=True)
class Entry:
    path: str
    size: int
    mtime_ns: int
    digest: str | None = None


def file_digest(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            sha.update(block)
    return sha.hexdigest()


def scan(
    root: str | Path,
    *,
    strict: bool = True,
    ignore: tuple[str, ...] = DEFAULT_IGNORE,
) -> dict[str, Entry]:
    """扫描目录。strict=True 时计算 SHA-256, 否则只记大小与时间(对应 rsync 的 quick check)。"""
    base = Path(root)
    if not base.is_dir():
        raise NotADirectoryError(str(root))
    entries: dict[str, Entry] = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if any(part in ignore for part in rel.parts):
            continue
        stat = path.stat()
        entries[rel.as_posix()] = Entry(
            path=rel.as_posix(),
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            digest=file_digest(path) if strict else None,
        )
    return entries


def save(entries: dict[str, Entry], path: str | Path) -> None:
    payload = {"version": 1, "files": [asdict(entry) for _, entry in sorted(entries.items())]}
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: str | Path) -> dict[str, Entry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {item["path"]: Entry(**item) for item in data.get("files", [])}
''',
    "dirdigest/compare.py": '''# 比对两份清单: 先认内容, 再谈路径。
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
    return "\\n".join(lines)
''',
    "tests/test_scan.py": '''from pathlib import Path

import pytest

from dirdigest import Entry, load, save, scan


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"\\x00\\x01\\x02")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "junk.pyc").write_bytes(b"x")
    return tmp_path


def test_scan_collects_files(tree: Path) -> None:
    entries = scan(tree)
    assert sorted(entries) == ["a.txt", "sub/b.bin"]


def test_scan_skips_ignored_dirs(tree: Path) -> None:
    assert all("__pycache__" not in path for path in scan(tree))


def test_scan_records_size_and_digest(tree: Path) -> None:
    entry = scan(tree)["a.txt"]
    assert entry.size == 5
    assert entry.digest is not None
    assert len(entry.digest) == 64


def test_digest_is_stable(tree: Path) -> None:
    assert scan(tree)["a.txt"].digest == scan(tree)["a.txt"].digest


def test_fast_mode_skips_digest(tree: Path) -> None:
    entries = scan(tree, strict=False)
    assert entries["a.txt"].digest is None
    assert entries["a.txt"].size == 5


def test_identical_content_same_digest(tmp_path: Path) -> None:
    (tmp_path / "x").write_text("same", encoding="utf-8")
    (tmp_path / "y").write_text("same", encoding="utf-8")
    entries = scan(tmp_path)
    assert entries["x"].digest == entries["y"].digest


def test_scan_rejects_non_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "f.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        scan(file_path)


def test_save_and_load_roundtrip(tree: Path, tmp_path: Path) -> None:
    entries = scan(tree)
    out = tmp_path / "manifest.json"
    save(entries, out)
    restored = load(out)
    assert restored == entries


def test_saved_manifest_is_sorted(tree: Path, tmp_path: Path) -> None:
    out = tmp_path / "manifest.json"
    save(scan(tree), out)
    body = out.read_text(encoding="utf-8")
    assert body.index("a.txt") < body.index("sub/b.bin")


def test_entry_is_immutable() -> None:
    entry = Entry(path="a", size=1, mtime_ns=2, digest=None)
    with pytest.raises(Exception):
        entry.size = 3  # type: ignore[misc]
''',
    "tests/test_compare.py": '''from pathlib import Path

import pytest

from dirdigest import diff, format_report, scan


def make(tmp_path: Path, name: str, files: dict[str, str], *, strict: bool = True) -> dict:
    root = tmp_path / name
    root.mkdir()
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return scan(root, strict=strict)


def test_no_change(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    after = make(tmp_path, "v2", {"a.txt": "x"})
    changes = diff(before, after)
    assert changes.is_empty is True
    assert changes.total == 0


def test_added_and_removed(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    after = make(tmp_path, "v2", {"b.txt": "y"})
    changes = diff(before, after)
    assert changes.added == ["b.txt"]
    assert changes.removed == ["a.txt"]


def test_modified(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    after = make(tmp_path, "v2", {"a.txt": "xx"})
    changes = diff(before, after)
    assert changes.modified == ["a.txt"]
    assert changes.added == [] and changes.removed == []


def test_rename_same_directory(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "same"})
    after = make(tmp_path, "v2", {"b.txt": "same"})
    changes = diff(before, after)
    assert changes.renamed == [("a.txt", "b.txt")]
    assert changes.added == [] and changes.removed == []


def test_move_across_directories(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "same"})
    after = make(tmp_path, "v2", {"sub/a.txt": "same"})
    changes = diff(before, after)
    assert changes.moved == [("a.txt", "sub/a.txt")]


def test_content_change_is_not_a_rename(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "one"})
    after = make(tmp_path, "v2", {"b.txt": "two"})
    changes = diff(before, after)
    assert changes.renamed == []
    assert changes.added == ["b.txt"]
    assert changes.removed == ["a.txt"]


def test_duplicate_content_pairs_one_to_one(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "dup", "b.txt": "dup"})
    after = make(tmp_path, "v2", {"c.txt": "dup"})
    changes = diff(before, after)
    assert len(changes.renamed) == 1
    assert len(changes.removed) == 1


def test_report_empty(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"})
    assert "没有变化" in format_report(diff(before, before))


def test_report_lines(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"keep.txt": "k", "gone.txt": "old-content", "edit.txt": "v1"})
    after = make(tmp_path, "v2", {"keep.txt": "k", "fresh.txt": "new-content", "edit.txt": "v2"})
    text = format_report(diff(before, after))
    lines = text.splitlines()
    assert lines[0].startswith("【清单比对】共 3 处变化")
    assert "+ fresh.txt" in lines
    assert "- gone.txt" in lines
    assert "~ edit.txt" in lines


def test_two_different_files_never_pair_as_rename(tmp_path: Path) -> None:
    """摘要不同就不能配成改名, 否则会把"改内容 + 换名字"误报告成一次改名。"""
    before = make(tmp_path, "v1", {"a.txt": "one"})
    after = make(tmp_path, "v2", {"b.txt": "two"})
    text = format_report(diff(before, after))
    assert "R a.txt -> b.txt" not in text


def test_fast_mode_detects_size_change(tmp_path: Path) -> None:
    before = make(tmp_path, "v1", {"a.txt": "x"}, strict=False)
    after = make(tmp_path, "v2", {"a.txt": "xxx"}, strict=False)
    assert diff(before, after).modified == ["a.txt"]


def test_fast_mode_cannot_detect_rename(tmp_path: Path) -> None:
    """fast 模式没有摘要, 改名只能退化报成 删除 + 新增 —— 这就是它快的代价。"""
    before = make(tmp_path, "v1", {"a.txt": "same"}, strict=False)
    after = make(tmp_path, "v2", {"b.txt": "same"}, strict=False)
    changes = diff(before, after)
    assert changes.renamed == []
    assert changes.added == ["b.txt"]
    assert changes.removed == ["a.txt"]
''',
}

CHALLENGE = {
    "target": "dirdigest/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 dirdigest/challenge.py 中实现 summary_line(changes) -> str: "
        "用 dirdigest.compare 的 Changes, 返回形如 "
        "'新增 1 删除 0 修改 0 改名 1 移动 0' 的单行摘要; 变化为空时返回 '无变化'。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from dirdigest import Changes
from dirdigest.challenge import summary_line


def test_empty() -> None:
    assert summary_line(Changes()) == "无变化"


def test_counts() -> None:
    changes = Changes(added=["a"], renamed=[("x", "y")])
    assert summary_line(changes) == "新增 1 删除 0 修改 0 改名 1 移动 0"
''',
}
