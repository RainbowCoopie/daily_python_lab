import pytest

from cnvalid import mask, mask_id_card


def test_mask_default_keeps_head_and_tail() -> None:
    assert mask("110101199003071234") == "110***********1234"


def test_mask_custom_widths() -> None:
    assert mask("110101199003071234", head=6, tail=4) == "110101********1234"
    assert mask("110101199003071234", head=0, tail=4) == "**************1234"


def test_mask_phone() -> None:
    assert mask("13800138000", head=3, tail=4) == "138****8000"


def test_mask_short_value_fully_hidden() -> None:
    assert mask("1234567", head=3, tail=4) == "*******"
    assert mask("", head=3, tail=4) == ""


def test_mask_length_preserved() -> None:
    for value in ("1234", "123456789012345678", "abc"):
        assert len(mask(value)) == len(value)


def test_mask_custom_fill() -> None:
    assert mask("13800138000", 3, 4, fill="#") == "138####8000"


def test_mask_rejects_negative_widths() -> None:
    with pytest.raises(ValueError):
        mask("123", head=-1)
    with pytest.raises(ValueError):
        mask("123", tail=-1)


def test_mask_id_card_helper() -> None:
    assert mask_id_card("11010519491231002X") == "110***********002X"
