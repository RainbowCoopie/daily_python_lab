import pytest

from textfold import (
    fold,
    fold_dashes,
    fold_quotes,
    fold_spaces,
    nfkc,
    same,
    skeleton,
    strip_invisible,
)


def test_strip_zero_width_and_soft_hyphen() -> None:
    assert strip_invisible("\u200babc\u00ad\ufeff") == "abc"


def test_strip_bidi_controls() -> None:
    assert strip_invisible("a\u202eb") == "ab"


def test_zwj_is_preserved() -> None:
    """emoji 家族序列靠 U+200D 连接, 删掉会变成三个独立的人。"""
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
    assert strip_invisible(family) == family


def test_variation_selector_is_preserved() -> None:
    heart = "\u2764\ufe0f"
    assert strip_invisible(heart) == heart


def test_fold_smart_quotes() -> None:
    assert fold_quotes("\u201c\u4e2d\u6587\u201d") == '"\u4e2d\u6587"'
    assert fold_quotes("\u2018a\u2019") == "'a'"


def test_fold_dashes() -> None:
    assert fold_dashes("a\u2013b\u2014c\u2212d\u2010e") == "a-b-c-d-e"


def test_fold_special_spaces() -> None:
    assert fold_spaces("a\u00a0b\u3000c") == "a b c"


def test_nfkc_fullwidth_and_circled() -> None:
    assert nfkc("\uff21\uff22\uff23\u2460") == "ABC1"
    assert nfkc("\uff0c") == ","


def test_fold_combines_everything() -> None:
    assert fold("\uff21\uff22\uff23, \u201cX\u201d") == 'abc, "x"'


def test_casefold_not_lower() -> None:
    assert "\u00df".casefold() == "ss"
    assert "\u00df".lower() == "\u00df"


def test_casefold_turkish_dotted_i() -> None:
    """İ 折叠成 i + 组合点, 两个码位 —— 这就是它和 lower 的区别之一。"""
    folded = fold("\u0130")
    assert folded == "i\u0307"
    assert len(folded) == 2


def test_case_can_be_kept() -> None:
    assert fold("\uff21\uff22\uff23", case=False) == "ABC"


def test_whitespace_collapsed() -> None:
    assert fold("  a   b  ") == "a b"


def test_whitespace_kept_when_disabled() -> None:
    assert fold("a  b", collapse_ws=False) == "a  b"


def test_skeleton_drops_punctuation() -> None:
    assert skeleton("Hello, World!") == "helloworld"


def test_skeleton_keeps_cjk() -> None:
    assert skeleton("\u4f60\u597d\uff0c\u4e16\u754c") == "\u4f60\u597d\u4e16\u754c"


def test_same_after_folding() -> None:
    assert same("\uff21\uff22\uff23", "abc") is True
    assert same("Hello, World!", "hello world") is True


def test_same_precomposed_vs_combining() -> None:
    """café 的两种写法(NFC 与 NFD)在归一后相等。"""
    assert same("caf\u00e9", "cafe\u0301") is True
    assert same("caf\u00e9", "cafe") is False


def test_same_rejects_different_words() -> None:
    assert same("abc", "abd") is False


@pytest.mark.parametrize("text", ["", "abc", "\uff21\uff22", "\u201c\u4f60\u597d\u201d"])
def test_fold_is_idempotent(text: str) -> None:
    once = fold(text)
    assert fold(once) == once


def test_skeleton_is_idempotent() -> None:
    once = skeleton("A, B! \u4f60\u597d")
    assert skeleton(once) == once


def test_empty_input() -> None:
    assert fold("") == ""
    assert skeleton("") == ""
    assert same("", "") is True


def test_nbsp_does_not_break_word() -> None:
    """不间断空格在展示上连在一起, 归一后应该变成一个普通空格。"""
    assert fold("hello\u00a0world") == "hello world"
    assert skeleton("hello\u00a0world") == "helloworld"
