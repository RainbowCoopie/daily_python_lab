import pytest

from simdup import jaccard, normalize_text, shingles


def test_normalize_collapses_and_lowercases() -> None:
    assert normalize_text("  Hello   World  ") == "hello world"


def test_normalize_fullwidth_to_halfwidth() -> None:
    assert normalize_text("ＡＢＣ　１２３") == "abc 123"


def test_shingles_basic() -> None:
    assert shingles("abcdef", 3) == {"abc", "bcd", "cde", "def"}


def test_shingles_short_text() -> None:
    assert shingles("ab", 3) == {"ab"}


def test_shingles_empty() -> None:
    assert shingles("", 3) == set()
    assert shingles("   ", 3) == set()


def test_shingles_honours_normalization() -> None:
    assert shingles("ABC DEF", 3) == shingles("abc   def", 3)


def test_shingles_rejects_bad_k() -> None:
    with pytest.raises(ValueError):
        shingles("abc", 0)


def test_jaccard_identical() -> None:
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint() -> None:
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial() -> None:
    assert jaccard({"a", "b", "c"}, {"b", "c", "d"}) == pytest.approx(2 / 4)


def test_jaccard_both_empty() -> None:
    assert jaccard(set(), set()) == 1.0


def test_jaccard_cjk_text() -> None:
    left = shingles("知识库入库前要去重", 3)
    right = shingles("知识库入库前需要去重", 3)
    assert 0.3 < jaccard(left, right) < 1.0
