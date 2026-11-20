# 模板挖掘: 分桶 + 相似度合并。
from __future__ import annotations

from dataclasses import dataclass, field

from .mask import mask_token, tokenize

WILDCARD = "<*>"


@dataclass
class Template:
    id: int
    tokens: tuple[str, ...]
    count: int = 0

    @property
    def text(self) -> str:
        return " ".join(self.tokens)

    def __str__(self) -> str:
        return self.text


def similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    """位置相同的比例; 任一侧已是 <*> 也算相同。"""
    if len(left) != len(right):
        return 0.0
    if not left:
        return 1.0
    same = sum(1 for a, b in zip(left, right) if a == b or a == WILDCARD or b == WILDCARD)
    return same / len(left)


def _merge(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(a if a == b else WILDCARD for a, b in zip(left, right))


class Miner:
    """按 token 数分桶, 桶内按相似度合并。"""

    def __init__(self, similarity_threshold: float = 0.5) -> None:
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("阈值必须在 0..1")
        self.similarity_threshold = similarity_threshold
        self._buckets: dict[int, list[Template]] = {}
        self._by_id: dict[int, Template] = {}
        self._next_id = 1

    def add(self, line: str) -> Template:
        tokens = tuple(mask_token(token) for token in tokenize(line))
        if not tokens:
            raise ValueError("空行没有模板")

        bucket = self._buckets.setdefault(len(tokens), [])
        best: Template | None = None
        best_score = -1.0
        for candidate in bucket:
            score = similarity(candidate.tokens, tokens)
            if score > best_score:
                best, best_score = candidate, score

        if best is not None and best_score >= self.similarity_threshold:
            best.tokens = _merge(best.tokens, tokens)
            best.count += 1
            return best

        template = Template(id=self._next_id, tokens=tokens, count=1)
        self._next_id += 1
        bucket.append(template)
        self._by_id[template.id] = template
        return template

    def get(self, template_id: int) -> Template:
        return self._by_id[template_id]

    def templates(self) -> list[Template]:
        """按模板编号(即首次出现顺序)返回。"""
        return [self._by_id[key] for key in sorted(self._by_id)]
