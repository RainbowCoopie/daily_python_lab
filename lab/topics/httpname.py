'''HTTP 头解析: Content-Disposition 文件名(含 RFC 5987/8187 的 filename*) 与 Range 分段。

灵感来源:
- MDN 讲得很清楚: filename* 用 RFC 5987 第 3.2 节的编码, 两者同时存在时 filename* 优先;
  服务端应同时提供 filename 作为兜底, 因为老客户端不认带星号的那个
  (https://mdn.org.cn/en-US/docs/Web/HTTP/Reference/Headers/Content-Disposition)
- 一份现成实现的做法值得抄: 只解 UTF-8 与 ISO-8859-1, 格式坏或用了别的字符集就忽略,
  退回普通的 filename
  (https://pypi.org/project/contentdisp/0.2.1/)
- 中文文件名乱码的真实复盘: 头字段本身是 ASCII 世界, 中文塞进去必然出问题,
  而且 IE 不认 filename*, 只写那一句在政务环境里会翻车
  (https://cloud.tencent.com.cn/developer/article/2717428)
- Range 的语法来自 HTTP/1.1 分段请求: byte-range-spec 与 suffix-byte-range-spec 两种形态
  (https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-p5-range-17)

为什么值得单独做一层: 爬虫下载文件时, 名字几乎总是从 Content-Disposition 里来的。
这里"解析"和"能不能落盘"必须分开 —— 本模块只负责按 RFC 解出正确的字符串,
把它变成安全的文件名是另一个模块(winname)的事。混在一起会导致: 解析规则被安全规则污染,
该保真的中文名被提前改掉了。
'''

SLUG = "httpname"
TITLE = "下载文件名与分段请求解析"
TAGS = ["HTTP 头", "RFC 6266", "中文文件名", "Range"]
PKG = "httpname"
SUMMARY = '解析 Content-Disposition 取下载文件名(filename* 优先, 中文不乱码), 以及 Range 分段请求。'
STACK_NOTES = [
    "filename* 按 RFC 5987 解: 只认 utf-8 与 iso-8859-1, 坏值或别的字符集一律忽略并退回 filename",
    "参数切分自己做, 处理引号内的分号与转义引号 —— 用 split(';') 会把文件名切碎",
    "Range 区分三种形态: 闭区间、开区间、后缀区间, 并提供按文件大小落地成具体字节区间",
]
NOTES = """
两个头, 各自的坑:

**Content-Disposition** 的关键在于"两个文件名并存时听谁的"。按 RFC 6266 第 4.3 节,
`filename*` 优先; 但 `filename*` 可能解析失败(缺字符集、字符集不支持、百分号编码坏掉),
这时必须干净地退回 `filename`, 而不是抛错或者返回空 —— 下载流程不能因为一个头写错就断。

**Range** 有三种写法, 语义完全不同:
- `bytes=0-499` 前 500 字节
- `bytes=500-` 从 500 到结尾
- `bytes=-500` 最后 500 字节(注意这里数字是"长度", 不是位置)

第三种最容易写错: 它算的是**倒数的长度**, 要靠文件总大小才能落成具体区间,
所以提供 `resolve(size)` 而不是直接返回一对数字。
"""

