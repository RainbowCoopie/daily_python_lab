import pytest

from unitconv import AmbiguousUnitError, format_size, parse_size


def test_plain_number_is_bytes() -> None:
    assert parse_size("2048") == 2048
    assert parse_size(2048) == 2048


def test_si_units_are_decimal() -> None:
    assert parse_size("1.5 GB") == 1500000000
    assert parse_size("1KB") == 1000


def test_iec_units_are_binary() -> None:
    assert parse_size("1.5GiB") == 1610612736
    assert parse_size("1KiB") == 1024


def test_case_insensitive_and_spaces_ignored() -> None:
    assert parse_size(" 1.5 gib ") == 1610612736


def test_kb_and_kib_differ() -> None:
    """这就是那个经典歧义: 同一个 '1.5', 差 7%。"""
    assert parse_size("1.5GB") != parse_size("1.5GiB")


def test_bare_unit_defaults_to_binary() -> None:
    assert parse_size("1G") == 1024 ** 3


def test_bare_unit_rejected_in_strict_mode() -> None:
    with pytest.raises(AmbiguousUnitError):
        parse_size("1G", strict=True)


def test_explicit_units_pass_strict_mode() -> None:
    assert parse_size("1GiB", strict=True) == 1024 ** 3
    assert parse_size("1GB", strict=True) == 1000 ** 3


@pytest.mark.parametrize("bad", ["", "abc", "-1GiB", "1.5ZiB", "1GiBx"])
def test_invalid_sizes(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_size(bad)


def test_format_default_is_si() -> None:
    assert format_size(1500) == "1.5KB"
    assert format_size(1000) == "1KB"


def test_format_binary() -> None:
    assert format_size(1536, binary=True) == "1.5KiB"
    assert format_size(1024, binary=True) == "1KiB"


def test_format_small_values() -> None:
    assert format_size(999) == "999B"
    assert format_size(0) == "0B"


def test_format_precision() -> None:
    assert format_size(1536, binary=True, precision=2) == "1.5KiB"
    assert format_size(1234567) == "1.2MB"


@pytest.mark.parametrize("value", [0, 1, 1000, 1_000_000, 1000 ** 3])
def test_roundtrip_exact_values(value: int) -> None:
    """只对"能被 SI 精确表示"的值做往返断言。"""
    assert parse_size(format_size(value)) == value


def test_si_formatting_is_lossy_for_binary_sizes() -> None:
    """1024 字节按 SI 显示成 1KB, 再解析回来是 1000 —— 这正是容量对不上的原因。"""
    assert format_size(1024) == "1KB"
    assert parse_size(format_size(1024)) == 1000
    # 想看真实字节数就用 IEC 输出
    assert parse_size(format_size(1024, binary=True)) == 1024


def test_roundtrip_binary() -> None:
    for value in (1024, 1024 ** 2, 1024 ** 3):
        assert parse_size(format_size(value, binary=True)) == value


def test_format_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        format_size(-1)
    with pytest.raises(TypeError):
        format_size(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        format_size(10, precision=-1)
