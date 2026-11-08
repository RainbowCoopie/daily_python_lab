"""生成结果的验收闸门: 能跑、能测、不含密钥。

任何一项不过, 当天就中止发布, 不把垃圾推到公开仓库。
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"ghp_[0-9A-Za-z]{30,}"),
    re.compile(r"github_pat_[0-9A-Za-z_]{30,}"),
    re.compile(r"gho_[0-9A-Za-z]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".cfg", ".ini", ".yml", ".yaml", ".ps1", ".sh"}


class ValidationError(RuntimeError):
    pass


def secret_scan(paths: list[Path], extra_secret: str | None = None) -> list[str]:
    """扫描待提交文件里是否混进了 token。"""
    hits: list[str] = []
    for p in paths:
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(content):
                hits.append(f"{p}: 命中密钥模式 {pat.pattern}")
        if extra_secret and extra_secret in content:
            hits.append(f"{p}: 含真实 token 字符串")
    return hits


def _decode(proc: subprocess.CompletedProcess) -> str:
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def compile_check(project_dir: Path, python_exe: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [python_exe, "-m", "compileall", "-q", str(project_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return proc.returncode == 0, _decode(proc)


def run_tests(project_dir: Path, python_exe: str) -> tuple[bool, str]:
    """在项目目录下跑 pytest。没有测试用例也算失败——每天至少要有可验证的东西。"""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [python_exe, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        env=env,
    )
    out = _decode(proc)
    if proc.returncode == 5:  # no tests collected
        return False, "没有收集到任何测试用例\n" + out
    return proc.returncode == 0, out


def gate(project_dir: Path, python_exe: str, token: str | None) -> str:
    """全部闸门跑一遍, 失败抛 ValidationError。返回 pytest 摘要。"""
    ok, out = compile_check(project_dir, python_exe)
    if not ok:
        raise ValidationError(f"compileall 失败:\n{out}")

    files = [p for p in project_dir.rglob("*") if p.is_file()]
    hits = secret_scan(files, extra_secret=token)
    if hits:
        raise ValidationError("密钥扫描未通过:\n" + "\n".join(hits))

    ok, out = run_tests(project_dir, python_exe)
    if not ok:
        raise ValidationError(f"pytest 失败:\n{out[-4000:]}")
    return out
