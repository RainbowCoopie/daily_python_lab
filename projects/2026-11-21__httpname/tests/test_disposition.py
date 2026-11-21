import pytest

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
    assert parse_content_disposition(header).filename == "\u62a5\u8868.xlsx"


def test_filename_star_wins_over_plain() -> None:
    header = (
        'attachment; filename="fallback.xlsx"; '
        "filename*=UTF-8''%E6%8A%A5%E8%A1%A8.xlsx"
    )
    result = parse_content_disposition(header)
    assert result.filename == "\u62a5\u8868.xlsx"
    assert result.params["filename"] == "fallback.xlsx"


def test_broken_filename_star_falls_back() -> None:
    header = 'attachment; filename="fallback.xlsx"; filename*=not-a-valid-value'
    assert parse_content_disposition(header).filename == "fallback.xlsx"


def test_unsupported_charset_falls_back() -> None:
    header = 'attachment; filename="fallback.xlsx"; filename*=GBK\'\'%B1%A8%B1%ED'
    assert parse_content_disposition(header).filename == "fallback.xlsx"


def test_iso8859_1_supported() -> None:
    header = "attachment; filename*=ISO-8859-1''caf%E9.txt"
    assert parse_content_disposition(header).filename == "caf\u00e9.txt"


def test_semicolon_inside_quotes_is_kept() -> None:
    result = parse_content_disposition('attachment; filename="a;b.txt"')
    assert result.filename == "a;b.txt"


def test_escaped_quote_inside_name() -> None:
    result = parse_content_disposition('attachment; filename="a\\"b.txt"')
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
