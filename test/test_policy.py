from segmentedproxy.policy import check_host_policy


def test_deny_domain_exact():
    d = check_host_policy(
        "example.com",
        allow_domains=tuple(),
        deny_domains=("example.com",),
        deny_private=False,
    )
    assert not d.allowed


def test_deny_domain_suffix():
    d = check_host_policy(
        "a.example.com",
        allow_domains=tuple(),
        deny_domains=(".example.com",),
        deny_private=False,
    )
    assert not d.allowed


def test_allow_list_blocks_other():
    d = check_host_policy(
        "other.com",
        allow_domains=("example.com",),
        deny_domains=tuple(),
        deny_private=False,
    )
    assert not d.allowed


def test_allow_list_allows_suffix():
    d = check_host_policy(
        "sub.example.com",
        allow_domains=(".example.com",),
        deny_domains=tuple(),
        deny_private=False,
    )
    assert d.allowed


def test_private_ip_blocked_by_default():
    d = check_host_policy(
        "127.0.0.1",
        allow_domains=tuple(),
        deny_domains=tuple(),
        deny_private=True,
    )
    assert not d.allowed
