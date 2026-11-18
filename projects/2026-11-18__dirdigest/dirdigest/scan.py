# 扫描目录生成清单: 相对路径 + 大小 + 修改时间 + (可选)摘要。
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
