'''fastapi 服务的最小可测骨架: 业务逻辑与框架解耦, 没有 fastapi 也能测核心逻辑。'''

SLUG = "fastapi_kv"
TITLE = "带 TTL 的内存 KV 服务"
TAGS = ["FastAPI", "pytest", "接口设计", "依赖解耦"]
PKG = "kvsvc"
SUMMARY = "TTL 键值服务: 存储层不依赖 Web 框架可独立测试, API 层用 FastAPI 暴露 REST 接口, 时钟可注入。"
STACK_NOTES = [
    "TTLStore 注入 clock, 过期逻辑不睡真实时间也能测",
    "FastAPI 层薄到只剩路由, 换框架不伤业务",
    "没有装 fastapi 时自动 skip API 测试, CI 不会红",
]
NOTES = """
约定: 存储层只认 `clock` 这个可调用对象, 默认 `time.monotonic`。测试里塞一个手动推进的假时钟,
过期行为就变成确定性的。API 层用 `create_app(store)` 工厂, 方便测试注入不同 store。
"""

FILES = {
    "kvsvc/__init__.py": '''from .store import TTLStore

__all__ = ["TTLStore"]
''',
    "kvsvc/store.py": '''# 带过期时间的内存 KV, 时钟可注入以便测试。
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class _Entry:
    value: object
    expires_at: float | None


class TTLStore:
    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._data: dict[str, _Entry] = {}
        self._clock = clock or time.monotonic

    def set(self, key: str, value: object, ttl: float | None = None) -> None:
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl 必须为正数, 收到 " + str(ttl))
        expires = None if ttl is None else self._clock() + ttl
        self._data[key] = _Entry(value=value, expires_at=expires)

    def _live(self, key: str) -> _Entry | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and self._clock() >= entry.expires_at:
            del self._data[key]
            return None
        return entry

    def get(self, key: str, default: object = None) -> object:
        entry = self._live(key)
        return default if entry is None else entry.value

    def has(self, key: str) -> bool:
        return self._live(key) is not None

    def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    def purge(self) -> int:
        dead = [k for k in list(self._data) if self._live(k) is None]
        for k in dead:
            self._data.pop(k, None)
        return len(dead)

    def keys(self) -> list[str]:
        return [k for k in list(self._data) if self._live(k) is not None]

    def __len__(self) -> int:
        return len(self.keys())
''',
    "kvsvc/api.py": '''# FastAPI 路由层: 只做参数转换和状态码映射。
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .store import TTLStore


class Item(BaseModel):
    value: object
    ttl: float | None = None


def create_app(store: TTLStore | None = None) -> FastAPI:
    store = store or TTLStore()
    app = FastAPI(title="kvsvc", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "size": len(store)}

    @app.put("/kv/{key}")
    def put(key: str, item: Item) -> dict:
        try:
            store.set(key, item.value, item.ttl)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"key": key, "stored": True}

    @app.get("/kv/{key}")
    def fetch(key: str) -> dict:
        if not store.has(key):
            raise HTTPException(status_code=404, detail="key not found")
        return {"key": key, "value": store.get(key)}

    @app.delete("/kv/{key}")
    def drop(key: str) -> dict:
        if not store.delete(key):
            raise HTTPException(status_code=404, detail="key not found")
        return {"deleted": key}

    return app


app = create_app()
''',
    "tests/test_store.py": '''import pytest

from kvsvc.store import TTLStore


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(clock: FakeClock) -> TTLStore:
    return TTLStore(clock=clock)


def test_set_get_delete(store: TTLStore) -> None:
    store.set("a", 1)
    assert store.get("a") == 1
    assert store.has("a") is True
    assert store.delete("a") is True
    assert store.has("a") is False
    assert store.delete("a") is False


def test_ttl_expires(store: TTLStore, clock: FakeClock) -> None:
    store.set("a", "v", ttl=10)
    clock.advance(9.9)
    assert store.get("a") == "v"
    clock.advance(0.2)
    assert store.get("a") is None
    assert store.has("a") is False


def test_no_ttl_never_expires(store: TTLStore, clock: FakeClock) -> None:
    store.set("a", "v")
    clock.advance(10 ** 6)
    assert store.get("a") == "v"


def test_invalid_ttl(store: TTLStore) -> None:
    with pytest.raises(ValueError):
        store.set("a", 1, ttl=0)
    with pytest.raises(ValueError):
        store.set("a", 1, ttl=-1)


def test_purge_and_keys(store: TTLStore, clock: FakeClock) -> None:
    store.set("a", 1, ttl=1)
    store.set("b", 2)
    clock.advance(2)
    assert store.keys() == ["b"]
    assert store.purge() == 0  # keys() 已经顺手清掉了过期的
    assert len(store) == 1
''',
    "tests/test_api.py": '''import pytest

fastapi = pytest.importorskip("fastapi", reason="未安装 fastapi, 跳过 API 层测试")
pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi.testclient import TestClient  # noqa: E402

from kvsvc.api import create_app  # noqa: E402
from kvsvc.store import TTLStore  # noqa: E402


def test_crud_flow() -> None:
    client = TestClient(create_app(TTLStore()))
    assert client.get("/health").status_code == 200
    assert client.put("/kv/k1", json={"value": {"n": 1}}).status_code == 200
    got = client.get("/kv/k1")
    assert got.status_code == 200
    assert got.json()["value"] == {"n": 1}
    assert client.delete("/kv/k1").status_code == 200
    assert client.get("/kv/k1").status_code == 404


def test_bad_ttl_returns_400() -> None:
    client = TestClient(create_app(TTLStore()))
    assert client.put("/kv/x", json={"value": 1, "ttl": 0}).status_code == 400
''',
    "requirements.txt": "fastapi>=0.110\nuvicorn[standard]>=0.27\nhttpx>=0.27\n# 核心逻辑只用标准库\n",
}

CHALLENGE = {
    "target": "kvsvc/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 kvsvc/challenge.py 中实现 LRU 包装类 LimitedStore: "
        "__init__(self, limit: int, store: TTLStore | None = None) 持有内部 TTLStore, "
        "set(key, value, ttl=None) 在写入后若存活 key 数超过 limit, 淘汰最久未被访问的 key; "
        "get(key) 命中时把该 key 标记为最近使用(用 OrderedDict 或自维护顺序表); "
        "提供 keys() 返回当前存活 key 列表。不得修改 kvsvc/store.py。"
    ),
    "tests_content": '''from kvsvc.challenge import LimitedStore
from kvsvc.store import TTLStore


def test_evicts_least_recently_used() -> None:
    s = LimitedStore(limit=2, store=TTLStore())
    s.set("a", 1)
    s.set("b", 2)
    s.get("a")          # a 变成最近使用
    s.set("c", 3)       # 应淘汰 b
    assert set(s.keys()) == {"a", "c"}


def test_limit_respected() -> None:
    s = LimitedStore(limit=3, store=TTLStore())
    for i in range(10):
        s.set("k" + str(i), i)
    assert len(s.keys()) == 3
''',
}
