import pytest

from widegrid import char_width, pad, text_width, truncate


def test_ascii_width() -> None:
    assert text_width("hello") == 5
    assert char_width("a") == 1


def test_cjk_counts_two() -> None:
    assert char_width("中") == 2
    assert text_width("中文") == 4
    assert text_width("abc中文") == 7


def test_fullwidth_forms_count_two() -> None:
    assert char_width("Ａ") == 2        # 全角 A
    assert char_width("。") == 2        # 全角句号


def test_combining_mark_counts_zero() -> None:
    assert char_width("\u0301") == 0
    assert text_width("e\u0301") == 1


def test_zero_width_category_counts_zero() -> None:
    assert char_width("\u200b") == 0   # 零宽空格


def test_emoji_counts_two() -> None:
    assert char_width("😀") == 2


def test_tab_is_four() -> None:
    assert char_width("\t") == 4


def test_char_width_rejects_multi() -> None:
    with pytest.raises(ValueError):
        char_width("ab")


def test_truncate_noop_when_fits() -> None:
    assert truncate("abc", 5) == "abc"
    assert truncate("中文", 4) == "中文"


def test_truncate_respects_display_columns() -> None:
    assert truncate("中文字符", 5) == "中文…"
    assert truncate("中文字符", 4) == "中…"
    assert truncate("中文字符", 3) == "中…"
    assert truncate("中文字符", 2) == "…"


def test_truncate_zero_and_negative() -> None:
    assert truncate("abc", 0) == ""
    assert truncate("abc", -3) == ""


def test_truncate_custom_ellipsis() -> None:
    assert truncate("abcdef", 5, ellipsis="..") == "abc.."


def test_truncate_result_never_exceeds_limit() -> None:
    for limit in range(0, 12):
        assert text_width(truncate("中文abcdef混合", limit)) <= limit


def test_pad_aligns() -> None:
    assert pad("中", 4) == "中  "
    assert pad("中", 4, "right") == "  中"
    assert pad("中", 5, "center") == " 中  "
    assert pad("中", 4, "center") == " 中 "


def test_pad_noop_when_wide_enough() -> None:
    assert pad("中文", 2) == "中文"


def test_pad_rejects_bad_align() -> None:
    with pytest.raises(ValueError):
        pad("a", 3, "middle")
