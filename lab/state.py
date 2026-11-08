"""运行状态: 记录历史, 保证轮转不重复。"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .config import ROOT

STATE_FILE = ROOT / "state" / "history.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"runs": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _last_seen(state: dict) -> dict[str, str]:
    """slug -> 最近一次的日期字符串。"""
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
    """选一个最久没写过的主题; 全都没写过则按目录顺序取第一个。"""
    today = today or date.today()
    seen = _last_seen(state)
    ranked = sorted(specs, key=lambda s: (seen.get(s.SLUG, ""), s.SLUG))
    chosen = ranked[0]
    # 同日重跑保护: 如果今天是它刚跑过的, 依次往后挪
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
    commit: str | None = None,
    pushed: bool = False,
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
            "commit": commit,
            "pushed": pushed,
            "note": note,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_state(state)
    return state
