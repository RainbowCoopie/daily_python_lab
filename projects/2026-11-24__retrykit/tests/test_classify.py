import pytest

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
