# 策略组装: 分类 + 预算 + 退避。
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .budget import RetryBudget
from .classify import classify

JITTER_MODES = ("full", "equal", "none")


def backoff(
    attempt: int,
    *,
    base: float = 0.5,
    cap: float = 30.0,
    jitter: str = "full",
    rng: random.Random | None = None,
) -> float:
    """第 attempt 次(从 0 计)重试前的等待秒数。"""
    if attempt < 0:
        raise ValueError("attempt 不能为负")
    if jitter not in JITTER_MODES:
        raise ValueError("jitter 只能是 " + "/".join(JITTER_MODES))
    raw = min(cap, base * (2 ** attempt))
    if jitter == "none":
        return raw
    generator = rng or random.Random(0)
    if jitter == "equal":
        half = raw / 2
        return half + generator.uniform(0, half)
    return generator.uniform(0, raw)


@dataclass
class Policy:
    max_attempts: int = 3
    base: float = 0.5
    cap: float = 30.0
    jitter: str = "full"
    budget: RetryBudget | None = field(default_factory=lambda: RetryBudget())

    def decide(
        self,
        attempt: int,
        *,
        status: int | None = None,
        exc: BaseException | None = None,
        method: str = "GET",
        has_key: bool = False,
        rng: random.Random | None = None,
    ) -> tuple[bool, float, str]:
        """返回 (是否重试, 等待秒数, 理由)。"""
        if attempt + 1 >= self.max_attempts:
            return False, 0.0, "已达最大尝试次数"
        action, reason = classify(status=status, exc=exc, method=method, has_key=has_key)
        if action != "retry":
            return False, 0.0, reason
        if self.budget is not None and not self.budget.allow():
            return False, 0.0, "重试预算耗尽, 停止放大故障"
        return True, backoff(attempt, base=self.base, cap=self.cap, jitter=self.jitter, rng=rng), reason
