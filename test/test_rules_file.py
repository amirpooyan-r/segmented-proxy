import pytest

from segmentedproxy.main import build_parser, make_settings


def _write_rules_file(path, contents: str) -> str:
    path.write_text(contents, encoding="utf-8")
    return str(path)


def test_rules_file_ignores_blank_and_comments(tmp_path) -> None:
    rules_path = _write_rules_file(
        tmp_path / "rules.txt",
        """
        # comment

        example.com=direct

          # indented comment
        *.example.com=segment_upstream,action=upstream,upstream=127.0.0.1:3128
        """,
    )
    args = build_parser().parse_args(["--rules-file", rules_path])
    settings = make_settings(args)
    hosts = [rule.host_glob for rule in settings.segmentation_rules]
    assert hosts == ["example.com", "*.example.com"]


def test_rules_file_multiple_files_order(tmp_path) -> None:
    first = _write_rules_file(tmp_path / "first.txt", "one.example.com=direct\n")
    second = _write_rules_file(tmp_path / "second.txt", "two.example.com=direct\n")
    args = build_parser().parse_args(["--rules-file", first, "--rules-file", second])
    settings = make_settings(args)
    hosts = [rule.host_glob for rule in settings.segmentation_rules]
    assert hosts == ["one.example.com", "two.example.com"]


def test_rules_file_then_inline_rules_order(tmp_path) -> None:
    rules_path = _write_rules_file(tmp_path / "rules.txt", "file.example.com=direct\n")
    args = build_parser().parse_args(
        [
            "--rules-file",
            rules_path,
            "--segment-rule",
            "inline.example.com=direct",
        ]
    )
    settings = make_settings(args)
    hosts = [rule.host_glob for rule in settings.segmentation_rules]
    assert hosts == ["file.example.com", "inline.example.com"]


def test_rules_file_invalid_line_reports_location(tmp_path) -> None:
    rules_path = _write_rules_file(
        tmp_path / "bad.txt",
        """
        # comment
        *.example.com=segment_upstream,strategy=bad
        """,
    )
    args = build_parser().parse_args(["--rules-file", rules_path])
    with pytest.raises(ValueError) as exc_info:
        make_settings(args)
    message = str(exc_info.value)
    assert f"{rules_path}:3" in message
    assert "unknown strategy" in message
