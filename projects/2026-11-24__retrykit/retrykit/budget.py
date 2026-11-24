# 重试预算: 令牌桶, 成功回补, 重试消耗。
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
