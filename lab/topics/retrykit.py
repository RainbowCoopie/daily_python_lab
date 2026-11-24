'''重试策略: 错误分类 + 带 jitter 的退避 + 重试预算(防重试风暴)。

灵感来源:
- retry storm 的成因与控制手段: 调用方各自重试, 在故障瞬间把负载放大 N 倍,
  解法是"次数上限 + 带 jitter 的指数退避 + 重试预算 + 只在一层重试"
  (https://safeguard.sh/resources/blog/retry-storms-how-retries-become-a-self-inflicted-outage)
- 只对幂等方法重试, 且限定 408/429/500/502/503/504; POST/PATCH 必须带幂等键才允许重试
  (https://pub.dev/documentation/superso_flutter_sdk/latest/superso_flutter_sdk/RetryPolicy-class.html)
- 用令牌桶做重试预算: 成功回补、失败消耗, 让整个进程的重试总量有上界
  (https://github.com/joshrotenberg/tower-resilience/issues/171)
- 幂等键要给三态(进行中/完成/失败)和租约, 两态状态机会把崩溃点变成假完成
  (https://cloud.tencent.com.cn/developer/article/2742188)

为什么值得单独做一层: 重试最大的危险不是"没重试成功", 而是"重试把小事放大成事故"。
所以这一层的核心不是退避公式, 而是**什么时候根本不许重试**:
非幂等请求没带幂等键就不许、预算用完就不许、错误是确定性失败就不许。
本模块把这些禁止条件写成显式返回原因, 而不是散落在调用方的 if 里。
'''

SLUG = "retrykit"
TITLE = "重试策略与重试预算"
TAGS = ["重试风暴", "退避抖动", "幂等性", "HTTP 状态分类"]
PKG = "retrykit"
SUMMARY = "按方法与状态码判定能不能重试, 配 jitter 退避与令牌桶预算, 并给出不许重试的明确理由。"
STACK_NOTES = [
    "分类先看幂等性: POST/PATCH 没有幂等键时, 哪怕 503 也不许重试",
    "退避默认 full jitter, 且 rng 可注入 —— 测试里用定种随机数, 结果可复现",
    "重试预算用令牌桶: 成功按比例回补, 每次重试消耗一个, 到零就停",
]
NOTES = """
三道闸门, 顺序不能换:

1. **能不能重**(幂等性 + 状态码)。GET/HEAD/PUT/DELETE/OPTIONS 天然幂等;
   POST/PATCH 只有带了幂等键才算可重放。确定性失败(400/401/403/404/422)永远不重试 ——
   重试一个"请求本身写错了"的请求, 只会把错误重复 N 次。
2. **值不值得重**(预算)。令牌桶按"成功一次回补 ratio 个令牌, 重试一次消耗一个"运作。
   下游全挂的时候, 成功率下降 → 回补变少 → 重试很快被掐断。这就是防风暴的机制本身:
   它不判断某次重试有没有用, 只保证**总量**不会失控。
3. **等多久**(退避)。full jitter 在 [0, cap*2^n] 里均匀取值, 把同时重试的客户端打散。
   用定种随机数就能复现, 所以这一层是可以写测试的 —— 很多重试实现不测, 就是因为没法复现。

关于 409: 不重试。"冲突"通常意味着幂等键对应的请求体不一致, 重试只会继续冲突,
需要人工/上层决策。把它当可重试是把问题藏起来。
"""

