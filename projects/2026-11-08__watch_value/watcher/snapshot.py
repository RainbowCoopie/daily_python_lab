# 快照: 规范化 + 摘要 + 落盘。
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
