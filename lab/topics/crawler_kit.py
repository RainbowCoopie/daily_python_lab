'''爬虫的三块基础砖: 限速、退避重试、URL 去重。全部纯逻辑, 不联网也能测。'''

SLUG = "crawler_kit"
TITLE = "爬虫限速 / 重试 / 去重三件套"
TAGS = ["爬虫工程", "requests 思路", "限速", "去重"]
PKG = "crawlkit"
SUMMARY = "令牌桶限速、指数退避重试、URL 规范化去重——把爬虫里最容易写错的三块拆成可单测的小件。"
STACK_NOTES = [
    "时间由调用方传入 now, 不 sleep、不 mock、不飘",
    "URL 规范化: 大小写、默认端口、fragment、utm_ 参数、query 排序全部抹平",
    "重试延迟封顶, 避免 2^n 把线程挂死",
]
NOTES = """
限速和重试是最容易在真实项目里出事故的两处。这里的约定: 所有时间都是显式参数, 函数不自己 sleep,
也不读系统时钟, 所以测试是确定性的; sleep 交给调度层, 方便换成 asyncio 或 RPA 的等待逻辑。
"""

FILES = {
    "crawlkit/__init__.py": '''from .dedupe import SeenSet, canonical
from .retry import backoff_delay, retry_call
from .throttle import TokenBucket

__all__ = ["TokenBucket", "backoff_delay", "retry_call", "canonical", "SeenSet"]
''',
    "crawlkit/throttle.py": '''# 令牌桶: 只算"要等多久", 自己不睡。
from __future__ import annotations


class TokenBucket:
    def __init__(self, rate: float, capacity: float | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate 必须为正数")
        self.rate = float(rate)
        self.capacity = float(capacity if capacity is not None else rate)
        if self.capacity < 1:
            raise ValueError("capacity 至少为 1, 否则单次请求永远取不到令牌")
        self._tokens = self.capacity
        self._last = 0.0

    def _refill(self, now: float) -> None:
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now

    def take(self, n: int = 1, now: float = 0.0) -> float:
        """尝试取 n 个令牌。返回 0 表示立刻可用, 否则返回建议等待秒数。"""
        if n <= 0:
            raise ValueError("n 必须为正数")
        if n > self.capacity:
            raise ValueError("n 超过桶容量")
        self._refill(now)
        if self._tokens >= n:
            self._tokens -= n
            return 0.0
        shortfall = n - self._tokens
        self._tokens = 0.0
        return shortfall / self.rate
''',
    "crawlkit/retry.py": '''# 指数退避 + 可注入 sleep, 便于测试与替换调度器。
from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    """第 attempt 次失败(从 0 计)后的等待秒数, 上限 cap。"""
    if attempt < 0:
        raise ValueError("attempt 不能为负")
    return min(cap, base * (2 ** attempt))


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base: float = 0.5,
    cap: float = 30.0,
    sleep: Callable[[float], None] | None = None,
    on_retry: Callable[[int, float, Exception], None] | None = None,
) -> T:
    """最多执行 attempts 次, 全失败则抛出最后一次异常。"""
    if attempts < 1:
        raise ValueError("attempts 至少为 1")
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - 这里就是要接住一切再决定要不要重试
            last = exc
            if i == attempts - 1:
                break
            delay = backoff_delay(i, base, cap)
            if on_retry is not None:
                on_retry(i, delay, exc)
            if sleep is not None:
                sleep(delay)
    assert last is not None
    raise last
''',
    "crawlkit/dedupe.py": '''# URL 规范化与去重集合。
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DROPPED_PREFIXES = ("utm_", "spm", "from")


def canonical(url: str) -> str:
    """抹平大小写、默认端口、fragment、追踪参数与 query 顺序。"""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "http"
    host = (parts.hostname or "").lower()
    port = parts.port
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else host + ":" + str(port)
    pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not any(k.lower().startswith(p) for p in DROPPED_PREFIXES)
    ]
    pairs.sort()
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, urlencode(pairs, doseq=True), ""))


class SeenSet:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def add(self, url: str) -> bool:
        """首次出现返回 True, 重复返回 False。"""
        key = canonical(url)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def __contains__(self, url: object) -> bool:
        return isinstance(url, str) and canonical(url) in self._seen

    def __len__(self) -> int:
        return len(self._seen)
''',
    "tests/test_throttle.py": '''import pytest

from crawlkit.throttle import TokenBucket


def test_burst_then_throttle() -> None:
    bucket = TokenBucket(rate=2.0, capacity=2)
    assert bucket.take(now=0.0) == 0.0
    assert bucket.take(now=0.0) == 0.0
    assert bucket.take(now=0.0) == pytest.approx(0.5)


def test_refill_over_time() -> None:
    bucket = TokenBucket(rate=2.0, capacity=2)
    bucket.take(now=0.0)
    bucket.take(now=0.0)
    assert bucket.take(now=0.5) == 0.0        # 0.5s 补 1 个令牌
    assert bucket.take(now=0.5) == pytest.approx(0.5)


def test_capacity_cap() -> None:
    bucket = TokenBucket(rate=1.0, capacity=1)
    assert bucket.take(now=100.0) == 0.0
    assert bucket.take(now=100.0) == pytest.approx(1.0)


def test_invalid_args() -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate=0)
    with pytest.raises(ValueError):
        TokenBucket(rate=1.0, capacity=0.5)
    bucket = TokenBucket(rate=1.0, capacity=1)
    with pytest.raises(ValueError):
        bucket.take(n=2)
''',
    "tests/test_retry.py": '''import pytest

from crawlkit.retry import backoff_delay, retry_call


def test_backoff_doubles_and_caps() -> None:
    assert backoff_delay(0, base=0.5, cap=30) == 0.5
    assert backoff_delay(3, base=0.5, cap=30) == 4.0
    assert backoff_delay(10, base=0.5, cap=30) == 30


def test_retry_until_success() -> None:
    calls = {"n": 0}
    delays: list[float] = []

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("boom")
        return "ok"

    assert retry_call(flaky, attempts=3, base=0.5, sleep=delays.append) == "ok"
    assert calls["n"] == 3
    assert delays == [0.5, 1.0]


def test_raises_last_error() -> None:
    def always_fail() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        retry_call(always_fail, attempts=2, sleep=lambda _: None)


def test_on_retry_callback() -> None:
    seen: list[int] = []

    def fail() -> None:
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        retry_call(fail, attempts=2, on_retry=lambda i, d, e: seen.append(i))
    assert seen == [0]


def test_attempts_validation() -> None:
    with pytest.raises(ValueError):
        retry_call(lambda: None, attempts=0)
''',
    "tests/test_dedupe.py": '''from crawlkit.dedupe import SeenSet, canonical


def test_canonical_normalizes() -> None:
    raw = "HTTP://Example.COM:80/a/b/?utm_source=x&b=2&a=1#frag"
    assert canonical(raw) == "http://example.com/a/b/?a=1&b=2"


def test_canonical_keeps_non_default_port() -> None:
    assert canonical("https://a.com:8443/x") == "https://a.com:8443/x"
    assert canonical("https://a.com:443/x") == "https://a.com/x"


def test_canonical_default_path() -> None:
    assert canonical("https://a.com") == "https://a.com/"


def test_seen_set() -> None:
    seen = SeenSet()
    assert seen.add("https://a.com/x?utm_medium=1") is True
    assert seen.add("https://a.com/x") is False
    assert "https://A.com/x" in seen
    assert len(seen) == 1
''',
}
