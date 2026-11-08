'''最小 LLM 客户端: SSE 流式解析 + 可注入传输层 + 退避重试, 不依赖 openai SDK。'''

SLUG = "llm_client_min"
TITLE = "OpenAI 兼容的最小 LLM 客户端"
TAGS = ["LLM", "SSE 流式解析", "urllib", "可注入传输层"]
PKG = "llmkit"
SUMMARY = "自己写一遍 chat completions 客户端: SSE 分帧、错误重试、传输层可替换, 全程只用标准库。"
STACK_NOTES = [
    "SSE 规范里的多行 data 与 [DONE] 边界都覆盖了",
    "Transport 是协议类, 测试注入假传输层, 不联网",
    "重试次数与退避都显式, 日志里能看到第几次尝试",
]
NOTES = """
直接装 SDK 当然更省事, 但本地 ollama / vLLM / 各家兼容接口的差异全在分帧和错误码上。
自己实现对一遍 SSE 规范, 下次换成流式输出或者接国产网关时不用再翻文档:
`data:` 行可能连续多行合成一个事件, 空行才是事件边界, 注释行以 `:` 开头直接丢。
"""

FILES = {
    "llmkit/__init__.py": '''from .client import ChatClient, ChatError, Transport, UrllibTransport
from .sse import parse_sse

__all__ = ["ChatClient", "ChatError", "Transport", "UrllibTransport", "parse_sse"]
''',
    "llmkit/sse.py": '''# SSE 分帧: 空行是事件边界, 多行 data 用换行拼接, [DONE] 结束。
from __future__ import annotations

import json
from typing import Iterable, Iterator


def parse_sse(lines: Iterable[str]) -> Iterator[dict]:
    buffer: list[str] = []
    for raw in lines:
        line = raw.rstrip("\\r\\n")
        if line == "":
            if not buffer:
                continue
            payload = "\\n".join(buffer)
            buffer.clear()
            if payload == "[DONE]":
                return
            yield json.loads(payload)
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if field == "data":
            buffer.append(value[1:] if value.startswith(" ") else value)
    if buffer:
        payload = "\\n".join(buffer)
        if payload != "[DONE]":
            yield json.loads(payload)
''',
    "llmkit/client.py": '''# OpenAI 兼容的 chat completions 客户端, 传输层与 sleep 都可注入。
from __future__ import annotations

import json
import time
import urllib.request
from typing import Protocol


class Transport(Protocol):
    def post(self, url: str, body: dict, timeout: float) -> str: ...


class UrllibTransport:
    def post(self, url: str, body: dict, timeout: float) -> str:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")


class ChatError(RuntimeError):
    """重试用尽仍失败。"""


class ChatClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        transport: Transport | None = None,
        retries: int = 2,
        timeout: float = 30.0,
        sleep=None,
    ) -> None:
        if retries < 0:
            raise ValueError("retries 不能为负")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport or UrllibTransport()
        self.retries = retries
        self.timeout = timeout
        self._sleep = sleep or time.sleep
        self.calls = 0

    @property
    def url(self) -> str:
        return self.base_url + "/chat/completions"

    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        body = {"model": self.model, "messages": messages, "temperature": temperature}
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            self.calls += 1
            try:
                raw = self.transport.post(self.url, body, self.timeout)
                data = json.loads(raw)
                return data["choices"][0]["message"]["content"]
            except Exception as exc:  # noqa: BLE001 - 网络/解析错误一起退避重试
                last = exc
                if attempt < self.retries:
                    self._sleep(0.5 * (2 ** attempt))
        raise ChatError(f"chat 调用失败: {last}") from last
''',
    "tests/test_sse.py": '''import json

import pytest

from llmkit.sse import parse_sse

STREAM = """data: {"choices":[{"delta":{"content":"你"}}]}

data: {"choices":[{"delta":{"content":"好"}}]}

data: [DONE]

"""


def test_parses_events() -> None:
    events = list(parse_sse(STREAM.splitlines()))
    assert len(events) == 2
    assert events[0]["choices"][0]["delta"]["content"] == "你"
    assert events[1]["choices"][0]["delta"]["content"] == "好"


def test_stops_at_done() -> None:
    lines = STREAM.splitlines() + ['data: {"ignored":1}', ""]
    assert len(list(parse_sse(lines))) == 2


def test_multiline_data_and_comments() -> None:
    lines = [": heartbeat", 'data: {"a":', "data:  1}", ""]
    events = list(parse_sse(lines))
    assert events == [{"a": 1}]


def test_trailing_without_blank_line() -> None:
    assert list(parse_sse(['data: {"x":1}'])) == [{"x": 1}]


def test_bad_json_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        list(parse_sse(["data: {oops}", ""]))
''',
    "tests/test_client.py": '''import json

import pytest

from llmkit.client import ChatClient, ChatError


class FakeTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.bodies: list[dict] = []

    def post(self, url: str, body: dict, timeout: float) -> str:
        self.bodies.append(body)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return json.dumps(item)


def ok(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_returns_content() -> None:
    transport = FakeTransport([ok("你好")])
    client = ChatClient("http://x/v1", "m", transport=transport)
    assert client.chat([{"role": "user", "content": "hi"}]) == "你好"
    assert transport.bodies[0]["model"] == "m"


def test_retries_then_succeeds() -> None:
    transport = FakeTransport([TimeoutError("超时"), ok("ok")])
    delays: list[float] = []
    client = ChatClient("http://x/v1/", "m", transport=transport, retries=2, sleep=delays.append)
    assert client.chat([]) == "ok"
    assert delays == [0.5]
    assert client.calls == 2
    assert client.url == "http://x/v1/chat/completions"


def test_exhausted_raises() -> None:
    transport = FakeTransport([TimeoutError("a"), TimeoutError("b")])
    client = ChatClient("http://x", "m", transport=transport, retries=1, sleep=lambda _: None)
    with pytest.raises(ChatError, match="chat 调用失败"):
        client.chat([])
    assert client.calls == 2


def test_malformed_response_retried() -> None:
    transport = FakeTransport([{"nope": True}, ok("fine")])
    client = ChatClient("http://x", "m", transport=transport, retries=1, sleep=lambda _: None)
    assert client.chat([]) == "fine"


def test_negative_retries_rejected() -> None:
    with pytest.raises(ValueError):
        ChatClient("http://x", "m", transport=FakeTransport([]), retries=-1)
''',
}
