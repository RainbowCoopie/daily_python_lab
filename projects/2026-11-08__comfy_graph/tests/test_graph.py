import pytest

from comfygraph import CycleError, DuplicateNode, Graph, GraphError


def build_txt2img() -> Graph:
    g = Graph()
    g.add_node("4", "CheckpointLoaderSimple", ckpt_name="sd_xl.safetensors")
    g.add_node("6", "CLIPTextEncode", text="a cat")
    g.add_node("3", "KSampler", seed=42, steps=20)
    g.link("4", 0, "3", "model")
    g.link("4", 1, "6", "clip")
    g.link("6", 0, "3", "positive")
    return g


def test_topo_order_respects_deps() -> None:
    order = build_txt2img().topo_sort()
    assert order.index("4") < order.index("3")
    assert order.index("4") < order.index("6")
    assert order.index("6") < order.index("3")


def test_duplicate_node() -> None:
    g = Graph()
    g.add_node("1", "A")
    with pytest.raises(DuplicateNode):
        g.add_node("1", "B")


def test_link_requires_both_ends() -> None:
    g = Graph()
    g.add_node("1", "A")
    with pytest.raises(GraphError):
        g.link("1", 0, "2", "x")
    with pytest.raises(GraphError):
        g.link("9", 0, "1", "x")


def test_cycle_detected() -> None:
    g = Graph()
    g.add_node("1", "A")
    g.add_node("2", "B")
    g.link("1", 0, "2", "in")
    g.link("2", 0, "1", "in")
    with pytest.raises(CycleError, match="环"):
        g.topo_sort()


def test_self_loop_is_cycle() -> None:
    g = Graph()
    g.add_node("1", "A")
    g.link("1", 0, "1", "in")
    with pytest.raises(CycleError):
        g.topo_sort()


def test_missing_deps() -> None:
    g = Graph()
    g.add_node("1", "A")
    g.nodes["1"].inputs["model"] = ["9", 0]
    assert g.missing_deps() == ["9"]
    assert g.topo_sort() == ["1"]


def test_to_prompt_shape() -> None:
    prompt = build_txt2img().to_prompt()
    assert prompt["3"]["class_type"] == "KSampler"
    assert prompt["3"]["inputs"]["positive"] == ["6", 0]
    assert prompt["4"]["inputs"]["ckpt_name"] == "sd_xl.safetensors"
