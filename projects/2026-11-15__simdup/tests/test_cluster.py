import pytest

from simdup import dedupe, jaccard, near_duplicates, shingles

BASE = (
    "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖关系、失败重试策略、"
    "每日跑批的时间窗口安排，以及上游数据延迟时的降级方案和告警阈值设置。"
)
TWEAK = (
    "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖关系、失败重试策略、"
    "每日跑批的时间窗口安排，以及上游数据延迟时的降级方案和告警阈值处理。"
)
OTHER = (
    "完全不同的主题：讲的是前端动画性能优化的若干技巧，包括合成层与重绘的取舍、"
    "requestAnimationFrame 的调度时机，以及离屏画布的使用边界。"
)


def test_groups_identical_texts() -> None:
    groups = near_duplicates([BASE, BASE, OTHER])
    assert groups == [[0, 1], [2]]


def test_near_duplicate_clusters_together() -> None:
    groups = near_duplicates([BASE, OTHER, TWEAK])
    assert groups[0] == [0, 2]
    assert groups[1] == [1]


def test_dedupe_keeps_first_of_each_group() -> None:
    assert dedupe([BASE, BASE, OTHER]) == [0, 2]


def test_threshold_one_requires_exact() -> None:
    groups = near_duplicates([BASE, TWEAK], threshold=1.0)
    assert groups == [[0], [1]]


def test_short_text_edit_moves_jaccard_a_lot() -> None:
    """短文本 + 字符 3-gram: 改两个字就能把 Jaccard 从 1.0 拉到 0.8 附近。

    所以阈值不要设在正好等于理论相似度的位置 —— MinHash 是估计器,
    128 个置换在 0.8 附近的波动足以让结果左右翻转。
    """
    short_a = "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖关系。"
    short_b = "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖处理。"
    value = jaccard(shingles(short_a), shingles(short_b))
    assert 0.75 < value < 0.85


def test_threshold_zero_merges_everything() -> None:
    groups = near_duplicates([BASE, OTHER], threshold=0.0)
    assert groups == [[0, 1]]


def test_empty_input() -> None:
    assert near_duplicates([]) == []
    assert dedupe([]) == []


def test_single_item() -> None:
    assert near_duplicates([BASE]) == [[0]]


def test_groups_sorted_by_first_index() -> None:
    groups = near_duplicates([BASE, OTHER, BASE, OTHER])
    assert [group[0] for group in groups] == sorted(group[0] for group in groups)


def test_threshold_validation() -> None:
    with pytest.raises(ValueError):
        near_duplicates([BASE], threshold=1.5)
