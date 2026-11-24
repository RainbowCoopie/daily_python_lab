# 错误分类: 先问"能不能重", 再谈退避。
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
