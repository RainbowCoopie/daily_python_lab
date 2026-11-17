'''Windows 文件名清洗: 非法字符、保留设备名、尾部空格与点、路径穿越、长度截断。

灵感来源:
- 保留设备名清单: CON PRN AUX NUL CLOCK$ COM1-9 LPT1-9, 且带扩展名同样危险(NUL.txt)
  (https://learn.microsoft.com/en-nz/answers/questions/2725570/folder-names)
- 上标变体 COM¹ COM² COM³ LPT¹ LPT² LPT³ 也算 (Naming Files, Paths, and Namespaces)
  (https://learn.microsoft.com/en-us/answers/questions/3878903/no-error-dialog-message-when-creating-a-file-with)
- 首尾 ASCII 空格与尾部句点会被文件系统静默丢弃, 于是"写进去的名字"和"看到的名字"不一致
  (https://learn.microsoft.com/sk-sk/troubleshoot/windows-client/shell-experience/file-folder-name-whitespace-characters)

为什么值得单独做一层: 爬虫和 RPA 每天都在"用别人给的名字存文件"。
Content-Disposition 里带个冒号、报表名以句点结尾、导出叫 CON.csv —— 这些都会让
落盘静默变形或者直接失败, 而失败点往往离取名的地方很远, 排查成本极高。
本模块只做一件事: 给一个任意字符串, 返回一个 Windows 上一定能存住的名字。
'''

SLUG = "winname"
TITLE = "Windows 文件名清洗"
TAGS = ["文件名", "保留设备名", "路径穿越", "爬虫/下载"]
PKG = "winname"
SUMMARY = "把任意字符串洗成 Windows 上一定能落盘的文件名: 非法字符、保留设备名、尾部点空格、长度截断。"
STACK_NOTES = [
    "保留名按第一个点之前的部分判断, 所以 COM1.tar.gz 也算危险",
    "非法字符整段替换成一个分隔符, 不会产生连续下划线破坏可读性",
    "先截断再复检尾部点与空格, 避免截断本身又造出非法名字",
]
NOTES = """
Windows 的文件名有三层坑, 从浅到深:

1. **非法字符** `< > : " / \\ | ? *` 与 0x00-0x1F 控制符。这一段最好办, 替换掉即可。
2. **保留设备名**。CON / PRN / AUX / NUL / CLOCK$ / COM1-9 / LPT1-9 是设备,
   不是文件。即使写成 `NUL.txt` 也仍然指向设备。判断时要取**第一个点之前**的部分,
   所以 `COM1.tar.gz` 同样不安全。
3. **尾部空格与句点**。NTFS 本身允许, 但 Win32 子系统会静默丢弃,
   结果是"你以为存成了 '报表.' 其实存成了 '报表'", 甚至出现删不掉的文件。

另外顺手处理两件事: 路径分隔符之后只取最后一段(防 `../../etc/passwd`),
以及超长名字要截断但保住扩展名。

明确不处理的: 双扩展名伪装(`evil.txt.exe`)。它合法, 该由上层做类型判断,
在这一层拦是错的位置。
"""

