# 节点图模型: 校验 + 拓扑排序 + 导出。
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
