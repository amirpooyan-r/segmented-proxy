from segmentedproxy.main import build_parser, format_rule, make_settings


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
