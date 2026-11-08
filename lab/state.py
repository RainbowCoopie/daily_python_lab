"""运行状态: 记录历史, 保证轮转与幂等。

`state/history.json` 会进仓库(作为工作日志), 因此**不写入 commit sha** ——
内含自身 commit 哈希会造成 amend 死循环。sha 记在 `state/local.json`, 该文件被 gitignore。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .config import ROOT

STATE_FILE = ROOT / "state" / "history.json"
LOCAL_FILE = ROOT / "state" / "local.json"


def _read(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return default


def load_state() -> dict:
    return _read(STATE_FILE, {"runs": []})


def load_local() -> dict:
    return _read(LOCAL_FILE, {"commits": []})


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_local(local: dict) -> None:
    LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_FILE.write_text(json.dumps(local, ensure_ascii=False, indent=2), encoding="utf-8")


def ran_today(state: dict, today: date | None = None) -> bool:
    today = today or date.today()
    return any(
        r.get("date") == today.isoformat() and r.get("status") == "ok"
        for r in state.get("runs", [])
    )


def _last_seen(state: dict) -> dict[str, str]:
    seen: dict[str, str] = {}
    for run in state.get("runs", []):
        if run.get("status") != "ok":
            continue
        slug = run.get("slug")
        d = run.get("date", "")
        if slug and d >= seen.get(slug, ""):
            seen[slug] = d
    return seen


def pick_topic(specs: list, state: dict, today: date | None = None) -> object:
    """选一个最久没写过的主题; 全都没写过则按 slug 顺序取第一个。"""
    today = today or date.today()
    seen = _last_seen(state)
    ranked = sorted(specs, key=lambda s: (seen.get(s.SLUG, ""), s.SLUG))
    chosen = ranked[0]
    if seen.get(chosen.SLUG) == today.isoformat():
        later = [s for s in ranked if seen.get(s.SLUG) != today.isoformat()]
        if later:
            chosen = later[0]
    return chosen


def record_run(
    state: dict,
    *,
    slug: str,
    project: str,
    status: str,
    note: str = "",
    today: date | None = None,
) -> dict:
    today = today or date.today()
    state.setdefault("runs", []).append(
        {
            "date": today.isoformat(),
            "slug": slug,
            "project": project,
            "status": status,
            "note": note,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_state(state)
    return state


def record_commit(sha: str, message: str) -> None:
    local = load_local()
    local.setdefault("commits", []).append(
        {
            "at": datetime.now().isoformat(timespec="seconds"),
            "sha": sha,
            "message": message.splitlines()[0] if message else "",
        }
    )
    save_local(local)
