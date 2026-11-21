# Content-Disposition: 取文件名, filename* 优先。
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
        if ch == "\\" and quoted:
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
            elif ch == "\\":
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
