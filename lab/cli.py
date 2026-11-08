"""命令行入口: python -m lab <command>

run      从主题库生成一个项目 -> 闸门 -> 提交推送
publish  把工作区当前所有改动(新增/维护/重构)过闸门后提交推送
dry      只生成 + 校验, 不提交
status   看运行记录
index    重建 INDEX.md
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date

from . import catalog, codegen, publish, scaffold, state as statemod, validate
from .config import ROOT, load_config, read_token

VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"


def python_exe() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def log(msg: str) -> None:
    print(msg, flush=True)


def _gate_all(token: str | None) -> list[tuple[str, str]]:
    """对所有已生成项目跑一遍闸门, 返回失败清单。"""
    py = python_exe()
    failures: list[tuple[str, str]] = []
    for project in scaffold.list_projects():
        try:
            validate.gate(project, py, token)
        except validate.ValidationError as exc:
            failures.append((project.name, str(exc)[:400]))
    return failures


def _publish(cfg: dict, token: str, message: str, paths) -> int:
    try:
        publish.ensure_repo(cfg, token)
        sha = publish.commit_paths(cfg, token, ROOT, message, paths)
        if not sha:
            log("      没有变更可提交")
            return 0
        statemod.record_commit(sha, message)
        log(f"      commit {sha}")
        publish.push(cfg, token, ROOT)
        log(f"      已推送 -> https://github.com/{cfg['owner']}/{cfg['repo']}")
        return 0
    except publish.PublishError as exc:
        log(f"      发布失败: {exc}")
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config()
    token = read_token()
    py = python_exe()
    today = date.fromisoformat(args.date) if args.date else date.today()

    if not args.no_push and not token:
        log("缺少 GITHUB_TOKEN, 无法推送。用 --no-push 可以先本地跑通。")
        return 2

    st = statemod.load_state()
    if getattr(args, "if_idle", False) and statemod.ran_today(st, today):
        log(f"今天({today})已有成功运行, --if-idle 跳过")
        return 0

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
    log(f"      {summary.splitlines()[-1] if summary else 'ok'}")

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
        paths = None
    else:
        message = (
            f"day {today.isoformat()}: {spec.TITLE}\n\n"
            f"- slug: {spec.SLUG}\n"
            f"- 技术点: {', '.join(spec.TAGS)}\n"
            f"- 验收: compileall + pytest 全绿\n"
            f"- {note or '纯模板生成'}"
        )
        # 当天项目 + 索引 + 流水线源码(新主题模块就在 lab/ 里) + 运行日志
        paths = [project, index, statemod.STATE_FILE, ROOT / "lab"]

    code = _publish(cfg, token, message, paths)
    if code == 0:
        log("[6/6] 完成")
    return code


def cmd_publish(args: argparse.Namespace) -> int:
    """维护 / 修复 / 重构后的通用发布口: 全仓库过闸门, 再提交当前所有改动。"""
    cfg = load_config()
    token = read_token()
    if not token and not args.no_push:
        log("缺少 GITHUB_TOKEN")
        return 2

    log("[1/3] 闸门: 扫描所有项目")
    failures = _gate_all(token)
    if failures:
        for name, err in failures:
            log(f"      失败 {name}:\n{err}")
        log("      有项目未通过, 中止发布")
        return 1
    log(f"      {len(scaffold.list_projects())} 个项目全部通过")

    log("[2/3] 重建索引")
    index = scaffold.rebuild_index()
    log(f"      {index.relative_to(ROOT)}")

    if args.no_push:
        log("[3/3] --no-push: 不提交")
        return 0

    log("[3/3] 提交")
    return _publish(cfg, token, args.message, None)


def cmd_dry(args: argparse.Namespace) -> int:
    args.no_push = True
    return cmd_run(args)


def cmd_status(args: argparse.Namespace) -> int:
    st = statemod.load_state()
    runs = st.get("runs", [])
    commits = statemod.load_local().get("commits", [])
    if not runs:
        log("还没有运行记录")
        return 0
    log(f"共 {len(runs)} 次运行, 最近 {min(args.n, len(runs))} 条:\n")
    for r in runs[-args.n :]:
        flag = "OK  " if r["status"] == "ok" else "FAIL"
        log(f"{flag} {r['date']}  {r['slug']:<22} {r.get('project','')}")
        if r.get("note"):
            log(f"       {r['note'][:120]}")
    if commits:
        log(f"\n最近提交: {commits[-1]['sha']}  {commits[-1]['message']}")
    return 0


def cmd_topics(args: argparse.Namespace) -> int:
    """看主题库使用情况, 决定今天写新的还是维护旧的。"""
    st = statemod.load_state()
    specs = catalog.load_specs()
    seen = {}
    for r in st.get("runs", []):
        if r.get("status") == "ok":
            seen[r["slug"]] = max(seen.get(r["slug"], ""), r["date"])
    log(f"主题库共 {len(specs)} 个, 已生成 {len(seen)} 个\n")
    for s in sorted(specs, key=lambda x: (seen.get(x.SLUG, ""), x.SLUG)):
        used = seen.get(s.SLUG)
        log(f"{'  ' if used else 'NEW'} {s.SLUG:<22} {s.TITLE:<24} {used or '未写过'}")
    log("\n未写过 = 可直接用 run --slug; 全部写过 = 该写新主题或维护旧项目了")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    p = scaffold.rebuild_index()
    log(f"已重建 {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lab", description="每日 Python 工程流水线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, fn, helptext in (
        ("run", cmd_run, "从主题库生成一个项目: 生成 + 校验 + 提交推送"),
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
            p.add_argument("--if-idle", action="store_true", help="今天已有成功运行则直接跳过")
        p.set_defaults(func=fn)

    p = sub.add_parser("publish", help="维护/修复后发布: 全项目过闸门 + 提交所有改动")
    p.add_argument("-m", "--message", required=True, help="commit message")
    p.add_argument("--no-push", action="store_true")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("status", help="查看运行记录")
    p.add_argument("-n", type=int, default=15)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("topics", help="查看主题库使用情况")
    p.set_defaults(func=cmd_topics)

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