FILES = {
    "winname/__init__.py": '''from .sanitize import RESERVED, is_reserved, is_safe, sanitize, split_ext

__all__ = ["RESERVED", "is_reserved", "is_safe", "sanitize", "split_ext"]
''',
    "winname/sanitize.py": '''# 文件名清洗: 只保证"能落盘", 不猜业务意图。
from __future__ import annotations

import re
import unicodedata

REPLACEMENT = "_"
ILLEGAL_RUN = re.compile(r'[<>:"/\\\\|?*\\x00-\\x1f]+')
TRAILING = re.compile(r"[ .]+$")
PATH_SEP = re.compile(r"[\\\\/]+")
MAX_EXT_LEN = 10

RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
    | {"COM\\u00b9", "COM\\u00b2", "COM\\u00b3", "LPT\\u00b9", "LPT\\u00b2", "LPT\\u00b3"}
)


def split_ext(name: str) -> tuple[str, str]:
    """拆主名与扩展名; 扩展名超过 10 个字符或含空格时视为没有扩展名。"""
    if "." not in name:
        return name, ""
    stem, ext = name.rsplit(".", 1)
    if not ext or len(ext) > MAX_EXT_LEN or " " in ext:
        return name, ""
    return stem, "." + ext


def is_reserved(name: str) -> bool:
    """按第一个点之前的部分判断, 所以 COM1.tar.gz 也算危险。"""
    base = name.split(".")[0].strip().upper()
    return base in RESERVED


def sanitize(
    name: str,
    replacement: str = REPLACEMENT,
    max_len: int = 120,
    fallback: str = "unnamed",
) -> str:
    """返回一个 Windows 上一定能落盘的文件名。"""
    if max_len < 1:
        raise ValueError("max_len 必须 >= 1")

    text = unicodedata.normalize("NFC", str(name))
    text = PATH_SEP.split(text)[-1]          # 只取最后一段, 防路径穿越
    if text in ("", ".", ".."):
        return fallback

    text = ILLEGAL_RUN.sub(replacement, text)
    text = text.strip(" ")

    stem, ext = split_ext(text)
    stem = TRAILING.sub("", stem)            # 主名尾部的空格与句点必须去掉
    if not stem:
        return fallback
    text = stem + ext

    if is_reserved(text):
        text = replacement + text

    if len(text) > max_len:
        stem, ext = split_ext(text)
        if len(ext) >= max_len:
            text = stem[:max_len]
        else:
            text = stem[: max_len - len(ext)] + ext

    text = TRAILING.sub("", text)            # 截断可能又造出尾部空格
    return text or fallback


def is_safe(name: str) -> bool:
    """这个字符串能不能原样落盘。"""
    return sanitize(name) == name
''',
    "tests/test_sanitize.py": '''import pytest

from winname import RESERVED, is_reserved, is_safe, sanitize, split_ext


def test_illegal_chars_collapse_into_one_separator() -> None:
    assert sanitize("my<file>:v2.txt") == "my_file_v2.txt"


def test_each_illegal_char_family() -> None:
    assert sanitize("a|b|c?d*e.txt") == "a_b_c_d_e.txt"
    assert sanitize('q"w.txt') == "q_w.txt"


def test_backslash_is_path_separator_not_illegal_char() -> None:
    """先按路径切, 再谈非法字符: 所以反斜杠永远走不到替换那一步。"""
    assert sanitize("a\\\\b\\\\c.txt") == "c.txt"


def test_control_characters_replaced() -> None:
    assert sanitize("a\\x01b.txt") == "a_b.txt"


def test_path_traversal_keeps_last_segment() -> None:
    assert sanitize("../../etc/passwd") == "passwd"
    assert sanitize("C:\\\\Users\\\\report.xlsx") == "report.xlsx"


def test_dot_only_names_fall_back() -> None:
    assert sanitize("") == "unnamed"
    assert sanitize(".") == "unnamed"
    assert sanitize("..") == "unnamed"
    assert sanitize("...") == "unnamed"


def test_trailing_space_and_dot_removed() -> None:
    assert sanitize("report.") == "report"
    assert sanitize("report ") == "report"
    assert sanitize("a .txt") == "a.txt"


def test_leading_space_removed() -> None:
    assert sanitize(" report.txt") == "report.txt"


@pytest.mark.parametrize("name", ["CON", "con", "PRN", "AUX", "NUL", "CLOCK$"])
def test_reserved_names_prefixed(name: str) -> None:
    assert sanitize(name) == "_" + name


@pytest.mark.parametrize("name", ["CON.txt", "nul.log", "AUX.csv"])
def test_reserved_names_with_extension_prefixed(name: str) -> None:
    assert sanitize(name) == "_" + name


def test_reserved_check_uses_part_before_first_dot() -> None:
    assert is_reserved("COM1.tar.gz") is True
    assert sanitize("COM1.tar.gz") == "_COM1.tar.gz"


def test_reserved_superscript_variants() -> None:
    assert is_reserved("COM\\u00b9.txt") is True


def test_not_reserved_names_pass_through() -> None:
    assert is_reserved("COM0") is False
    assert is_reserved("report.txt") is False
    assert sanitize("console.txt") == "console.txt"


def test_cjk_names_untouched() -> None:
    assert sanitize("月度报表（终版）.xlsx") == "月度报表（终版）.xlsx"


def test_length_truncation_keeps_extension() -> None:
    long_name = "x" * 200 + ".txt"
    result = sanitize(long_name, max_len=20)
    assert len(result) == 20
    assert result.endswith(".txt")


def test_length_truncation_without_extension() -> None:
    assert sanitize("y" * 50, max_len=10) == "y" * 10


def test_truncation_does_not_leave_trailing_space() -> None:
    result = sanitize("a" * 18 + " .txt", max_len=20)
    assert not result.endswith(" ")
    assert not result.endswith(".")


def test_split_ext() -> None:
    assert split_ext("a.txt") == ("a", ".txt")
    assert split_ext("a.tar.gz") == ("a.tar", ".gz")
    assert split_ext("noext") == ("noext", "")
    assert split_ext("trailing.") == ("trailing.", "")
    assert split_ext("a.longextension") == ("a.longextension", "")
    assert split_ext("a. wi th") == ("a. wi th", "")


def test_sanitize_rejects_bad_max_len() -> None:
    with pytest.raises(ValueError):
        sanitize("a.txt", max_len=0)


def test_is_safe_round_trip() -> None:
    assert is_safe("report.txt") is True
    assert is_safe("月度报表.xlsx") is True
    assert is_safe("CON.txt") is False
    assert is_safe("a<b.txt") is False
    assert is_safe("report.") is False


def test_double_extension_left_alone() -> None:
    # 合法, 该由上层判断类型, 不在这一层拦
    assert sanitize("evil.txt.exe") == "evil.txt.exe"


def test_result_is_idempotent() -> None:
    samples = ["CON.txt", "../a<b>.txt", "report.", "x" * 200 + ".txt", "中文.xlsx"]
    for sample in samples:
        once = sanitize(sample)
        assert sanitize(once) == once


def test_reserved_set_contents() -> None:
    assert "CON" in RESERVED
    assert "LPT9" in RESERVED
    assert "COM1" in RESERVED
    assert "COM10" not in RESERVED
''',
}

CHALLENGE = {
    "target": "winname/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 winname/challenge.py 中实现 unique_names(names: list[str]) -> list[str]: "
        "先用 winname.sanitize 清洗每个名字, 再去重: 重名的在扩展名前加 _2、_3 递增, "
        "保持输入顺序。不得修改其他模块。"
    ),
    "tests_content": '''from winname.challenge import unique_names


def test_no_conflict() -> None:
    assert unique_names(["a.txt", "b.txt"]) == ["a.txt", "b.txt"]


def test_conflict_gets_suffix() -> None:
    assert unique_names(["a.txt", "a.txt", "a.txt"]) == ["a.txt", "a_2.txt", "a_3.txt"]


def test_conflict_after_sanitize() -> None:
    assert unique_names(["a<b.txt", "a>b.txt"]) == ["a_b.txt", "a_b_2.txt"]
''',
}
