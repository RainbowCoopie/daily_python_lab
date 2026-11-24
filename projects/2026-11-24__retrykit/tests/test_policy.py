import random

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
