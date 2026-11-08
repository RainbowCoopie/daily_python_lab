'''带延迟与优先级的任务池: 队列逻辑不依赖 Redis / Kafka, 换后端只改一层适配。'''

SLUG = "queue_pool"
TITLE = "延迟 + 优先级任务池"
TAGS = ["消息队列", "Kafka 思路", "优先级调度", "时间可注入"]
PKG = "taskpool"
SUMMARY = "支持任务延迟投递、优先级抢占、失败重投的内存任务池, 时间由调用方传入, 行为完全确定。"
STACK_NOTES = [
    "优先级高的先出, 同优先级按入队先后, 延迟未到不出现",
    "重投把任务的 run_at 推后, 不禁用也不丢",
    "next_run_at 让调度层知道下一次该在什么时候醒",
]
NOTES = """
Kafka 里这类需求通常靠重试 topic + 延迟级别实现, 本地调试时太重。
这里先把手感做对: push 带 run_at, pop_ready(now) 只吐已经到点的任务,
同优先级退化成 FIFO, 重投只是把 run_at 往后推。接真实 broker 时把这层当内存缓冲即可。
"""

FILES = {
    "taskpool/__init__.py": '''from .queue import DelayQueue, Task

__all__ = ["Task", "DelayQueue"]
''',
    "taskpool/queue.py": '''# 内存任务池: 优先级 + 延迟 + 重投。
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    id: str
    payload: object = None
    priority: int = 0
    run_at: float = 0.0
    attempts: int = 0


class DelayQueue:
    def __init__(self) -> None:
        self._seq = 0
        self._items: list[tuple[int, Task]] = []

    def push(self, task: Task, now: float = 0.0) -> None:
        """入队; run_at 早于 now 的任务立即视为可执行。"""
        if task.run_at < now:
            task.run_at = now
        self._seq += 1
        self._items.append((self._seq, task))

    def pop_ready(self, now: float) -> Task | None:
        """取出最高优先级且已到点的任务; 同优先级按入队顺序。"""
        ready = [(seq, task) for seq, task in self._items if task.run_at <= now]
        if not ready:
            return None
        seq, task = max(ready, key=lambda item: (item[1].priority, -item[1].run_at, -item[0]))
        self._items = [item for item in self._items if item[0] != seq]
        task.attempts += 1
        return task

    def reschedule(self, task: Task, now: float, delay: float) -> None:
        """失败重投: 推后 run_at 再入队。"""
        if delay < 0:
            raise ValueError("delay 不能为负")
        task.run_at = now + delay
        self.push(task, now)

    def next_run_at(self) -> float | None:
        return min((task.run_at for _, task in self._items), default=None)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, task_id: object) -> bool:
        return any(task.id == task_id for _, task in self._items)
''',
    "tests/test_queue.py": '''import pytest

from taskpool import DelayQueue, Task


def test_priority_order() -> None:
    q = DelayQueue()
    q.push(Task("low", priority=1))
    q.push(Task("high", priority=9))
    q.push(Task("mid", priority=5))
    assert [q.pop_ready(0).id for _ in range(3)] == ["high", "mid", "low"]
    assert len(q) == 0


def test_same_priority_is_fifo() -> None:
    q = DelayQueue()
    for name in ("a", "b", "c"):
        q.push(Task(name))
    assert [q.pop_ready(0).id for _ in range(3)] == ["a", "b", "c"]


def test_delayed_task_not_ready() -> None:
    q = DelayQueue()
    q.push(Task("later", run_at=10.0))
    assert q.pop_ready(5.0) is None
    assert q.next_run_at() == 10.0
    assert q.pop_ready(10.0).id == "later"


def test_push_clamps_past_run_at() -> None:
    q = DelayQueue()
    q.push(Task("x", run_at=1.0), now=5.0)
    assert q.next_run_at() == 5.0
    assert q.pop_ready(5.0).id == "x"


def test_attempts_increments() -> None:
    q = DelayQueue()
    q.push(Task("x"))
    task = q.pop_ready(0)
    assert task.attempts == 1


def test_reschedule() -> None:
    q = DelayQueue()
    q.push(Task("x"))
    task = q.pop_ready(0)
    q.reschedule(task, now=0.0, delay=3.0)
    assert "x" in q
    assert q.pop_ready(2.9) is None
    assert q.pop_ready(3.0).id == "x"
    assert "x" not in q


def test_reschedule_rejects_negative_delay() -> None:
    q = DelayQueue()
    task = Task("x")
    with pytest.raises(ValueError):
        q.reschedule(task, now=0.0, delay=-1)
''',
}

CHALLENGE = {
    "target": "taskpool/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 taskpool/challenge.py 中实现 drain_ready(queue: DelayQueue, now: float, limit: int) -> list[Task]: "
        "循环调用 queue.pop_ready(now), 最多取出 limit 个任务并按取出顺序返回; "
        "队列空时提前返回; limit <= 0 时返回空列表且不触碰队列。"
        "必须复用 taskpool.queue.DelayQueue, 不得修改它。"
    ),
    "tests_content": '''from taskpool import DelayQueue, Task
from taskpool.challenge import drain_ready


def test_drains_in_priority_order() -> None:
    q = DelayQueue()
    q.push(Task("a", priority=1))
    q.push(Task("b", priority=5))
    assert [t.id for t in drain_ready(q, 0.0, limit=5)] == ["b", "a"]
    assert len(q) == 0


def test_respects_limit() -> None:
    q = DelayQueue()
    for i in range(5):
        q.push(Task(str(i)))
    got = drain_ready(q, 0.0, limit=2)
    assert len(got) == 2
    assert len(q) == 3


def test_zero_limit_keeps_queue() -> None:
    q = DelayQueue()
    q.push(Task("a"))
    assert drain_ready(q, 0.0, limit=0) == []
    assert len(q) == 1
''',
}
