"""命令行入口: python -m lab <command>"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date
from pathlib import Path

from . import catalog, codegen, publish, scaffold, state as statemod, validate
from .config import ROOT, load_config, read_token

VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"


def python_exe() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def log(msg: str) -> None:
    print(msg, flush=True)


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config()
    token = read_token()
    py = python_exe()
    today = date.fromisoformat(args.date) if args.date else date.today()

    if not args.no_push and not token:
        log("缺少 GITHUB_TOKEN, 无法推送。用 --no-push 可以先本地跑通。")
        return 2

    st = statemod.load_state()
    specs = catalog.load_specs()
    spec = catalog.by_slug(args.slug) if args.slug else statemod.pick_topic(specs, st, today)

    log(f"[1/6] 选题: {spec.SLUG} — {spec.TITLE}")
    project = scaffold.write_project(spec, today, cfg["project_dir_pattern"])
    log(f"      生成: {project.relative_to(ROOT)}")

    note = ""
    challenge = getattr(spec, "CHALLENGE", None)
    if challenge and args.llm and cfg.get("llm_enabled"):
        log("[2/6] LLM 挑战模块（显式开启，会占用本机显卡）")
        note = codegen.try_challenge(spec, challenge, project, py, cfg, log=log)
        log(f"      {note}")
    else:
        log("[2/6] 纯模板生成（不调用任何模型）")

    log("[3/6] 闸门: compileall + 密钥扫描 + pytest")
    try:
        summary = validate.gate(project, py, token)
    except validate.ValidationError as exc:
        log(f"      闸门未通过, 中止发布:\n{exc}")
        statemod.record_run(
            st, slug=spec.SLUG, project=project.name, status="failed", note=str(exc)[:500], today=today
        )
        return 1
    last_line = summary.splitlines()[-1] if summary else "ok"
    log(f"      {last_line}")

    log("[4/6] 重建索引")
    index = scaffold.rebuild_index(today)
    log(f"      {index.relative_to(ROOT)}")

    statemod.record_run(
        st, slug=spec.SLUG, project=project.name, status="ok", note=note, today=today
    )

    if args.no_push:
        log("[5/6] --no-push: 不提交")
        log("[6/6] 完成（本地）")
        return 0

    log("[5/6] 提交")
    bootstrap = not (ROOT / ".git").exists()
    if bootstrap:
        message = (
            f"init: daily_python_lab 流水线 + 首个项目 {spec.TITLE}\n\n"
            f"- 每天生成一个测试全绿的 Python 小工程并自动推送\n"
            f"- 首个项目 slug: {spec.SLUG}\n"
            f"- 验收: compileall + pytest 全绿\n"
            f"- {note or '纯模板生成'}"
        )
    else:
        message = (
            f"day {today.isoformat()}: {spec.TITLE}\n\n"
            f"- slug: {spec.SLUG}\n"
            f"- 技术点: {', '.join(spec.TAGS)}\n"
            f"- 验收: compileall + pytest 全绿\n"
            f"- {note or '纯模板生成'}"
        )
    try:
        publish.ensure_repo(cfg, token)
        # 首次提交把流水线自身也带上; 之后每天只提交当天项目与索引
        stage = None if bootstrap else [project, index]
        sha = publish.commit_paths(cfg, token, ROOT, message, stage)
        if not sha:
            log("      没有变更可提交")
            return 0
        st["runs"][-1]["commit"] = sha
        st["runs"][-1]["pushed"] = True
        statemod.save_state(st)
        sha = publish.amend_paths(cfg, token, ROOT, [statemod.STATE_FILE], sha)
        log(f"      commit {sha}")
        publish.push(cfg, token, ROOT)
        log(f"      已推送 -> https://github.com/{cfg['owner']}/{cfg['repo']}")
    except publish.PublishError as exc:
        log(f"      发布失败: {exc}")
        return 1

    log("[6/6] 完成")
    return 0


def cmd_dry(args: argparse.Namespace) -> int:
    args.no_push = True
    return cmd_run(args)


def cmd_status(args: argparse.Namespace) -> int:
    st = statemod.load_state()
    runs = st.get("runs", [])
    if not runs:
        log("还没有运行记录")
        return 0
    log(f"共 {len(runs)} 次运行, 最近 {min(args.n, len(runs))} 条:\n")
    for r in runs[-args.n :]:
        flag = "OK  " if r["status"] == "ok" else "FAIL"
        log(
            f"{flag} {r['date']}  {r['slug']:<22} {r.get('project',''):<34}"
            f" {r.get('commit') or '-':<9} {'pushed' if r.get('pushed') else ''}"
        )
        if r.get("note"):
            log(f"       {r['note'][:120]}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    p = scaffold.rebuild_index()
    log(f"已重建 {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lab", description="每日 Python 工程流水线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, fn, helptext in (
        ("run", cmd_run, "完整跑一遍: 生成 + 校验 + 提交推送"),
        ("dry", cmd_dry, "只生成 + 校验, 不提交"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--slug", help="指定主题 slug")
        p.add_argument("--date", help="指定日期 YYYY-MM-DD (默认今天)")
        p.add_argument(
            "--llm",
            action="store_true",
            help="额外用本地 ollama 补全挑战模块（会占用显卡，默认关闭）",
        )
        if name == "run":
            p.add_argument("--no-push", action="store_true", help="只提交到本地, 不推送")
        p.set_defaults(func=fn)

    p = sub.add_parser("status", help="查看运行记录")
    p.add_argument("-n", type=int, default=15)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("index", help="重建 INDEX.md")
    p.set_defaults(func=cmd_index)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception:  # noqa: BLE001 - CLI 兜底, 保证定时任务有日志
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
