import pytest

from logmine import Miner


def test_identical_lines_share_one_template() -> None:
    miner = Miner()
    for line in ("connected to 10.0.0.1", "connected to 10.0.0.2", "connected to 10.0.0.3"):
        miner.add(line)
    templates = miner.templates()
    assert len(templates) == 1
    assert templates[0].text == "connected to <IP>"
    assert templates[0].count == 3


def test_hex_and_number_masked() -> None:
    miner = Miner()
    miner.add("Hex number 0xDEADBEAF")
    miner.add("Hex number 0x10000")
    miner.add("count 42")
    miner.add("count 7")
    texts = sorted(t.text for t in miner.templates())
    assert texts == ["Hex number <HEX>", "count <NUM>"]


def test_unknown_variation_becomes_wildcard() -> None:
    miner = Miner()
    miner.add("user davidoh logged in")
    miner.add("user eranr logged in")
    templates = miner.templates()
    assert len(templates) == 1
    assert templates[0].text == "user <*> logged in"
    assert templates[0].count == 2


def test_different_shapes_stay_separate() -> None:
    miner = Miner()
    miner.add("connected to 10.0.0.1")
    miner.add("job finished")
    assert len(miner.templates()) == 2


def test_different_token_counts_never_merge() -> None:
    miner = Miner()
    miner.add("a b c")
    miner.add("a b c d")
    assert len(miner.templates()) == 2


def test_threshold_controls_aggressiveness() -> None:
    strict = Miner(similarity_threshold=0.9)
    strict.add("alpha beta gamma delta")
    strict.add("alpha beta gamma omega")
    assert len(strict.templates()) == 2     # 3/4 = 0.75 < 0.9

    loose = Miner(similarity_threshold=0.5)
    loose.add("alpha beta gamma delta")
    loose.add("alpha beta gamma omega")
    assert len(loose.templates()) == 1     # 0.75 >= 0.5


def test_template_ids_follow_first_seen_order() -> None:
    miner = Miner()
    first = miner.add("alpha beta")
    second = miner.add("gamma delta")
    assert (first.id, second.id) == (1, 2)
    assert [t.id for t in miner.templates()] == [1, 2]


def test_exactly_threshold_similarity_merges() -> None:
    """蒙掉数字后只剩一个词不同: 相似度正好 0.5, 而阈值是闭区间, 所以合并。

    这个边界是刻意选的: `a 1` 和 `b 2` 形状相同, 合成 `<*> <NUM>` 更符合"模板"的意义。
    想要更保守就把阈值调高。
    """
    miner = Miner()
    first = miner.add("a 1")
    merged = miner.add("b 2")
    assert merged.id == first.id
    assert merged.text == "<*> <NUM>"


def test_ids_are_stable_across_runs() -> None:
    def run() -> list[int]:
        miner = Miner()
        for line in ("alpha beta", "gamma delta", "alpha beta"):
            miner.add(line)
        return [t.id for t in miner.templates()]

    assert run() == run() == [1, 2]


def test_get_by_id() -> None:
    miner = Miner()
    tpl = miner.add("connected to 10.0.0.1")
    assert miner.get(tpl.id) is tpl


def test_get_unknown_id_raises() -> None:
    with pytest.raises(KeyError):
        Miner().get(99)


def test_empty_line_rejected() -> None:
    with pytest.raises(ValueError):
        Miner().add("   ")


def test_bad_threshold_rejected() -> None:
    with pytest.raises(ValueError):
        Miner(similarity_threshold=1.5)


def test_wildcard_positions_stay_wildcard() -> None:
    """合并成 <*> 之后再来的日志, 不应把通配位"填回去"。"""
    miner = Miner()
    miner.add("user davidoh logged in")
    miner.add("user eranr logged in")
    tpl = miner.add("user bob logged in")
    assert tpl.text == "user <*> logged in"
    assert tpl.count == 3


def test_similarity_helper() -> None:
    from logmine.miner import similarity

    assert similarity(("a", "b"), ("a", "b")) == 1.0
    assert similarity(("a", "b"), ("a", "<*>")) == 1.0
    assert similarity(("a", "b"), ("c", "d")) == 0.0
    assert similarity(("a", "b"), ("a",)) == 0.0
