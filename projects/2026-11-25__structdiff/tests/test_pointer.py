from structdiff import pointer
from structdiff.pointer import escape


def test_root_is_empty_string() -> None:
    assert pointer([]) == ""


def test_simple_path() -> None:
    assert pointer(["a", "b"]) == "/a/b"
    assert pointer([0, "name"]) == "/0/name"


def test_escape_slash_then_tilde() -> None:
    """顺序很重要: 先转 ~ 再转 /, 否则 / 会变成 ~1 里的 ~ 被二次转义。"""
    assert escape("a/b") == "a~1b"
    assert escape("m~n") == "m~0n"
    assert escape("a~/b") == "a~0~1b"


def test_pointer_escapes_keys() -> None:
    assert pointer(["a/b"]) == "/a~1b"
    assert pointer(["m~n"]) == "/m~0n"


def test_pointer_empty_key_is_single_slash() -> None:
    """空键名与根节点不同: 前者是 '/', 后者是 ''。"""
    assert pointer([""]) == "/"
    assert pointer([]) == ""


def test_pointer_unicode_key() -> None:
    assert pointer(["名称"]) == "/名称"