FILES = {
    "retrykit/__init__.py": '''from .budget import RetryBudget
from .classify import IDEMPOTENT_METHODS, RETRYABLE_STATUS, classify
from .policy import Policy, backoff

__all__ = [
    "IDEMPOTENT_METHODS",
    "RETRYABLE_STATUS",
    "classify",
    "RetryBudget",
    "backoff",
    "Policy",
]
''',
    "retrykit/classify.py": '''# 错误分类: 先问"能不能重", 再谈退避。
from __future__ import annotations

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS", "TRACE"})

# 可重试的状态码: 都是"服务端暂时不行", 不是"请求写错了"
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _method_is_safe(method: str, has_key: bool) -> tuple[bool, str]:
    name = method.upper()
    if name in IDEMPOTENT_METHODS:
        return True, ""
    if has_key:
        return True, ""
    return False, "非幂等方法且没有幂等键, 重试可能重复下单/重复扣费"


def classify(
    *,
    status: int | None = None,
    exc: BaseException | None = None,
    method: str = "GET",
    has_key: bool = False,
) -> tuple[str, str]:
    """返回 (动作, 理由)。动作取 ok / retry / fatal / needs_key。"""
    safe, why = _method_is_safe(method, has_key)

    if exc is not None:
        if isinstance(exc, (TimeoutError, ConnectionError)):
            if not safe:
                return "needs_key", why
            return "retry", "网络类异常, 且请求可安全重放"
        return "fatal", "非网络异常, 重试没有意义"

    if status is None:
        return "fatal", "既没有状态码也没有异常"

    if 200 <= status < 400:
        return "ok", "请求已成功"
    if status in RETRYABLE_STATUS:
        if not safe:
            return "needs_key", why
        return "retry", "服务端暂时不可用"
    if 400 <= status < 500:
        return "fatal", "客户端错误, 重试只会重复同一个错误"
    return "fatal", "未归类的状态码"
''',
    "retrykit/budget.py": '''# 重试预算: 令牌桶, 成功回补, 重试消耗。
from __future__ import annotations


class RetryBudget:
    """让整个进程的重试总量有上界 —— 防重试风暴的机制就在这里。"""

    def __init__(self, ratio: float = 0.1, capacity: float = 10.0) -> None:
        if ratio < 0:
            raise ValueError("ratio 不能为负")
        if capacity <= 0:
            raise ValueError("capacity 必须为正")
        self.ratio = ratio
        self.capacity = float(capacity)
        self._tokens = float(capacity)

    @property
    def tokens(self) -> float:
        return self._tokens

    def record_success(self, count: int = 1) -> None:
        """每次成功按比例回补; 下游健康时预算自然充足。"""
        if count < 0:
            raise ValueError("count 不能为负")
        self._tokens = min(self.capacity, self._tokens + self.ratio * count)

    def allow(self) -> bool:
        """取一个重试许可; 预算耗尽返回 False。"""
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False
''',
    "retrykit/policy.py": '''# 策略组装: 分类 + 预算 + 退避。
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
''',
    "tests/test_classify.py": '''import pytest

from retrykit import classify


@pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504])
def test_retryable_statuses_on_idempotent_method(status: int) -> None:
    assert classify(status=status, method="GET")[0] == "retry"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
def test_client_errors_are_fatal(status: int) -> None:
    action, _ = classify(status=status, method="GET")
    assert action == "fatal"


@pytest.mark.parametrize("status", [200, 201, 204, 301, 304])
def test_success_is_ok(status: int) -> None:
    assert classify(status=status)[0] == "ok"


def test_post_without_key_needs_key() -> None:
    action, reason = classify(status=503, method="POST")
    assert action == "needs_key"
    assert "幂等键" in reason


def test_post_with_key_can_retry() -> None:
    assert classify(status=503, method="POST", has_key=True)[0] == "retry"


def test_patch_without_key_needs_key() -> None:
    assert classify(status=500, method="PATCH")[0] == "needs_key"


def test_idempotent_methods_pass_without_key() -> None:
    for method in ("GET", "HEAD", "PUT", "DELETE", "OPTIONS"):
        assert classify(status=503, method=method)[0] == "retry", method


def test_network_exception_on_idempotent_is_retryable() -> None:
    assert classify(exc=TimeoutError("timeout"), method="GET")[0] == "retry"
    assert classify(exc=ConnectionResetError("reset"), method="GET")[0] == "retry"


def test_network_exception_on_post_without_key_needs_key() -> None:
    assert classify(exc=TimeoutError("timeout"), method="POST")[0] == "needs_key"


def test_non_network_exception_is_fatal() -> None:
    assert classify(exc=ValueError("bad payload"))[0] == "fatal"


def test_missing_both_is_fatal() -> None:
    assert classify()[0] == "fatal"


def test_method_case_insensitive() -> None:
    assert classify(status=503, method="get")[0] == "retry"
''',
    "tests/test_policy.py": '''import random

import pytest

from retrykit import Policy, RetryBudget, backoff


def test_backoff_grows_and_caps() -> None:
    assert backoff(0, base=1.0, cap=30, jitter="none") == 1.0
    assert backoff(3, base=1.0, cap=30, jitter="none") == 8.0
    assert backoff(10, base=1.0, cap=30, jitter="none") == 30.0


def test_full_jitter_within_range_and_reproducible() -> None:
    value = backoff(3, base=1.0, cap=100, rng=random.Random(42))
    assert 0.0 <= value <= 8.0
    assert value == backoff(3, base=1.0, cap=100, rng=random.Random(42))


def test_equal_jitter_keeps_half() -> None:
    value = backoff(2, base=1.0, cap=100, jitter="equal", rng=random.Random(7))
    assert 2.0 <= value <= 4.0


def test_backoff_validation() -> None:
    with pytest.raises(ValueError):
        backoff(-1)
    with pytest.raises(ValueError):
        backoff(0, jitter="weird")


def test_budget_consumes_and_stops() -> None:
    budget = RetryBudget(ratio=0.1, capacity=2.0)
    assert budget.allow() is True
    assert budget.allow() is True
    assert budget.allow() is False


def test_budget_refills_on_success() -> None:
    budget = RetryBudget(ratio=0.5, capacity=2.0)
    budget.allow()
    budget.allow()
    assert budget.allow() is False
    budget.record_success(4)          # 回补 2 个令牌
    assert budget.allow() is True


def test_budget_caps_at_capacity() -> None:
    budget = RetryBudget(ratio=1.0, capacity=2.0)
    budget.record_success(100)
    assert budget.tokens == 2.0


def test_budget_validation() -> None:
    with pytest.raises(ValueError):
        RetryBudget(ratio=-1)
    with pytest.raises(ValueError):
        RetryBudget(capacity=0)


def test_policy_stops_at_max_attempts() -> None:
    policy = Policy(max_attempts=2, budget=RetryBudget(capacity=10))
    assert policy.decide(0, status=503)[0] is True
    retry, delay, reason = policy.decide(1, status=503)
    assert retry is False
    assert delay == 0.0
    assert "最大尝试" in reason


def test_policy_refuses_fatal() -> None:
    policy = Policy(budget=RetryBudget(capacity=10))
    retry, _, reason = policy.decide(0, status=404)
    assert retry is False
    assert "客户端错误" in reason


def test_policy_refuses_without_key() -> None:
    policy = Policy(budget=RetryBudget(capacity=10))
    retry, _, reason = policy.decide(0, status=503, method="POST")
    assert retry is False
    assert "幂等键" in reason


def test_policy_stops_when_budget_empty() -> None:
    policy = Policy(max_attempts=10, budget=RetryBudget(capacity=0.5))
    retry, _, reason = policy.decide(0, status=503)
    assert retry is False
    assert "预算" in reason


def test_policy_returns_delay() -> None:
    # max_attempts 要留够余量: 默认 3 时 attempt=2 已经是最后一次, 不会再重试
    policy = Policy(max_attempts=5, budget=RetryBudget(capacity=10), base=1.0, jitter="none")
    retry, delay, _ = policy.decide(2, status=503)
    assert retry is True
    assert delay == 4.0


def test_policy_without_budget_always_allows() -> None:
    policy = Policy(budget=None, max_attempts=5)
    assert policy.decide(0, status=503)[0] is True
''',
}

CHALLENGE = {
    "target": "retrykit/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 retrykit/challenge.py 中实现 explain_policy(status: int, method: str, has_key: bool) -> str: "
        "用 retrykit.classify 分类, 返回 '重试' / '不重试' 加上理由, 形如 '重试: 服务端暂时不可用'。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from retrykit.challenge import explain_policy


def test_retry_case() -> None:
    assert explain_policy(503, "GET", False).startswith("重试: ")


def test_fatal_case() -> None:
    assert explain_policy(404, "GET", False).startswith("不重试: ")


def test_needs_key_case() -> None:
    assert "幂等键" in explain_policy(503, "POST", False)
''',
}
