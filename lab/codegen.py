"""LLM 代码补全回路: 固定测试 -> 模型写实现 -> pytest -> 失败带错误重试。

设计取舍: 测试由人固定下来, 模型只负责实现。绿了才留, 不绿就删。
这样 LLM 永远不会把不可运行的代码带进公开仓库。
"""
from __future__ import annotations

from pathlib import Path

from . import llm, validate


def _prompt(spec, challenge: dict, feedback: str = "") -> str:
    base = f"""你在为一个 Python 项目补全一个模块。严格遵守:

1. 只输出一个 python 代码块, 不要解释。
2. 只用标准库。
3. 中文注释, 类型标注齐全。
4. 必须让下面这份测试全部通过。

模块: {challenge["target"]}
要求: {challenge["prompt"]}

测试文件内容:
```python
{challenge["tests_content"]}
```
"""
    if feedback:
        base += f"\n上一次实现的 pytest 报错如下, 请修复后重试:\n```\n{feedback[-1500:]}\n```\n"
    return base


def try_challenge(
    spec,
    challenge: dict,
    project_dir: Path,
    python_exe: str,
    cfg: dict,
    log=print,
) -> str:
    """返回结果说明; 失败时清掉挑战文件, 不影响主工程。"""
    target = project_dir / challenge["target"]
    tests = project_dir / challenge["tests"]

    feedback = ""
    for attempt in range(1, int(cfg.get("llm_max_attempts", 2)) + 1):
        log(f"  [llm] 第 {attempt} 次生成 {challenge['target']}")
        try:
            raw = llm.generate(
                _prompt(spec, challenge, feedback),
                model=cfg["ollama_model"],
                base=cfg["ollama_base"],
                timeout=int(cfg.get("llm_timeout_seconds", 180)),
                system="你是严谨的 Python 工程师, 只写可运行代码。",
            )
        except llm.OllamaError as exc:
            log(f"  [llm] 跳过: {exc}")
            break

        code = llm.extract_code(raw)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        tests.parent.mkdir(parents=True, exist_ok=True)
        tests.write_text(challenge["tests_content"], encoding="utf-8")

        ok, out = validate.run_tests(project_dir, python_exe)
        if ok:
            return f"LLM 挑战模块通过（第 {attempt} 次）"
        feedback = out
        log(f"  [llm] 测试未通过, 重试")

    for p in (target, tests):
        if p.exists():
            p.unlink()
    return "LLM 挑战模块未通过, 已丢弃, 只保留主工程"
