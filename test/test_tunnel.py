import pytest

from segmentedproxy.tunnel import parse_connect_target


def test_parse_connect_target_ok():
    host, port = parse_connect_target("example.com:443")
    assert host == "example.com"
    assert port == 443


def test_parse_connect_target_ipv4_ok():
    host, port = parse_connect_target("1.2.3.4:8443")
    assert host == "1.2.3.4"
    assert port == 8443


def test_parse_connect_target_missing_port():
    with pytest.raises(ValueError):
        parse_connect_target("example.com")


def test_parse_connect_target_bad_port():
    with pytest.raises(ValueError):
        parse_connect_target("example.com:abc")