FILES = {
    "httpname/__init__.py": '''from .disposition import Disposition, parse_content_disposition
from .ranges import ByteRange, parse_ranges

__all__ = ["Disposition", "parse_content_disposition", "ByteRange", "parse_ranges"]
''',
    "httpname/disposition.py": '''# Content-Disposition: 取文件名, filename* 优先。
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import unquote_to_bytes

SUPPORTED_CHARSETS = {"utf-8", "iso-8859-1"}


@dataclass
class Disposition:
    kind: str = ""
    params: dict[str, str] = field(default_factory=dict)
    filename: str | None = None
    filename_star: str | None = None

    @property
    def is_attachment(self) -> bool:
        return self.kind.lower() == "attachment"


def split_unquoted(text: str, sep: str = ";") -> list[str]:
    """按分隔符切分, 但跳过引号内的分隔符; 支持反斜杠转义。"""
    parts: list[str] = []
    buf: list[str] = []
    quoted = False
    escaped = False
    for ch in text:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\\\" and quoted:
            escaped = True
            continue
        if ch == '"':
            quoted = not quoted
            buf.append(ch)
            continue
        if ch == sep and not quoted:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return [part.strip() for part in parts if part.strip()]


def unquote(value: str) -> str:
    body = value.strip()
    if len(body) >= 2 and body[0] == '"' and body[-1] == '"':
        inner = body[1:-1]
        out: list[str] = []
        escaped = False
        for ch in inner:
            if escaped:
                out.append(ch)
                escaped = False
            elif ch == "\\\\":
                escaped = True
            else:
                out.append(ch)
        return "".join(out)
    return body


def decode_ext_value(value: str) -> str | None:
    """解 RFC 5987 的 charset'lang'percent-encoded 形式; 不支持就返回 None。"""
    pieces = value.split("'", 2)
    if len(pieces) != 3:
        return None
    charset, _language, encoded = pieces
    charset = charset.strip().lower()
    if charset not in SUPPORTED_CHARSETS:
        return None
    try:
        raw = unquote_to_bytes(encoded)
        return raw.decode(charset)
    except (UnicodeDecodeError, ValueError):
        return None


def parse_content_disposition(header: str) -> Disposition:
    """解析 Content-Disposition; 无法识别的部分跳过, 不让整个下载流程失败。"""
    pieces = split_unquoted(str(header))
    if not pieces:
        return Disposition()

    result = Disposition(kind=pieces[0].strip())
    for piece in pieces[1:]:
        key, _, raw_value = piece.partition("=")
        key = key.strip().lower()
        if not key:
            continue
        result.params[key] = unquote(raw_value)

    plain = result.params.get("filename")
    extended = result.params.get("filename*")
    result.filename_star = decode_ext_value(extended) if extended else None
    result.filename = result.filename_star or plain
    return result
''',
    "httpname/ranges.py": '''# Range: bytes=first-last / first- / -suffix。
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRange:
    first: int | None
    last: int | None
    suffix: bool = False

    def resolve(self, size: int) -> tuple[int, int]:
        """按文件总大小落成具体的 (起始字节, 结束字节), 闭区间。"""
        if size < 0:
            raise ValueError("size 不能为负")
        if size == 0:
            return (0, -1)
        if self.suffix:
            length = min(self.last or 0, size)
            return (size - length, size - 1)
        start = self.first or 0
        end = size - 1 if self.last is None else min(self.last, size - 1)
        return (start, end)


def _digits(text: str) -> int | None:
    body = text.strip()
    if not body.isdigit():
        return None
    return int(body)


def parse_ranges(header: str) -> list[ByteRange] | None:
    """解析 Range 头。单位不是 bytes 或语法不合法时返回 None。"""
    body = str(header).strip()
    unit, _, spec = body.partition("=")
    if unit.strip().lower() != "bytes" or not spec.strip():
        return None

    parsed: list[ByteRange] = []
    for chunk in spec.split(","):
        part = chunk.strip()
        if not part or "-" not in part:
            return None
        left, _, right = part.partition("-")
        left, right = left.strip(), right.strip()

        if not left:
            length = _digits(right)
            if length is None or length == 0:
                return None
            parsed.append(ByteRange(first=None, last=length, suffix=True))
            continue

        start = _digits(left)
        if start is None:
            return None
        if not right:
            parsed.append(ByteRange(first=start, last=None))
            continue
        end = _digits(right)
        if end is None or end < start:
            return None
        parsed.append(ByteRange(first=start, last=end))

    return parsed or None
''',
    "tests/test_disposition.py": '''import pytest

from httpname import parse_content_disposition


def test_plain_filename() -> None:
    result = parse_content_disposition('attachment; filename="report.xlsx"')
    assert result.kind == "attachment"
    assert result.is_attachment is True
    assert result.filename == "report.xlsx"


def test_inline_is_not_attachment() -> None:
    result = parse_content_disposition('inline; filename="a.png"')
    assert result.kind == "inline"
    assert result.is_attachment is False


def test_filename_star_decoded() -> None:
    header = "attachment; filename*=UTF-8''%E6%8A%A5%E8%A1%A8.xlsx"
    assert parse_content_disposition(header).filename == "\\u62a5\\u8868.xlsx"


def test_filename_star_wins_over_plain() -> None:
    header = (
        'attachment; filename="fallback.xlsx"; '
        "filename*=UTF-8''%E6%8A%A5%E8%A1%A8.xlsx"
    )
    result = parse_content_disposition(header)
    assert result.filename == "\\u62a5\\u8868.xlsx"
    assert result.params["filename"] == "fallback.xlsx"


def test_broken_filename_star_falls_back() -> None:
    header = 'attachment; filename="fallback.xlsx"; filename*=not-a-valid-value'
    assert parse_content_disposition(header).filename == "fallback.xlsx"


def test_unsupported_charset_falls_back() -> None:
    header = 'attachment; filename="fallback.xlsx"; filename*=GBK\\'\\'%B1%A8%B1%ED'
    assert parse_content_disposition(header).filename == "fallback.xlsx"


def test_iso8859_1_supported() -> None:
    header = "attachment; filename*=ISO-8859-1''caf%E9.txt"
    assert parse_content_disposition(header).filename == "caf\\u00e9.txt"


def test_semicolon_inside_quotes_is_kept() -> None:
    result = parse_content_disposition('attachment; filename="a;b.txt"')
    assert result.filename == "a;b.txt"


def test_escaped_quote_inside_name() -> None:
    result = parse_content_disposition('attachment; filename="a\\\\"b.txt"')
    assert result.filename == 'a"b.txt'


def test_multiple_params() -> None:
    result = parse_content_disposition('attachment; filename="a.txt"; size=123')
    assert result.params["size"] == "123"


def test_empty_header() -> None:
    result = parse_content_disposition("")
    assert result.kind == ""
    assert result.filename is None


def test_no_filename_at_all() -> None:
    assert parse_content_disposition("attachment").filename is None


def test_keys_are_lowercased() -> None:
    result = parse_content_disposition('ATTACHMENT; FILENAME="a.txt"')
    assert result.kind == "ATTACHMENT"
    assert result.filename == "a.txt"


def test_is_attachment_case_insensitive() -> None:
    assert parse_content_disposition("Attachment; filename=a.txt").is_attachment is True
''',
    "tests/test_ranges.py": '''import pytest

from httpname import ByteRange, parse_ranges


def test_closed_range() -> None:
    ranges = parse_ranges("bytes=0-499")
    assert ranges == [ByteRange(first=0, last=499)]


def test_open_ended_range() -> None:
    ranges = parse_ranges("bytes=500-")
    assert ranges == [ByteRange(first=500, last=None)]


def test_suffix_range() -> None:
    ranges = parse_ranges("bytes=-500")
    assert ranges == [ByteRange(first=None, last=500, suffix=True)]


def test_multiple_ranges() -> None:
    assert len(parse_ranges("bytes=0-1, 5-6")) == 2


def test_unit_must_be_bytes() -> None:
    assert parse_ranges("items=0-1") is None


def test_invalid_syntax_returns_none() -> None:
    for bad in ("", "bytes=", "bytes=abc", "bytes=5", "bytes=5-1", "bytes=-0", "bytes=0-" + "x"):
        assert parse_ranges(bad) is None, bad


def test_resolve_closed_range() -> None:
    assert parse_ranges("bytes=0-499")[0].resolve(1000) == (0, 499)


def test_resolve_open_ended_uses_size() -> None:
    assert parse_ranges("bytes=500-")[0].resolve(1000) == (500, 999)


def test_resolve_suffix_counts_from_end() -> None:
    """-500 表示"最后 500 字节", 不是"第 -500 字节"。"""
    assert parse_ranges("bytes=-500")[0].resolve(1000) == (500, 999)


def test_resolve_suffix_larger_than_file() -> None:
    assert parse_ranges("bytes=-500")[0].resolve(100) == (0, 99)


def test_resolve_clamps_end() -> None:
    assert parse_ranges("bytes=0-9999")[0].resolve(1000) == (0, 999)


def test_resolve_empty_file() -> None:
    assert parse_ranges("bytes=0-10")[0].resolve(0) == (0, -1)


def test_resolve_rejects_negative_size() -> None:
    with pytest.raises(ValueError):
        parse_ranges("bytes=0-1")[0].resolve(-1)


def test_zero_length_closed_range() -> None:
    assert parse_ranges("bytes=0-0")[0].resolve(10) == (0, 0)
''',
}

CHALLENGE = {
    "target": "httpname/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 httpname/challenge.py 中实现 describe(header: str, size: int) -> str: "
        "解析 Content-Disposition, 返回 'attachment 报表.xlsx 1000B' 这样的描述; "
        "没有文件名时用 'unnamed'。复用 httpname.disposition.parse_content_disposition, "
        "不得修改其他模块。"
    ),
    "tests_content": '''from httpname.challenge import describe


def test_with_plain_name() -> None:
    assert describe('attachment; filename="a.txt"', 1000) == "attachment a.txt 1000B"


def test_with_extended_name() -> None:
    header = "attachment; filename*=UTF-8''%E6%8A%A5%E8%A1%A8.xlsx"
    assert describe(header, 512) == "attachment \\u62a5\\u8868.xlsx 512B"


def test_missing_name() -> None:
    assert describe("inline", 0) == "inline unnamed 0B"
''',
}
