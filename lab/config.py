"""配置与密钥装载。

密钥优先级: 环境变量 GITHUB_TOKEN > %USERPROFILE%\\.dsh\\secrets\\github_token.txt
永远不会写入仓库, 也不会被 print 出来。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"
SECRET_FILE = Path.home() / ".dsh" / "secrets" / "github_token.txt"

_DEFAULTS = {
    "owner": "RainbowCoopie",
    "repo": "daily_python_lab",
    "branch": "main",
    "repo_description": "Daily Python engineering drills.",
    "author_name": "RainbowCoopie",
    "author_email": "18080862606@163.com",
    "ollama_base": "http://127.0.0.1:11434",
    "ollama_model": "deepseek-14b",
    "llm_enabled": True,
    "llm_timeout_seconds": 180,
    "llm_max_attempts": 2,
    "project_dir_pattern": "{date}__{slug}",
}


def load_config() -> dict:
    cfg = dict(_DEFAULTS)
    if CONFIG_FILE.exists():
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    return cfg


def read_token() -> str | None:
    """读取 GitHub token; 找不到返回 None。"""
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env and env.strip():
        return env.strip()
    if SECRET_FILE.exists():
        tok = SECRET_FILE.read_text(encoding="utf-8").strip()
        return tok or None
    return None


def write_token(token: str) -> Path:
    """把 token 写到用户目录下的受限文件（不落在仓库里）。"""
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(token.strip() + "\n", encoding="utf-8")
    return SECRET_FILE


def redact(text: str, token: str | None) -> str:
    if token:
        text = text.replace(token, "***REDACTED***")
    return text
