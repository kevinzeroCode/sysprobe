from collections.abc import Callable, Sequence
from dataclasses import dataclass
import ipaddress

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]


def parse_active_ipv4_interfaces(output: str) -> tuple[str, ...]:
    """Parse interface names from one-line global IPv4 address records."""

    interfaces: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split()
        try:
            index_text, interface_name, family, address = fields[:4]
            index = int(index_text.removesuffix(":"))
            if (
                not index_text.endswith(":")
                or index <= 0
                or family != "inet"
                or "/" not in address
            ):
                raise ValueError
            ipaddress.IPv4Interface(address)
        except (ValueError, IndexError) as error:
            raise ValueError("malformed IPv4 interface output") from error

        if interface_name not in interfaces:
            interfaces.append(interface_name)

    return tuple(interfaces)


def parse_default_route_interfaces(output: str) -> tuple[str, ...]:
    """Parse device names from default IPv4 route records."""

    interfaces: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split()
        try:
            if fields[0] != "default":
                raise ValueError

            for position, field in enumerate(fields):
                if field == "via":
                    ipaddress.IPv4Address(fields[position + 1])

            device_positions = [
                position
                for position, field in enumerate(fields)
                if field == "dev"
            ]
            if not device_positions:
                raise ValueError

            devices = [fields[position + 1] for position in device_positions]
        except (ValueError, IndexError) as error:
            raise ValueError("malformed default IPv4 route output") from error

        for interface_name in devices:
            if interface_name not in interfaces:
                interfaces.append(interface_name)

    return tuple(interfaces)


@dataclass(frozen=True, slots=True)
class NetworkMetrics:
    """Successfully observed facts from the configured network layers."""

    active_ipv4_interfaces: tuple[str, ...]
    default_route_interfaces: tuple[str, ...]
    ping_host: str | None
    host_reachable: bool | None


@dataclass(frozen=True, slots=True)
class NetworkValidationResult:
    """The network decision plus every command record behind it."""

    passed: bool
    reason: str
    metrics: NetworkMetrics | None
    interface_command_result: CommandResult
    route_command_result: CommandResult
    ping_command_result: CommandResult | None


def validate_network(
    *,
    command_executor: CommandExecutor = run_command,
) -> NetworkValidationResult:
    """Check mandatory local IPv4 interface and route layers."""

    interface_result = command_executor(
        ["ip", "-o", "-4", "addr", "show", "scope", "global", "up"]
    )
    route_result = command_executor(
        ["ip", "-4", "route", "show", "default"]
    )
    interfaces = parse_active_ipv4_interfaces(interface_result.stdout)
    routes = parse_default_route_interfaces(route_result.stdout)
    failures: list[str] = []

    if not interfaces:
        failures.append("no active global IPv4 interface")
    if not routes:
        failures.append("no default IPv4 route")

    passed = not failures
    reason = (
        "Network has active IPv4 interface and default IPv4 route"
        if passed
        else "Network check failed: " + "; ".join(failures)
    )

    return NetworkValidationResult(
        passed=passed,
        reason=reason,
        metrics=NetworkMetrics(
            active_ipv4_interfaces=interfaces,
            default_route_interfaces=routes,
            ping_host=None,
            host_reachable=None,
        ),
        interface_command_result=interface_result,
        route_command_result=route_result,
        ping_command_result=None,
    )
