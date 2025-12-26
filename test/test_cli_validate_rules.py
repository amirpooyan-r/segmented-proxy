import pytest

from segmentedproxy.main import build_parser, format_rule, make_settings, validate_args


def test_validate_rules_flag_parses() -> None:
    args = build_parser().parse_args(["--validate-rules"])
    assert args.validate_rules is True


def test_make_settings_parses_rules() -> None:
    args = build_parser().parse_args(
        [
            "--segment-rule",
            "*.example.com=segment_upstream,action=block,reason=test",
        ]
    )
    settings = make_settings(args)
    assert settings.segmentation_rules


def test_format_rule_includes_host() -> None:
    args = build_parser().parse_args(
        [
            "--segment-rule",
            "*.example.com=segment_upstream,action=block,reason=test",
        ]
    )
    settings = make_settings(args)
    rule = settings.segmentation_rules[0]
    formatted = format_rule(rule)
    assert "host=*.example.com" in formatted


def test_dns_port_requires_dns_server(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["--dns-port", "5353"])
    with pytest.raises(SystemExit):
        validate_args(args, parser)
    err = capsys.readouterr().err
    assert "dns-port requires --dns-server" in err


def test_dns_transport_requires_dns_server(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["--dns-transport", "tcp"])
    with pytest.raises(SystemExit):
        validate_args(args, parser)
    err = capsys.readouterr().err
    assert "dns-transport requires --dns-server" in err


def test_dns_cache_size_negative(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["--dns-cache-size", "-1"])
    with pytest.raises(SystemExit):
        validate_args(args, parser)
    err = capsys.readouterr().err
    assert "dns-cache-size must be" in err


def test_dns_port_out_of_range(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["--dns-server", "1.1.1.1", "--dns-port", "70000"])
    with pytest.raises(SystemExit):
        validate_args(args, parser)
    err = capsys.readouterr().err
    assert "dns-port must be between" in err
