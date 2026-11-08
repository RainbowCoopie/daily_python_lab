"""Git / GitHub 发布层。

token 只出现在 push 的 URL 参数里, 不写进 .git/config, 不进日志。
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .config import redact

API = "https://api.github.com"


class PublishError(RuntimeError):
    pass


def _api(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "daily-python-lab",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed


def whoami(token: str) -> dict:
    status, data = _api("GET", "/user", token)
    if status != 200:
        raise PublishError(f"token 无效或权限不足 (HTTP {status}): {data}")
    return data


def ensure_repo(cfg: dict, token: str) -> str:
    """仓库不存在就用 API 建一个空的。返回一句人话状态。"""
    owner, repo = cfg["owner"], cfg["repo"]
    status, data = _api("GET", f"/repos/{owner}/{repo}", token)
    if status == 200:
        return f"仓库已存在: {data.get('full_name')}"
    if status != 404:
        raise PublishError(f"查询仓库失败 (HTTP {status}): {data}")
    status, data = _api(
        "POST",
        "/user/repos",
        token,
        {
            "name": repo,
            "description": cfg.get("repo_description", ""),
            "private": False,
            "has_issues": True,
            "has_wiki": False,
            "auto_init": False,
        },
    )
    if status not in (201, 422):  # 422 = 已存在, 并发时会出现
        raise PublishError(f"创建仓库失败 (HTTP {status}): {data}")
    return f"仓库已创建: {owner}/{repo}"


def _git(args: list[str], cwd: Path, token: str | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise PublishError(redact(f"git {' '.join(args[:2])} 失败:\n{out}", token))
    return out


def remote_has_commits(cfg: dict, token: str) -> bool:
    url = f"https://{cfg['owner']}:{token}@github.com/{cfg['owner']}/{cfg['repo']}.git"
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if proc.returncode != 0:
        raise PublishError(redact(f"ls-remote 失败:\n{proc.stderr}", token))
    return bool((proc.stdout or "").strip())


def init_repo(cfg: dict, root: Path, token: str) -> None:
    git_dir = root / ".git"
    if git_dir.exists():
        return
    if remote_has_commits(cfg, token):
        raise PublishError(
            f"远端 {cfg['owner']}/{cfg['repo']} 已有提交, 但本地 {root} 没有 git 历史。"
            "请先把远端 clone 下来, 否则会把历史顶掉。"
        )
    _git(["init", "-b", cfg.get("branch", "main")], root)
    _git(["remote", "add", "origin", f"https://github.com/{cfg['owner']}/{cfg['repo']}.git"], root)


def _identity(cfg: dict) -> list[str]:
    return [
        "-c",
        f"user.name={cfg.get('author_name', 'bot')}",
        "-c",
        f"user.email={cfg.get('author_email', 'bot@example.com')}",
    ]


def _rel(root: Path, paths: list[Path]) -> list[str]:
    return [str(p.relative_to(root)) for p in paths]


def commit_paths(
    cfg: dict, token: str, root: Path, message: str, paths: list[Path] | None = None
) -> str | None:
    """暂存指定路径并提交, 返回短 hash; 没有变更返回 None。"""
    init_repo(cfg, root, token)
    _git(["add", "--", *(_rel(root, paths) if paths else ["."])], root, token)
    if not _git(["diff", "--cached", "--name-only"], root, token).strip():
        return None
    _git([*_identity(cfg), "commit", "-m", message], root, token)
    return _git(["rev-parse", "--short", "HEAD"], root, token).strip()


def amend_paths(cfg: dict, token: str, root: Path, paths: list[Path], sha: str) -> str:
    """把刚写出的状态文件并进同一个 commit, 避免一天两条噪声提交。"""
    _git(["add", "--", *_rel(root, paths)], root, token)
    _git([*_identity(cfg), "commit", "--amend", "--no-edit"], root, token)
    return _git(["rev-parse", "--short", "HEAD"], root, token).strip() or sha


def push(cfg: dict, token: str, root: Path) -> None:
    branch = cfg.get("branch", "main")
    url = f"https://{cfg['owner']}:{token}@github.com/{cfg['owner']}/{cfg['repo']}.git"
    _git(["push", url, f"HEAD:{branch}"], root, token)


def commit_and_push(
    cfg: dict,
    token: str,
    root: Path,
    message: str,
    paths: list[Path] | None = None,
) -> tuple[str, bool]:
    """提交并推送。返回 (commit hash, 是否推送成功)。"""
    sha = commit_paths(cfg, token, root, message, paths)
    if not sha:
        return "", False
    push(cfg, token, root)
    return sha, True
