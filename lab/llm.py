"""本地 ollama 客户端（只用标准库 urllib，无第三方依赖）。"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> str:
    """去掉推理模型吐出的 <think> 段。"""
    text = _THINK.sub("", text)
    # 未闭合的情况: 截到最后一次 <｜end▁of▁thinking｜> 之后
    if "<｜end▁of▁thinking｜>" in text:
        text = text.split("<｜end▁of▁thinking｜>")[-1]
    return text.strip()


def extract_code(text: str) -> str:
    """从模型输出里取出第一个 python 代码块。"""
    text = strip_think(text)
    fenced = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced[0].strip() + "\n"
    return text.strip() + "\n"


class OllamaError(RuntimeError):
    pass


def generate(
    prompt: str,
    *,
    model: str,
    base: str,
    timeout: int = 180,
    system: str | None = None,
) -> str:
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 900},
    }
    if system:
        payload["system"] = system
    req = urllib.request.Request(
        f"{base.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OllamaError(f"ollama 调用失败: {exc}") from exc
    out = data.get("response", "")
    if not out.strip():
        raise OllamaError("ollama 返回空内容")
    return strip_think(out)
