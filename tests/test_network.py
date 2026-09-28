import pytest


def test_parse_active_ipv4_interfaces_reads_and_deduplicates() -> None:
    from sysprobe.validators.network import parse_active_ipv4_interfaces

    output = (
        "2: eth0    inet 192.0.2.10/24 brd 192.0.2.255 "
        "scope global eth0\\       valid_lft forever preferred_lft forever\n"
        "3: wlan0   inet 198.51.100.7/24 brd 198.51.100.255 "
        "scope global wlan0\\       valid_lft forever preferred_lft forever\n"
        "2: eth0    inet 192.0.2.11/24 brd 192.0.2.255 "
        "scope global secondary eth0\\       valid_lft forever "
        "preferred_lft forever\n"
    )

    assert parse_active_ipv4_interfaces(output) == ("eth0", "wlan0")


def test_parse_active_ipv4_interfaces_accepts_empty_output() -> None:
    from sysprobe.validators.network import parse_active_ipv4_interfaces

    assert parse_active_ipv4_interfaces("\n") == ()


@pytest.mark.parametrize(
    "output",
    [
        "not an address record\n",
        "2: eth0 inet6 2001:db8::1/64 scope global\n",
        "x: eth0 inet 192.0.2.10/24 scope global\n",
        "0: eth0 inet 192.0.2.10/24 scope global\n",
        "2: eth0 inet 999.0.0.1/24 scope global\n",
        "2: eth0 inet 192.0.2.10 scope global\n",
    ],
)
def test_parse_active_ipv4_interfaces_rejects_malformed_records(
    output: str,
) -> None:
    from sysprobe.validators.network import parse_active_ipv4_interfaces

    with pytest.raises(ValueError, match="malformed IPv4 interface output"):
        parse_active_ipv4_interfaces(output)


def test_parse_default_route_interfaces_reads_and_deduplicates() -> None:
    from sysprobe.validators.network import parse_default_route_interfaces

    output = (
        "default via 192.0.2.1 dev eth0 proto dhcp metric 100\n"
        "default dev ppp0 scope link metric 200\n"
        "default via 198.51.100.1 dev eth0 proto static metric 300\n"
    )

    assert parse_default_route_interfaces(output) == ("eth0", "ppp0")


def test_parse_default_route_interfaces_accepts_empty_output() -> None:
    from sysprobe.validators.network import parse_default_route_interfaces

    assert parse_default_route_interfaces("\n") == ()


@pytest.mark.parametrize(
    "output",
    [
        "192.0.2.0/24 dev eth0 scope link\n",
        "default via 999.0.0.1 dev eth0\n",
        "default via 192.0.2.1\n",
        "default dev\n",
        "default via dev eth0\n",
    ],
)
def test_parse_default_route_interfaces_rejects_malformed_records(
    output: str,
) -> None:
    from sysprobe.validators.network import parse_default_route_interfaces

    with pytest.raises(ValueError, match="malformed default IPv4 route output"):
        parse_default_route_interfaces(output)
