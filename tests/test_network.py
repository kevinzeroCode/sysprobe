from collections.abc import Callable, Sequence

import pytest

from sysprobe.result import CommandResult
from sysprobe.validators.network import (
    NetworkMetrics,
    NetworkValidationResult,
    parse_active_ipv4_interfaces,
    parse_default_route_interfaces,
    validate_network,
)


INTERFACE_COMMAND = (
    "ip",
    "-o",
    "-4",
    "addr",
    "show",
    "scope",
    "global",
    "up",
)
ROUTE_COMMAND = ("ip", "-4", "route", "show", "default")

ACTIVE_INTERFACE_OUTPUT = (
    "2: eth0 inet 192.0.2.10/24 brd 192.0.2.255 "
    "scope global eth0\\ valid_lft forever preferred_lft forever\n"
)
DEFAULT_ROUTE_OUTPUT = (
    "default via 192.0.2.1 dev eth0 proto dhcp metric 100\n"
)


def make_command_result(
    command: tuple[str, ...],
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )


def make_executor(
    results: dict[tuple[str, ...], CommandResult],
) -> tuple[
    Callable[[Sequence[str]], CommandResult],
    list[tuple[str, ...]],
]:
    calls: list[tuple[str, ...]] = []

    def execute(command: Sequence[str]) -> CommandResult:
        recorded_command = tuple(command)
        calls.append(recorded_command)
        return results[recorded_command]

    return execute, calls


def test_parse_active_ipv4_interfaces_reads_and_deduplicates() -> None:
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
    with pytest.raises(ValueError, match="malformed IPv4 interface output"):
        parse_active_ipv4_interfaces(output)


def test_parse_default_route_interfaces_reads_and_deduplicates() -> None:
    output = (
        "default via 192.0.2.1 dev eth0 proto dhcp metric 100\n"
        "default dev ppp0 scope link metric 200\n"
        "default via 198.51.100.1 dev eth0 proto static metric 300\n"
    )

    assert parse_default_route_interfaces(output) == ("eth0", "ppp0")


def test_parse_default_route_interfaces_accepts_empty_output() -> None:
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
    with pytest.raises(ValueError, match="malformed default IPv4 route output"):
        parse_default_route_interfaces(output)


@pytest.mark.parametrize(
    (
        "interface_output",
        "route_output",
        "expected_passed",
        "expected_reason",
    ),
    [
        (
            ACTIVE_INTERFACE_OUTPUT,
            DEFAULT_ROUTE_OUTPUT,
            True,
            "Network has active IPv4 interface and default IPv4 route",
        ),
        (
            "",
            DEFAULT_ROUTE_OUTPUT,
            False,
            "Network check failed: no active global IPv4 interface",
        ),
        (
            ACTIVE_INTERFACE_OUTPUT,
            "",
            False,
            "Network check failed: no default IPv4 route",
        ),
        (
            "",
            "",
            False,
            (
                "Network check failed: no active global IPv4 interface; "
                "no default IPv4 route"
            ),
        ),
    ],
)
def test_validate_network_applies_mandatory_local_policy(
    interface_output: str,
    route_output: str,
    expected_passed: bool,
    expected_reason: str,
) -> None:
    interface_result = make_command_result(
        INTERFACE_COMMAND,
        stdout=interface_output,
    )
    route_result = make_command_result(ROUTE_COMMAND, stdout=route_output)
    executor, calls = make_executor(
        {
            INTERFACE_COMMAND: interface_result,
            ROUTE_COMMAND: route_result,
        }
    )

    result = validate_network(command_executor=executor)

    assert result == NetworkValidationResult(
        passed=expected_passed,
        reason=expected_reason,
        metrics=NetworkMetrics(
            active_ipv4_interfaces=parse_active_ipv4_interfaces(
                interface_output
            ),
            default_route_interfaces=parse_default_route_interfaces(
                route_output
            ),
            ping_host=None,
            host_reachable=None,
        ),
        interface_command_result=interface_result,
        route_command_result=route_result,
        ping_command_result=None,
    )
    assert calls == [INTERFACE_COMMAND, ROUTE_COMMAND]
