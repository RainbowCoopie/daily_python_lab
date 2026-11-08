'''YOLO 标注格式转换与框运算: COCO <-> YOLO 归一化、裁剪、IoU。训练前的脏框清理都在这层。'''

SLUG = "yolo_labels"
TITLE = "YOLO / COCO 标注转换工具"
TAGS = ["YOLO", "CV 标注", "数据清洗", "IoU"]
PKG = "labelkit"
SUMMARY = "COCO 像素框与 YOLO 归一化中心框互转, 附带越界裁剪与 IoU 计算, 用于训练前的标注体检。"
STACK_NOTES = [
    "转换双向可逆, 往返误差控制在浮点量级",
    "越界框自动裁到图内, 裁没了的框返回零面积而不是负数",
    "IoU 用交集/并集, 完全重合为 1, 无交集为 0",
]
NOTES = """
标注转换最容易出的两类错: 一是把中心点当左上角, 二是忘记归一化或者除以了错的尺寸。
这里的约定写在函数名和类型里: 凡是 rgb 像素尺寸都用 width/height 显式传,
凡是归一化坐标都返回 0~1 的浮点。框统一表示为 (x, y, w, h) 或 (cx, cy, w, h), 不用 8 元组。
"""

FILES = {
    "labelkit/__init__.py": '''from .boxes import area, clip_coco, coco_to_yolo, iou, yolo_to_coco

__all__ = ["coco_to_yolo", "yolo_to_coco", "clip_coco", "iou", "area"]
''',
    "labelkit/boxes.py": '''# 框坐标运算: 全部显式传图尺寸, 不用全局状态。
from __future__ import annotations

Box = tuple[float, float, float, float]


def _check_size(width: float, height: float) -> None:
    if width <= 0 or height <= 0:
        raise ValueError(f"图尺寸必须为正, 收到 {width}x{height}")


def area(box: Box) -> float:
    return max(0.0, box[2]) * max(0.0, box[3])


def coco_to_yolo(box: Box, width: float, height: float) -> Box:
    """(x, y, w, h) 像素 -> (cx, cy, w, h) 归一化。"""
    _check_size(width, height)
    x, y, w, h = box
    return ((x + w / 2) / width, (y + h / 2) / height, w / width, h / height)


def yolo_to_coco(box: Box, width: float, height: float) -> Box:
    """(cx, cy, w, h) 归一化 -> (x, y, w, h) 像素。"""
    _check_size(width, height)
    cx, cy, nw, nh = box
    w = nw * width
    h = nh * height
    return (cx * width - w / 2, cy * height - h / 2, w, h)


def clip_coco(box: Box, width: float, height: float) -> Box:
    """把框裁进图内, 越界部分丢弃; 全在外面的框返回零面积框。"""
    _check_size(width, height)
    x, y, w, h = box
    x1 = min(max(x, 0.0), width)
    y1 = min(max(y, 0.0), height)
    x2 = min(max(x + w, 0.0), width)
    y2 = min(max(y + h, 0.0), height)
    return (x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1))


def iou(a: Box, b: Box) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    inter_w = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    inter_h = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = inter_w * inter_h
    union = area(a) + area(b) - inter
    if union <= 0:
        return 0.0
    return inter / union
''',
    "tests/test_boxes.py": '''import pytest

from labelkit import area, clip_coco, coco_to_yolo, iou, yolo_to_coco


def test_coco_to_yolo_known_value() -> None:
    # 640x480 图上一个 64x48 的框, 中心 (100+32, 50+24) = (132, 74)
    cx, cy, w, h = coco_to_yolo((100, 50, 64, 48), 640, 480)
    assert cx == pytest.approx(132 / 640)
    assert cy == pytest.approx(74 / 480)
    assert w == pytest.approx(0.1)
    assert h == pytest.approx(0.1)


def test_roundtrip() -> None:
    box = (12.5, 33.0, 100.0, 80.0)
    back = yolo_to_coco(coco_to_yolo(box, 1280, 720), 1280, 720)
    for a, b in zip(box, back):
        assert a == pytest.approx(b)


def test_clip_inside_is_identity() -> None:
    assert clip_coco((10, 10, 20, 20), 100, 100) == (10, 10, 20, 20)


def test_clip_truncates() -> None:
    assert clip_coco((90, 90, 50, 50), 100, 100) == (90, 90, 10, 10)
    assert clip_coco((-10, -10, 30, 30), 100, 100) == (0, 0, 20, 20)


def test_clip_fully_outside_gives_zero() -> None:
    x, y, w, h = clip_coco((200, 200, 10, 10), 100, 100)
    assert (w, h) == (0.0, 0.0)
    assert area((x, y, w, h)) == 0.0


def test_iou_cases() -> None:
    box = (0, 0, 10, 10)
    assert iou(box, box) == pytest.approx(1.0)
    assert iou(box, (20, 20, 10, 10)) == 0.0
    # 平移一半: 交集 50, 并集 150
    assert iou(box, (5, 0, 10, 10)) == pytest.approx(1 / 3)


def test_invalid_size() -> None:
    with pytest.raises(ValueError):
        coco_to_yolo((0, 0, 1, 1), 0, 100)
    with pytest.raises(ValueError):
        yolo_to_coco((0.5, 0.5, 0.1, 0.1), 100, -1)
''',
}
