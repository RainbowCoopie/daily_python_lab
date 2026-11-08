import pytest

from sheetref import (
    MAX_COL,
    MAX_ROW,
    InvalidRef,
    RangeTooLarge,
    Ref,
    col_to_index,
    expand_range,
    format_ref,
    index_to_col,
    parse_range,
    parse_ref,
)


@pytest.mark.parametrize(
    "name,index",
    [("A", 1), ("B", 2), ("Z", 26), ("AA", 27), ("AZ", 52), ("BA", 53), ("ZZ", 702), ("AAA", 703), ("XFD", 16384)],
)
def test_col_to_index_known_values(name: str, index: int) -> None:
    assert col_to_index(name) == index
    assert index_to_col(index) == name


@pytest.mark.parametrize("index", [1, 25, 26, 27, 52, 53, 702, 703, 16384])
def test_roundtrip(index: int) -> None:
    assert col_to_index(index_to_col(index)) == index


def test_lowercase_accepted() -> None:
    assert col_to_index("xfd") == 16384


def test_col_limits() -> None:
    with pytest.raises(InvalidRef):
        col_to_index("XFE")          # 超出一列
    with pytest.raises(InvalidRef):
        col_to_index("ABCD")         # 四字母
    with pytest.raises(InvalidRef):
        col_to_index("")
    with pytest.raises(InvalidRef):
        index_to_col(0)
    with pytest.raises(InvalidRef):
        index_to_col(MAX_COL + 1)


def test_parse_relative() -> None:
    ref = parse_ref("B12")
    assert (ref.col, ref.row) == (2, 12)
    assert (ref.abs_col, ref.abs_row) == (False, False)


def test_parse_absolute() -> None:
    ref = parse_ref("$AB$12")
    assert (ref.col, ref.row) == (28, 12)
    assert (ref.abs_col, ref.abs_row) == (True, True)
    assert format_ref(ref) == "$AB$12"


def test_parse_mixed_and_roundtrip() -> None:
    for text in ("A1", "$A1", "A$1", "$A$1", "$XFD$1048576"):
        assert format_ref(parse_ref(text)) == text


@pytest.mark.parametrize("bad", ["", "1A", "A", "A0", "A1048577", "A1B", "$", "A1:A2:A3"])
def test_invalid_refs(bad: str) -> None:
    with pytest.raises(InvalidRef):
        parse_ref(bad)


def test_row_limit() -> None:
    assert parse_ref("A" + str(MAX_ROW)).row == MAX_ROW
    with pytest.raises(InvalidRef):
        parse_ref("A" + str(MAX_ROW + 1))


def test_parse_range_single_cell() -> None:
    start, end = parse_range("C3")
    assert start == end == Ref(col=3, row=3)


def test_expand_range_row_major() -> None:
    assert expand_range("A1:B2") == ["A1", "B1", "A2", "B2"]


def test_expand_range_normalizes_reversed_input() -> None:
    assert expand_range("B2:A1") == ["A1", "B1", "A2", "B2"]


def test_expand_range_guard() -> None:
    with pytest.raises(RangeTooLarge):
        expand_range("A1:XFD1048576", limit=1000)


def test_expand_range_keeps_absolute_markers_out_of_cells() -> None:
    assert expand_range("$A$1:$B$1") == ["A1", "B1"]
