import pytest

from widegrid import render, text_width


def widths_of(text: str) -> set[int]:
    return {text_width(line) for line in text.splitlines()}


def test_render_plain_rows() -> None:
    out = render([["a", "bb"], ["cc", "d"]])
    assert out.splitlines() == ["a  | bb", "cc | d "]


def test_render_with_headers_and_separator() -> None:
    out = render([["1", "2"]], headers=["左", "右"])
    lines = out.splitlines()
    assert lines[0] == "左 | 右"
    assert set(lines[1].replace(" ", "")) == {"-", "|"}
    assert lines[2] == "1  | 2 "


def test_every_line_has_same_display_width_with_cjk() -> None:
    out = render(
        [["中文", "x"], ["a", "两个字"]],
        headers=["名称", "值"],
    )
    assert len(widths_of(out)) == 1


def test_right_alignment_for_numbers() -> None:
    out = render([["1", "10"], ["100", "2"]], aligns=["right", "right"])
    lines = out.splitlines()
    assert lines[0] == "  1 | 10"
    assert lines[1] == "100 |  2"


def test_ragged_rows_are_padded() -> None:
    out = render([["a", "b"], ["c"]])
    assert widths_of(out) == {5}


def test_empty_input() -> None:
    assert render([]) == ""
    assert render([], headers=[]) == ""


def test_max_width_truncates_cells() -> None:
    out = render([["中文字符很长", "b"]], max_width=5)
    assert out.splitlines()[0].startswith("中文…")
    assert len(widths_of(out)) == 1


def test_aligns_length_must_match() -> None:
    with pytest.raises(ValueError):
        render([["a", "b"]], aligns=["left"])


def test_max_width_must_be_positive() -> None:
    with pytest.raises(ValueError):
        render([["a"]], max_width=0)


def test_separator_row_can_be_disabled() -> None:
    out = render([["1"]], headers=["h"], separator_row=False)
    assert len(out.splitlines()) == 2
