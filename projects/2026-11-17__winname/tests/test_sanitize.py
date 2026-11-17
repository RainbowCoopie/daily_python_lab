import pytest

from winname import RESERVED, is_reserved, is_safe, sanitize, split_ext


def test_illegal_chars_collapse_into_one_separator() -> None:
    assert sanitize("my<file>:v2.txt") == "my_file_v2.txt"


def test_each_illegal_char_family() -> None:
    assert sanitize("a|b|c?d*e.txt") == "a_b_c_d_e.txt"
    assert sanitize('q"w.txt') == "q_w.txt"


def test_backslash_is_path_separator_not_illegal_char() -> None:
    """先按路径切, 再谈非法字符: 所以反斜杠永远走不到替换那一步。"""
    assert sanitize("a\\b\\c.txt") == "c.txt"


def test_control_characters_replaced() -> None:
    assert sanitize("a\x01b.txt") == "a_b.txt"


def test_path_traversal_keeps_last_segment() -> None:
    assert sanitize("../../etc/passwd") == "passwd"
    assert sanitize("C:\\Users\\report.xlsx") == "report.xlsx"


def test_dot_only_names_fall_back() -> None:
    assert sanitize("") == "unnamed"
    assert sanitize(".") == "unnamed"
    assert sanitize("..") == "unnamed"
    assert sanitize("...") == "unnamed"


def test_trailing_space_and_dot_removed() -> None:
    assert sanitize("report.") == "report"
    assert sanitize("report ") == "report"
    assert sanitize("a .txt") == "a.txt"


def test_leading_space_removed() -> None:
    assert sanitize(" report.txt") == "report.txt"


@pytest.mark.parametrize("name", ["CON", "con", "PRN", "AUX", "NUL", "CLOCK$"])
def test_reserved_names_prefixed(name: str) -> None:
    assert sanitize(name) == "_" + name


@pytest.mark.parametrize("name", ["CON.txt", "nul.log", "AUX.csv"])
def test_reserved_names_with_extension_prefixed(name: str) -> None:
    assert sanitize(name) == "_" + name


def test_reserved_check_uses_part_before_first_dot() -> None:
    assert is_reserved("COM1.tar.gz") is True
    assert sanitize("COM1.tar.gz") == "_COM1.tar.gz"


def test_reserved_superscript_variants() -> None:
    assert is_reserved("COM\u00b9.txt") is True


def test_not_reserved_names_pass_through() -> None:
    assert is_reserved("COM0") is False
    assert is_reserved("report.txt") is False
    assert sanitize("console.txt") == "console.txt"


def test_cjk_names_untouched() -> None:
    assert sanitize("月度报表（终版）.xlsx") == "月度报表（终版）.xlsx"


def test_length_truncation_keeps_extension() -> None:
    long_name = "x" * 200 + ".txt"
    result = sanitize(long_name, max_len=20)
    assert len(result) == 20
    assert result.endswith(".txt")


def test_length_truncation_without_extension() -> None:
    assert sanitize("y" * 50, max_len=10) == "y" * 10


def test_truncation_does_not_leave_trailing_space() -> None:
    result = sanitize("a" * 18 + " .txt", max_len=20)
    assert not result.endswith(" ")
    assert not result.endswith(".")


def test_split_ext() -> None:
    assert split_ext("a.txt") == ("a", ".txt")
    assert split_ext("a.tar.gz") == ("a.tar", ".gz")
    assert split_ext("noext") == ("noext", "")
    assert split_ext("trailing.") == ("trailing.", "")
    assert split_ext("a.longextension") == ("a.longextension", "")
    assert split_ext("a. wi th") == ("a. wi th", "")


def test_sanitize_rejects_bad_max_len() -> None:
    with pytest.raises(ValueError):
        sanitize("a.txt", max_len=0)


def test_is_safe_round_trip() -> None:
    assert is_safe("report.txt") is True
    assert is_safe("月度报表.xlsx") is True
    assert is_safe("CON.txt") is False
    assert is_safe("a<b.txt") is False
    assert is_safe("report.") is False


def test_double_extension_left_alone() -> None:
    # 合法, 该由上层判断类型, 不在这一层拦
    assert sanitize("evil.txt.exe") == "evil.txt.exe"


def test_result_is_idempotent() -> None:
    samples = ["CON.txt", "../a<b>.txt", "report.", "x" * 200 + ".txt", "中文.xlsx"]
    for sample in samples:
        once = sanitize(sample)
        assert sanitize(once) == once


def test_reserved_set_contents() -> None:
    assert "CON" in RESERVED
    assert "LPT9" in RESERVED
    assert "COM1" in RESERVED
    assert "COM10" not in RESERVED
