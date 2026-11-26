from confcheck import Rule, format_issues, validate


def test_pass_message() -> None:
    assert format_issues([]) == "【配置校验】通过"


def test_issue_lines() -> None:
    issues = validate({"port": "x"}, {"port": Rule(type=int)})
    text = format_issues(issues)
    lines = text.splitlines()
    assert lines[0] == "【配置校验】发现 1 个问题"
    assert lines[1].startswith("- port: ")


def test_root_rendered_as_root() -> None:
    issues = validate([], {"a": Rule(type=int)})
    assert issues[0].path == ""
    assert "<root>" in format_issues(issues)
