'''RPA 流程的声明式骨架: 把"步骤 / 重试 / 出错怎么办"从键鼠脚本里抽出来, 用假执行器就能测。'''

SLUG = "rpa_taskflow"
TITLE = "RPA 流程编排 DSL"
TAGS = ["RPA", "流程编排", "重试策略", "可测设计"]
PKG = "taskflow"
SUMMARY = "把 RPA 流程描述成步骤列表, 由 Flow 统一管重试与异常策略, 执行器可替换成 UiPath / 达观 / 影刀任意后端。"
STACK_NOTES = [
    "Step 只描述意图, 不碰具体设计器 API",
    "on_error=fail/skip 两种策略, 分别对应主流程与旁路校验",
    "执行器是注入的函数, 测试里换成记录调用顺序的假执行器",
]
NOTES = """
RPA 项目最难维护的不是单个流程, 是流程里的重试和异常处理散落在几百行键鼠调用里。
这里把控制流收到 Flow 一处: 步骤只关心"做什么", 重试次数和出错策略是数据, 不是代码分支。
日后接真实设计器, 只要实现一个 executor(step) 把 action 字符串映射到具体调用。
"""

FILES = {
    "taskflow/__init__.py": '''from .flow import Flow, FlowError, RunReport, Step, StepResult

__all__ = ["Step", "StepResult", "RunReport", "Flow", "FlowError"]
''',
    "taskflow/flow.py": '''# 声明式流程: 步骤数据化, 控制流集中管理。
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

VALID_POLICIES = ("fail", "skip")


class FlowError(RuntimeError):
    """某个步骤用尽重试仍然失败, 且策略为 fail。"""


@dataclass
class Step:
    name: str
    action: str
    retries: int = 0
    on_error: str = "fail"

    def __post_init__(self) -> None:
        if self.retries < 0:
            raise ValueError("retries 不能为负")
        if self.on_error not in VALID_POLICIES:
            raise ValueError("on_error 只能是 fail 或 skip")


@dataclass
class StepResult:
    name: str
    action: str
    ok: bool
    attempts: int
    error: str | None = None


@dataclass
class RunReport:
    flow: str
    results: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def failed(self) -> list[StepResult]:
        return [r for r in self.results if not r.ok]

    def summary(self) -> str:
        good = sum(1 for r in self.results if r.ok)
        return f"{self.flow}: {good}/{len(self.results)} 步成功"


class Flow:
    def __init__(self, name: str, steps: list[Step]) -> None:
        self.name = name
        self.steps = list(steps)

    def run(
        self,
        executor: Callable[[Step], None],
        on_retry: Callable[[Step, int, Exception], None] | None = None,
    ) -> RunReport:
        report = RunReport(flow=self.name)
        for step in self.steps:
            attempts = 0
            error: Exception | None = None
            while attempts <= step.retries:
                attempts += 1
                try:
                    executor(step)
                except Exception as exc:  # noqa: BLE001 - 步骤失败一律走策略判断
                    error = exc
                    if attempts <= step.retries and on_retry is not None:
                        on_retry(step, attempts, exc)
                    continue
                error = None
                break
            if error is None:
                report.results.append(
                    StepResult(name=step.name, action=step.action, ok=True, attempts=attempts)
                )
                continue
            report.results.append(
                StepResult(
                    name=step.name,
                    action=step.action,
                    ok=False,
                    attempts=attempts,
                    error=str(error),
                )
            )
            if step.on_error == "fail":
                raise FlowError(f"步骤 {step.name} 失败: {error}") from error
        return report
''',
    "tests/test_flow.py": '''import pytest

from taskflow import Flow, FlowError, Step


def recorder(log: list[str]):
    def executor(step: Step) -> None:
        log.append(step.action)

    return executor


def test_runs_in_order() -> None:
    log: list[str] = []
    flow = Flow("demo", [Step("a", "open"), Step("b", "click"), Step("c", "save")])
    report = flow.run(recorder(log))
    assert log == ["open", "click", "save"]
    assert report.ok is True
    assert report.summary() == "demo: 3/3 步成功"


def test_retry_then_success() -> None:
    calls: list[str] = []

    def flaky(step: Step) -> None:
        calls.append(step.name)
        if len(calls) < 3:
            raise TimeoutError("控件没出来")

    flow = Flow("demo", [Step("click", "click", retries=2)])
    report = flow.run(flaky)
    assert len(calls) == 3
    assert report.results[0].attempts == 3
    assert report.ok is True


def test_retry_exhausted_raises() -> None:
    def always_fail(step: Step) -> None:
        raise RuntimeError("元素定位失败")

    flow = Flow("demo", [Step("click", "click", retries=1)])
    with pytest.raises(FlowError, match="元素定位失败"):
        flow.run(always_fail)


def test_skip_policy_continues() -> None:
    log: list[str] = []

    def executor(step: Step) -> None:
        if step.name == "bad":
            raise ValueError("旁路校验失败")
        log.append(step.action)

    flow = Flow("demo", [Step("bad", "x", on_error="skip"), Step("good", "y")])
    report = flow.run(executor)
    assert log == ["y"]
    assert [r.name for r in report.failed] == ["bad"]
    assert report.ok is False


def test_on_retry_hook() -> None:
    seen: list[tuple[str, int]] = []

    def fail(step: Step) -> None:
        raise RuntimeError("boom")

    flow = Flow("demo", [Step("s", "act", retries=2)])
    with pytest.raises(FlowError):
        flow.run(fail, on_retry=lambda step, attempt, exc: seen.append((step.name, attempt)))
    assert seen == [("s", 1), ("s", 2)]


def test_step_validation() -> None:
    with pytest.raises(ValueError):
        Step("s", "a", retries=-1)
    with pytest.raises(ValueError):
        Step("s", "a", on_error="ignore")
''',
}
