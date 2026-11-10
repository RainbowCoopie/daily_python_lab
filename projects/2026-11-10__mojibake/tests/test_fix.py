import pytest

from mojibake import Repair, candidates, is_mojibake, repair, score


def make_mojibake(text: str, encoding: str = "latin-1") -> str:
    """按指定编码把 UTF-8 字节流读坏, 得到火星文。"""
    return text.encode("utf-8").decode(encoding)


def test_clean_text_scores_zero() -> None:
    assert score("hello world") == 0
    assert score("你好，世界") == 0
    assert score("") == 0


def test_latin_mojibake_has_positive_score() -> None:
    assert score(make_mojibake("你好")) > 0


def test_artifact_token_scored() -> None:
    assert score("锟斤拷") >= 5


def test_replacement_char_heavily_penalised() -> None:
    assert score("\ufffd") >= 10


def test_kana_penalised() -> None:
    assert score("ソ") == 1


def test_c1_and_private_use_penalised() -> None:
    assert score("\x81") == 3
    assert score("\ue000") == 4


@pytest.mark.parametrize("sample", ["你好", "数据管道", "RPA 流程", "中文路径"])
def test_repair_latin1_roundtrip(sample: str) -> None:
    broken = make_mojibake(sample)
    result = repair(broken)
    assert result.text == sample
    assert result.encoding == "latin-1"
    assert result.improved is True
    assert result.score_after < result.score_before


def test_repair_gbk_roundtrip() -> None:
    broken = make_mojibake("你好", "gbk")
    assert broken == "浣犲ソ"
    result = repair(broken)
    assert result.text == "你好"
    assert result.encoding == "gbk"


def test_repair_leaves_clean_text_alone() -> None:
    for text in ("hello", "你好", "café", "Ãlvaro", "こんにちは"):
        result = repair(text)
        assert result.text == text
        assert result.encoding is None
        assert result.improved is False


def test_unrecoverable_artifact_detected_but_not_repaired() -> None:
    result = repair("锟斤拷")
    assert result.improved is False
    assert result.text == "锟斤拷"
    assert is_mojibake("锟斤拷") is True


def test_result_never_contains_replacement_char() -> None:
    for text in (make_mojibake("你好"), make_mojibake("数据", "gbk"), "锟斤拷"):
        assert "\ufffd" not in repair(text).text


def test_is_mojibake_positive_cases() -> None:
    assert is_mojibake(make_mojibake("你好")) is True
    assert is_mojibake(make_mojibake("你好", "gbk")) is True


def test_is_mojibake_negative_cases() -> None:
    for text in ("hello", "你好", "こんにちは", ""):
        assert is_mojibake(text) is False


def test_candidates_sorted_by_score() -> None:
    got = candidates(make_mojibake("你好"))
    assert got
    scores = [score(text) for _, text in got]
    assert scores == sorted(scores)


def test_candidates_empty_for_unencodable_text() -> None:
    assert candidates("😀") == []


def test_repair_dataclass_fields() -> None:
    result = Repair(text="x", encoding="latin-1", score_before=3, score_after=0)
    assert result.improved is True
    assert Repair(text="x", encoding=None, score_before=0, score_after=0).improved is False


def test_mixed_mojibake_and_clean_text() -> None:
    mixed = "文件名: " + make_mojibake("报表") + ".xlsx"
    assert is_mojibake(mixed) is True
    assert "报表" in repair(mixed).text
    assert repair(mixed).text.startswith("文件名: ")
