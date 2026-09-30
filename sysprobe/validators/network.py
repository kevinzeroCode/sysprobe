from collections.abc import Callable, Sequence
from dataclasses import dataclass
import ipaddress
import re

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]

_DNS_LABEL = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
)


def _validate_ping_host(host: object) -> str | None:
    if host is None:
        return None
    if not isinstance(host, str) or not host:
        raise ValueError("host must be a valid IPv4 address or DNS hostname")

    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        dns_name = host[:-1] if host.endswith(".") else host
        labels = dns_name.split(".")
        if (
            not dns_name
            or len(dns_name) > 253
            or any(_DNS_LABEL.fullmatch(label) is None for label in labels)
        ):
            raise ValueError(
                "host must be a valid IPv4 address or DNS hostname"
            ) from None

    return host


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

        if interface_name != "lo" and interface_name not in interfaces:
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


def _command_failure(
    result: CommandResult,
    *,
    description: str,
) -> str | None:
    if result.timed_out:
        return f"{description} timed out"
    if result.exit_code != 0:
        return f"{description} failed with exit code {result.exit_code}"
    return None


def validate_network(
    *,
    host: str | None = None,
    command_executor: CommandExecutor = run_command,
) -> NetworkValidationResult:
    """Check local IPv4 layers and an optional ping host."""

    ping_host = _validate_ping_host(host)
    interface_result = command_executor(
        ["ip", "-o", "-4", "addr", "show", "scope", "global", "up"]
    )
    route_result = command_executor(
        ["ip", "-4", "route", "show", "default"]
    )
    ping_result = (
        command_executor(
            ["ping", "-4", "-c", "1", "-W", "2", ping_host]
        )
        if ping_host is not None
        else None
    )

    failures: list[str] = []
    data_unavailable = False
    interfaces: tuple[str, ...] | None = None
    routes: tuple[str, ...] | None = None
    host_reachable: bool | None = None

    interface_failure = _command_failure(
        interface_result,
        description="interface command",
    )
    if interface_failure is not None:
        failures.append(interface_failure)
        data_unavailable = True
    else:
        try:
            interfaces = parse_active_ipv4_interfaces(interface_result.stdout)
        except ValueError:
            failures.append("malformed interface output")
            data_unavailable = True
        else:
            if not interfaces:
                failures.append("no active global IPv4 interface")

    route_failure = _command_failure(
        route_result,
        description="route command",
    )
    if route_failure is not None:
        failures.append(route_failure)
        data_unavailable = True
    else:
        try:
            routes = parse_default_route_interfaces(route_result.stdout)
        except ValueError:
            failures.append("malformed default-route output")
            data_unavailable = True
        else:
            if not routes:
                failures.append("no default IPv4 route")

    if ping_result is not None:
        if ping_result.timed_out:
            failures.append("ping timed out")
            data_unavailable = True
        elif ping_result.exit_code == 0:
            host_reachable = True
        elif ping_result.exit_code == 1:
            host_reachable = False
            failures.append(f"host {ping_host} is unreachable")
        else:
            failures.append(
                f"ping failed with exit code {ping_result.exit_code}"
            )
            data_unavailable = True

    metrics: NetworkMetrics | None = None
    if not data_unavailable:
        assert interfaces is not None
        assert routes is not None
        metrics = NetworkMetrics(
            active_ipv4_interfaces=interfaces,
            default_route_interfaces=routes,
            ping_host=ping_host,
            host_reachable=host_reachable,
        )

    passed = not failures
    if passed and ping_host is None:
        reason = "Network has active IPv4 interface and default IPv4 route"
    elif passed:
        reason = (
            "Network has active IPv4 interface, default IPv4 route, "
            f"and reachable host {ping_host}"
        )
    else:
        reason = "Network check failed: " + "; ".join(failures)

    return NetworkValidationResult(
        passed=passed,
        reason=reason,
        metrics=metrics,
        interface_command_result=interface_result,
        route_command_result=route_result,
        ping_command_result=ping_result,
    )
