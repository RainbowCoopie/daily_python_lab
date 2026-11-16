import pytest
from datetime import date

from cnvalid import id_check_digit, id_parse, id_valid


def test_check_digit_matches_official_example() -> None:
    # 科普中国给的算例: 前 17 位 12345678901234567, 校验码应为 7
    assert id_check_digit("12345678901234567") == "7"


def test_check_digit_x_case() -> None:
    # 余数为 2 时校验码是 X, 不是 10
    assert id_check_digit("11010519491231002") == "X"


def test_valid_known_numbers() -> None:
    assert id_valid("123456789012345677") is True
    assert id_valid("11010519491231002X") is True


def test_lowercase_x_accepted() -> None:
    assert id_valid("11010519491231002x") is True


def test_spaces_and_fullwidth_normalised() -> None:
    assert id_valid(" 11010519491231002X ") is True
    assert id_valid("１１０１０５１９４９１２３１００２Ｘ") is True


def test_wrong_check_digit_rejected() -> None:
    assert id_valid("110105194912310021") is False


def test_wrong_length_or_chars_rejected() -> None:
    assert id_valid("1101051949123100") is False
    assert id_valid("11010519491231002Y") is False
    assert id_valid("1101051949123100AX") is False
    assert id_valid("") is False


def test_check_digit_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        id_check_digit("123")
    with pytest.raises(ValueError):
        id_check_digit("1234567890123456A")


def test_parse_fields() -> None:
    info = id_parse("11010519491231002X")
    assert info["region"] == "110105"
    assert info["birth"] == date(1949, 12, 31)
    assert info["gender"] == "女"          # 第 17 位是 2, 偶数
    assert info["check"] == "X"


def test_parse_gender_male() -> None:
    # 123456789012345677 是国标算例, 中间不是真生日, 不能用来测 parse
    body = "11010519900315001"        # 第 17 位是 1, 奇数 => 男
    info = id_parse(body + id_check_digit(body))
    assert info["gender"] == "男"
    assert info["birth"] == date(1990, 3, 15)


def test_parse_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        id_parse("110105194912310021")


def test_parse_rejects_impossible_date() -> None:
    # 构造一个校验码正确但日期不存在的号码
    body = "11010519900230" + "001"
    with pytest.raises(ValueError):
        id_parse(body + id_check_digit(body))
