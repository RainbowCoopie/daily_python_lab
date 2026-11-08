"""把主题规格落成真实项目目录。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from .config import ROOT

PROJECTS = ROOT / "projects"


def _readme(spec, today: date) -> str:
    notes = "\n".join(f"- {x}" for x in spec.STACK_NOTES)
    tags = " ".join(f"`{t}`" for t in spec.TAGS)
    return f"""# {today.isoformat()} · {spec.TITLE}

> {spec.SUMMARY}

标签: {tags}

## 今天练什么

{notes}

## 目录结构

```
{spec.PKG}/{spec.PKG}/      # 核心实现
{spec.PKG}/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd {spec.PKG}
python -m pytest -q
```

## 设计说明

{spec.NOTES.strip()}

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
"""


def project_name(spec, today: date, pattern: str) -> str:
    return pattern.format(date=today.isoformat(), slug=spec.SLUG)


def write_project(spec, today: date, pattern: str) -> Path:
    """写入项目文件, 返回项目目录。"""
    name = project_name(spec, today, pattern)
    out = PROJECTS / name
    out.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = dict(spec.FILES)
    files["README.md"] = _readme(spec, today)
    files.setdefault("requirements.txt", "# 仅用标准库, 无运行时依赖\n")
    # 放一个根级 conftest.py, 让 pytest 把项目根目录塞进 sys.path
    files.setdefault("conftest.py", "# 空文件: 让 pytest 以项目根目录作为 rootdir 插入 sys.path\n")

    for rel, content in files.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return out


def list_projects() -> list[Path]:
    if not PROJECTS.exists():
        return []
    return sorted([p for p in PROJECTS.iterdir() if p.is_dir()], reverse=True)


def rebuild_index(today: date | None = None) -> Path:
    """按目录名重建 INDEX.md。"""
    from .catalog import load_specs

    by_slug = {s.SLUG: s for s in load_specs()}
    rows = []
    for p in list_projects():
        name = p.name
        if "__" not in name:
            continue
        d, slug = name.split("__", 1)
        spec = by_slug.get(slug)
        title = spec.TITLE if spec else slug
        tags = " · ".join(spec.TAGS) if spec else ""
        rows.append(f"| {d} | [{title}](./projects/{name}) | {tags} |")

    header = (
        "# Daily Python Lab · 索引\n\n"
        "每个工作日在本地 ollama 辅助下生成一个小而完整的 Python 工程，"
        "编译与测试全绿后才提交。技术栈覆盖 CPython / FastAPI / 爬虫 / RPA / LLM / CV 标注。\n\n"
        "| 日期 | 项目 | 技术点 |\n|---|---|---|\n"
    )
    body = "\n".join(rows) if rows else "| - | 还没有生成任何项目 | - |"
    total = len(rows)
    text = header + body + f"\n\n---\n\n共 {total} 个项目。最近更新: {(today or date.today()).isoformat()}\n"

    out = ROOT / "INDEX.md"
    out.write_text(text, encoding="utf-8")
    return out
