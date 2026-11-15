import pytest

from simdup import (
    hamming,
    minhash_signature,
    minhash_similarity,
    shingles,
    simhash,
    simhash_similarity,
)

TEXT_A = "数据管道每天跑一次批处理任务"
TEXT_B = "数据管道每天跑一次批处理作业"
TEXT_C = "完全不相干的内容，讲的是别的事情"


def test_simhash_is_deterministic() -> None:
    first = simhash(shingles(TEXT_A))
    second = simhash(shingles(TEXT_A))
    assert first == second
    assert isinstance(first, int)


def test_simhash_identical_text_equal() -> None:
    assert simhash(shingles(TEXT_A)) == simhash(shingles(TEXT_A))


def test_simhash_near_text_closer_than_far_text() -> None:
    near = hamming(simhash(shingles(TEXT_A)), simhash(shingles(TEXT_B)))
    far = hamming(simhash(shingles(TEXT_A)), simhash(shingles(TEXT_C)))
    assert near < far


def test_simhash_empty_tokens() -> None:
    assert simhash(set()) == 0


def test_hamming_symmetric_and_zero() -> None:
    assert hamming(0b1010, 0b0011) == 2
    assert hamming(7, 7) == 0
    assert hamming(0b1010, 0b0011) == hamming(0b0011, 0b1010)


def test_simhash_similarity_range() -> None:
    value = simhash_similarity(1, 2)
    assert 0.0 <= value <= 1.0
    assert simhash_similarity(5, 5) == 1.0


def test_minhash_signature_shape_and_determinism() -> None:
    tokens = shingles(TEXT_A)
    sig = minhash_signature(tokens, num_perm=16)
    assert len(sig) == 16
    assert sig == minhash_signature(tokens, num_perm=16)


def test_minhash_rejects_bad_perm() -> None:
    with pytest.raises(ValueError):
        minhash_signature({"a"}, num_perm=0)


def test_minhash_similarity_identical() -> None:
    sig = minhash_signature(shingles(TEXT_A), num_perm=32)
    assert minhash_similarity(sig, sig) == 1.0


def test_minhash_length_mismatch() -> None:
    with pytest.raises(ValueError):
        minhash_similarity((1, 2), (1, 2, 3))


def test_minhash_approximates_jaccard() -> None:
    """两边各 100 个 token, 交集 50: 真实 Jaccard = 50/150 ≈ 0.333。"""
    left = {"t" + str(i) for i in range(100)}
    right = {"t" + str(i) for i in range(50, 150)}
    sig_left = minhash_signature(left, num_perm=256)
    sig_right = minhash_signature(right, num_perm=256)
    estimate = minhash_similarity(sig_left, sig_right)
    assert estimate == pytest.approx(1 / 3, abs=0.1)


def test_minhash_near_duplicate_high() -> None:
    sig_a = minhash_signature(shingles(TEXT_A), num_perm=64)
    sig_b = minhash_signature(shingles(TEXT_B), num_perm=64)
    sig_c = minhash_signature(shingles(TEXT_C), num_perm=64)
    assert minhash_similarity(sig_a, sig_b) > minhash_similarity(sig_a, sig_c)
