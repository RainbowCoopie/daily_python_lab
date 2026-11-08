'''ComfyUI 工作流的图模型: 节点、连线、拓扑排序、环检测, 以及导出成 API prompt 格式。'''

SLUG = "comfy_graph"
TITLE = "ComfyUI 工作流图校验器"
TAGS = ["ComfyUI", "DAG", "拓扑排序", "环检测"]
PKG = "comfygraph"
SUMMARY = "把 ComfyUI 那种节点连线结构建模成有向图, 提交前先查出断链和环, 不用等跑起来才发现报错。"
STACK_NOTES = [
    "Kahn 算法做拓扑排序, 有环直接抛 CycleError 并说明原因",
    "missing_deps 在推送工作流前就能定位断掉的上游节点",
    "to_prompt 输出与 /prompt 接口一致的结构, 可直接拿去请求",
]
NOTES = """
ComfyUI 的工作流 JSON 里, 一个节点的输入值要么是字面量, 要么是 `[上游节点 id, 输出槽位]`。
这种"字面量和引用混在同一个 dict"的结构最容易出问题。这里用显式 Graph 类承接:
link() 校验两端存在, topo_sort() 保证执行顺序, to_prompt() 负责吐出接口要的格式。
"""

FILES = {
    "comfygraph/__init__.py": '''from .graph import CycleError, DuplicateNode, Graph, GraphError, Node

__all__ = ["Graph", "Node", "GraphError", "CycleError", "DuplicateNode"]
''',
    "comfygraph/graph.py": '''# 节点图模型: 校验 + 拓扑排序 + 导出。
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class GraphError(Exception):
    """图结构非法。"""


class DuplicateNode(GraphError):
    """节点 id 重复。"""


class CycleError(GraphError):
    """图里存在环, 无法确定执行顺序。"""


@dataclass
class Node:
    id: str
    class_type: str
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)

    def add_node(self, node_id: str, class_type: str, **inputs: Any) -> Node:
        if node_id in self.nodes:
            raise DuplicateNode(f"节点 {node_id} 已存在")
        node = Node(id=node_id, class_type=class_type, inputs=dict(inputs))
        self.nodes[node_id] = node
        return node

    def link(self, src: str, slot: int, dst: str, field_name: str) -> None:
        if src not in self.nodes:
            raise GraphError(f"上游节点 {src} 不存在")
        if dst not in self.nodes:
            raise GraphError(f"下游节点 {dst} 不存在")
        self.nodes[dst].inputs[field_name] = [src, slot]

    @staticmethod
    def _deps(node: Node) -> list[str]:
        out: list[str] = []
        for value in node.inputs.values():
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
            ):
                out.append(value[0])
        return out

    def missing_deps(self) -> list[str]:
        """引用了但没注册的上游节点。"""
        missing: set[str] = set()
        for node in self.nodes.values():
            for dep in self._deps(node):
                if dep not in self.nodes:
                    missing.add(dep)
        return sorted(missing)

    def topo_sort(self) -> list[str]:
        indegree = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in self._deps(node):
                if dep in indegree:
                    indegree[node.id] += 1
        ready = sorted(nid for nid, deg in indegree.items() if deg == 0)
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for node in self.nodes.values():
                if current in self._deps(node):
                    indegree[node.id] -= 1
                    if indegree[node.id] == 0:
                        ready.append(node.id)
                        ready.sort()
        if len(order) != len(self.nodes):
            stuck = sorted(set(self.nodes) - set(order))
            raise CycleError("图里存在环, 牵涉节点: " + ", ".join(stuck))
        return order

    def to_prompt(self) -> dict[str, dict]:
        return {
            nid: {"class_type": node.class_type, "inputs": dict(node.inputs)}
            for nid, node in self.nodes.items()
        }
''',
    "tests/test_graph.py": '''import pytest

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
''',
}
