# Day 5 Network Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Linux IPv4 network validator that checks an active non-loopback interface, a default route, and an optional reachable ping host while preserving command evidence.

**Architecture:** Keep Day 5 behavior in `sysprobe/validators/network.py`. Two mandatory `ip` commands and one optional `ping` command are executed through the existing argument-vector runner; focused parsers turn successful command output into stable tuples, and `validate_network` combines the layers into one result with deterministic failure aggregation. Keep the result network-specific and defer IPv6, listening-socket inspection, retries, and a shared validator hierarchy.

**Tech Stack:** Python 3.10+, standard-library `dataclasses`, `ipaddress`, `re`, typing, pytest 9, deterministic SVG

---

## File Structure

- Create `sysprobe/validators/network.py`: host validation, interface and route parsers, metrics, result model, command classification, and layered policy.
- Create `tests/test_network.py`: parser, host-safety, decision, evidence, failure, and aggregation tests with injected command results.
- Modify `README.md`: Day 5 commands, optional-host behavior, usage, Linux scope, and focused test command.
- Create `docs/day5-network-validator-summary.svg`: colored beginner-oriented diagram of the three network layers.

### Task 1: Parse Active Global IPv4 Interfaces

**Files:**
- Create: `tests/test_network.py`
- Create: `sysprobe/validators/network.py`

- [ ] **Step 1: Write the failing interface parser tests**

Create `tests/test_network.py`:

```python
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
```

- [ ] **Step 2: Run the interface parser tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -v
```

Purpose: run only the new Day 5 test module so the missing feature is obvious.

Expected: pytest collects 8 cases and each fails inside the test with
`ModuleNotFoundError` because `sysprobe.validators.network` does not exist.

- [ ] **Step 3: Add the minimal interface parser**

Create `sysprobe/validators/network.py`:

```python
import ipaddress


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
```

- [ ] **Step 4: Re-run the interface parser tests and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -v
```

Purpose: prove the parser accepts `ip -o` records, preserves order, removes
duplicate interface names, accepts an empty result, and rejects corrupt data.

Expected: 8 tests pass.

- [ ] **Step 5: Commit the interface parser slice**

```powershell
git add -- sysprobe/validators/network.py tests/test_network.py
git commit -m "feat: parse active IPv4 interfaces"
```

### Task 2: Parse Default IPv4 Routes

**Files:**
- Modify: `tests/test_network.py`
- Modify: `sysprobe/validators/network.py`

- [ ] **Step 1: Add failing default-route parser tests**

Append to `tests/test_network.py`:

```python
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
```

- [ ] **Step 2: Run only the route parser tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -k default_route -v
```

Purpose: `-k default_route` selects only tests whose names contain that text.

Expected: pytest collects 7 selected cases and they fail because
`parse_default_route_interfaces` does not exist.

- [ ] **Step 3: Add the minimal default-route parser**

Append to `sysprobe/validators/network.py`:

```python
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
```

- [ ] **Step 4: Run both parser groups and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -v
```

Purpose: verify both independent parsers before adding command orchestration.

Expected: all 15 Day 5 parser cases pass.

- [ ] **Step 5: Commit the route parser slice**

```powershell
git add -- sysprobe/validators/network.py tests/test_network.py
git commit -m "feat: parse default IPv4 routes"
```

### Task 3: Apply the Mandatory Local Network Policy

**Files:**
- Modify: `tests/test_network.py`
- Modify: `sysprobe/validators/network.py`

- [ ] **Step 1: Add test helpers and failing local-layer tests**

Replace the import block at the top of `tests/test_network.py` with:

```python
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
```

Remove the function-local parser imports from Tasks 1 and 2, then add these
helpers below the imports:

```python
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
```

Append:

```python
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
```

- [ ] **Step 2: Run the local policy tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py::test_validate_network_applies_mandatory_local_policy -v
```

Purpose: isolate the new data model, two-command orchestration, and local
PASS/FAIL policy.

Expected: 4 cases fail during collection because `NetworkMetrics`,
`NetworkValidationResult`, and `validate_network` do not exist.

- [ ] **Step 3: Add result models and the local-layer policy**

Replace the production import block with:

```python
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import ipaddress

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]
```

Keep both parsers, then add:

```python
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
```

- [ ] **Step 4: Run Day 5 and regression tests and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -v
python -m pytest -v
```

Purpose: prove the mandatory interface/route policy and confirm Days 1 through
4 still work.

Expected: 19 Day 5 cases pass and 77 total tests pass.

- [ ] **Step 5: Commit the mandatory policy slice**

```powershell
git add -- sysprobe/validators/network.py tests/test_network.py
git commit -m "feat: validate local IPv4 network layers"
```

### Task 4: Validate and Check an Optional Ping Host

**Files:**
- Modify: `tests/test_network.py`
- Modify: `sysprobe/validators/network.py`

- [ ] **Step 1: Add failing accepted-host and ping tests**

Append to `tests/test_network.py`:

```python
@pytest.mark.parametrize(
    "host",
    ["192.0.2.25", "example.com", "localhost", "api.example.com."],
)
def test_validate_network_pings_valid_host(host: str) -> None:
    ping_command = ("ping", "-4", "-c", "1", "-W", "2", host)
    interface_result = make_command_result(
        INTERFACE_COMMAND,
        stdout=ACTIVE_INTERFACE_OUTPUT,
    )
    route_result = make_command_result(
        ROUTE_COMMAND,
        stdout=DEFAULT_ROUTE_OUTPUT,
    )
    ping_result = make_command_result(ping_command, stdout="1 packets received")
    executor, calls = make_executor(
        {
            INTERFACE_COMMAND: interface_result,
            ROUTE_COMMAND: route_result,
            ping_command: ping_result,
        }
    )

    result = validate_network(host=host, command_executor=executor)

    assert result == NetworkValidationResult(
        passed=True,
        reason=(
            "Network has active IPv4 interface, default IPv4 route, "
            f"and reachable host {host}"
        ),
        metrics=NetworkMetrics(
            active_ipv4_interfaces=("eth0",),
            default_route_interfaces=("eth0",),
            ping_host=host,
            host_reachable=True,
        ),
        interface_command_result=interface_result,
        route_command_result=route_result,
        ping_command_result=ping_result,
    )
    assert calls == [INTERFACE_COMMAND, ROUTE_COMMAND, ping_command]
```

- [ ] **Step 2: Add failing unsafe-host tests**

Append:

```python
@pytest.mark.parametrize(
    "host",
    [
        "",
        " ",
        " example.com",
        "example.com ",
        "bad host",
        "example.com\n",
        "-c",
        "::1",
        "bad_name",
        ".example.com",
        "example..com",
        "bad-.example",
        f"{'a' * 64}.example",
        "a" * 254,
        123,
        True,
    ],
)
def test_validate_network_rejects_invalid_host_before_execution(
    host: object,
) -> None:
    def unexpected_executor(_command: Sequence[str]) -> CommandResult:
        raise AssertionError("invalid host must fail before command execution")

    with pytest.raises(
        ValueError,
        match="host must be a valid IPv4 address or DNS hostname",
    ):
        validate_network(
            host=host,  # type: ignore[arg-type]
            command_executor=unexpected_executor,
        )
```

- [ ] **Step 3: Run optional-host tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -k "valid_host or invalid_host" -v
```

Purpose: test host syntax and the exact ping argument vector without contacting
the network.

Expected: the selected cases fail because `validate_network` does not accept
`host` yet.

- [ ] **Step 4: Add host validation and optional ping orchestration**

Add `import re` after `import ipaddress`, then add this before the dataclasses:

```python
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
```

Replace `validate_network` with:

```python
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

    interfaces = parse_active_ipv4_interfaces(interface_result.stdout)
    routes = parse_default_route_interfaces(route_result.stdout)
    host_reachable = ping_result.exit_code == 0 if ping_result else None
    failures: list[str] = []

    if not interfaces:
        failures.append("no active global IPv4 interface")
    if not routes:
        failures.append("no default IPv4 route")
    if host_reachable is False:
        failures.append(f"host {ping_host} is unreachable")

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
        metrics=NetworkMetrics(
            active_ipv4_interfaces=interfaces,
            default_route_interfaces=routes,
            ping_host=ping_host,
            host_reachable=host_reachable,
        ),
        interface_command_result=interface_result,
        route_command_result=route_result,
        ping_command_result=ping_result,
    )
```

- [ ] **Step 5: Run host, Day 5, and complete tests and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -k "valid_host or invalid_host" -v
python -m pytest tests/test_network.py -v
python -m pytest -v
```

Purpose: verify accepted hosts become one safe ping argument, invalid hosts run
no commands, and omitting `host` still skips ping.

Expected: 20 selected host cases, 39 Day 5 cases, and 97 total tests pass.

- [ ] **Step 6: Commit optional ping behavior**

```powershell
git add -- sysprobe/validators/network.py tests/test_network.py
git commit -m "feat: check optional network host"
```

### Task 5: Classify and Aggregate Network Failures

**Files:**
- Modify: `tests/test_network.py`
- Modify: `sysprobe/validators/network.py`

- [ ] **Step 1: Add failing operational and parsing failure tests**

Append to `tests/test_network.py`:

```python
@pytest.mark.parametrize(
    ("layer", "broken_result", "host", "expected_cause"),
    [
        (
            "interface",
            make_command_result(
                INTERFACE_COMMAND,
                exit_code=None,
                timed_out=True,
            ),
            None,
            "interface command timed out",
        ),
        (
            "interface",
            make_command_result(INTERFACE_COMMAND, exit_code=2),
            None,
            "interface command failed with exit code 2",
        ),
        (
            "interface",
            make_command_result(INTERFACE_COMMAND, stdout="broken\n"),
            None,
            "malformed interface output",
        ),
        (
            "route",
            make_command_result(
                ROUTE_COMMAND,
                exit_code=None,
                timed_out=True,
            ),
            None,
            "route command timed out",
        ),
        (
            "route",
            make_command_result(ROUTE_COMMAND, exit_code=2),
            None,
            "route command failed with exit code 2",
        ),
        (
            "route",
            make_command_result(ROUTE_COMMAND, stdout="broken\n"),
            None,
            "malformed default-route output",
        ),
        (
            "ping",
            make_command_result(
                ("ping", "-4", "-c", "1", "-W", "2", "example.com"),
                exit_code=None,
                timed_out=True,
            ),
            "example.com",
            "ping timed out",
        ),
        (
            "ping",
            make_command_result(
                ("ping", "-4", "-c", "1", "-W", "2", "example.com"),
                exit_code=2,
            ),
            "example.com",
            "ping failed with exit code 2",
        ),
    ],
)
def test_validate_network_reports_operational_or_parse_failure(
    layer: str,
    broken_result: CommandResult,
    host: str | None,
    expected_cause: str,
) -> None:
    ping_command = (
        ("ping", "-4", "-c", "1", "-W", "2", host)
        if host is not None
        else None
    )
    interface_result = make_command_result(
        INTERFACE_COMMAND,
        stdout=ACTIVE_INTERFACE_OUTPUT,
    )
    route_result = make_command_result(
        ROUTE_COMMAND,
        stdout=DEFAULT_ROUTE_OUTPUT,
    )
    results = {
        INTERFACE_COMMAND: interface_result,
        ROUTE_COMMAND: route_result,
    }

    if layer == "interface":
        results[INTERFACE_COMMAND] = broken_result
    elif layer == "route":
        results[ROUTE_COMMAND] = broken_result
    else:
        assert ping_command is not None
        results[ping_command] = broken_result

    executor, calls = make_executor(results)

    result = validate_network(host=host, command_executor=executor)

    assert result.passed is False
    assert result.reason == f"Network check failed: {expected_cause}"
    assert result.metrics is None
    assert result.interface_command_result is results[INTERFACE_COMMAND]
    assert result.route_command_result is results[ROUTE_COMMAND]
    assert result.ping_command_result is (
        results[ping_command] if ping_command is not None else None
    )
    expected_calls = [INTERFACE_COMMAND, ROUTE_COMMAND]
    if ping_command is not None:
        expected_calls.append(ping_command)
    assert calls == expected_calls
```

- [ ] **Step 2: Add failing multi-layer aggregation tests**

Append:

```python
def test_validate_network_retains_metrics_for_health_failures() -> None:
    host = "example.com"
    ping_command = ("ping", "-4", "-c", "1", "-W", "2", host)
    interface_result = make_command_result(INTERFACE_COMMAND)
    route_result = make_command_result(ROUTE_COMMAND)
    ping_result = make_command_result(ping_command, exit_code=1)
    executor, calls = make_executor(
        {
            INTERFACE_COMMAND: interface_result,
            ROUTE_COMMAND: route_result,
            ping_command: ping_result,
        }
    )

    result = validate_network(host=host, command_executor=executor)

    assert result.reason == (
        "Network check failed: no active global IPv4 interface; "
        "no default IPv4 route; host example.com is unreachable"
    )
    assert result.metrics == NetworkMetrics(
        active_ipv4_interfaces=(),
        default_route_interfaces=(),
        ping_host=host,
        host_reachable=False,
    )
    assert calls == [INTERFACE_COMMAND, ROUTE_COMMAND, ping_command]


def test_validate_network_reports_mixed_failures_in_stable_order() -> None:
    host = "example.com"
    ping_command = ("ping", "-4", "-c", "1", "-W", "2", host)
    interface_result = make_command_result(INTERFACE_COMMAND, stdout="broken\n")
    route_result = make_command_result(ROUTE_COMMAND)
    ping_result = make_command_result(ping_command, exit_code=1)
    executor, calls = make_executor(
        {
            INTERFACE_COMMAND: interface_result,
            ROUTE_COMMAND: route_result,
            ping_command: ping_result,
        }
    )

    result = validate_network(host=host, command_executor=executor)

    assert result.reason == (
        "Network check failed: malformed interface output; "
        "no default IPv4 route; host example.com is unreachable"
    )
    assert result.metrics is None
    assert result.interface_command_result is interface_result
    assert result.route_command_result is route_result
    assert result.ping_command_result is ping_result
    assert calls == [INTERFACE_COMMAND, ROUTE_COMMAND, ping_command]
```

- [ ] **Step 3: Run the failure tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -k "failure or failures" -v
```

Purpose: prove command errors and parser errors become structured results and
that later configured layers still execute.

Expected: the selected cases fail because the current validator parses failed
commands, treats every nonzero ping exit alike, and never returns `metrics=None`.

- [ ] **Step 4: Add command classification and replace the validator**

Add above `validate_network`:

```python
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
```

Replace `validate_network` with:

```python
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
```

- [ ] **Step 5: Run focused, Day 5, and complete suites and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -k "failure or failures" -v
python -m pytest tests/test_network.py -v
python -m pytest -v
```

Purpose: verify individual and simultaneous failures, then protect all earlier
Days from regressions.

Expected: 10 selected failure cases, 49 Day 5 cases, and 107 total tests pass.

- [ ] **Step 6: Commit failure aggregation**

```powershell
git add -- sysprobe/validators/network.py tests/test_network.py
git commit -m "feat: report network validation failures"
```

### Task 6: Document Day 5 and Add the Colored Learning Summary

**Files:**
- Modify: `README.md`
- Create: `docs/day5-network-validator-summary.svg`

- [ ] **Step 1: Update the project introduction**

Extend the introduction so its final sentence reads:

```markdown
Day 4 adds a CPU validator that normalizes Linux load average by available CPU
count. Day 5 adds a layered IPv4 network validator with an optional reachability
check.
```

- [ ] **Step 2: Add the Day 5 README section before Requirements**

Insert:

````markdown
## Day 5 behavior

`validate_network` checks three IPv4 layers on Linux:

1. `ip -o -4 addr show scope global up` finds active, non-loopback interfaces
   with a global IPv4 address.
2. `ip -4 route show default` finds the route used for destinations outside the
   local networks.
3. `ping -4 -c 1 -W 2 <host>` runs only when the caller supplies `host`.

```python
from sysprobe.validators.network import validate_network

local_result = validate_network()
remote_result = validate_network(host="example.com")

print("PASS" if local_result.passed else "FAIL")
print(local_result.reason)
print("PASS" if remote_result.passed else "FAIL")
print(remote_result.reason)
```

Ping is optional because some healthy networks block ICMP replies. Without a
host, PASS requires an active global IPv4 interface and a default IPv4 route.
With a host, PASS additionally requires one successful ping reply.

The result retains the interface, route, and optional ping `CommandResult`
objects. A ping exit code of `1` means the host did not reply; timeouts and
other nonzero exit codes are reported as execution failures. Host input is
validated before commands run, and argument vectors avoid shell injection.

The real commands require Linux. Deterministic unit tests run on Windows using
representative command output and never contact the network.

Run only the Day 5 tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -v
```

### Day 5 visual summary

![Day 5 Network Validator flow](docs/day5-network-validator-summary.svg)
````

- [ ] **Step 3: Create the deterministic colored SVG**

Create `docs/day5-network-validator-summary.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="860" viewBox="0 0 1400 860" role="img" aria-labelledby="title desc">
  <title id="title">SysProbe Day 5 Network Validator</title>
  <desc id="desc">Three network layers check an active IPv4 interface, a default route, and an optional ping host before producing PASS or FAIL.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ecfeff"/>
      <stop offset="1" stop-color="#f5f3ff"/>
    </linearGradient>
    <filter id="shadow"><feDropShadow dx="0" dy="7" stdDeviation="7" flood-opacity="0.14"/></filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#475569"/></marker>
    <style>
      text{font-family:"Segoe UI","Microsoft JhengHei",sans-serif;fill:#0f172a}.title{font-size:36px;font-weight:700}.sub{font-size:18px;fill:#475569}.head{font-size:22px;font-weight:700}.body{font-size:17px}.small{font-size:15px;fill:#475569}.code{font:700 15px Consolas,monospace}.card{stroke-width:2;filter:url(#shadow)}.arrow{stroke:#475569;stroke-width:4;fill:none;marker-end:url(#arrow)}
    </style>
  </defs>
  <rect width="1400" height="860" fill="url(#bg)"/>
  <text x="60" y="60" class="title">SysProbe Day 5：分層檢查 IPv4 網路</text>
  <text x="60" y="94" class="sub">先確認自己的網路設定，再選擇是否測試遠端主機</text>

  <rect class="card" x="55" y="155" width="350" height="220" rx="24" fill="#dbeafe" stroke="#60a5fa"/>
  <text x="85" y="202" class="head">1　網路介面（必要）</text>
  <text x="85" y="242" class="code">ip -o -4 addr show ...</text>
  <text x="85" y="282" class="body">至少一個非 loopback、UP、</text>
  <text x="85" y="312" class="body">具有 global IPv4 的介面</text>
  <rect x="85" y="330" width="185" height="32" rx="16" fill="#bfdbfe"/>
  <text x="105" y="352" class="small">例：eth0 192.0.2.10</text>

  <path class="arrow" d="M405 265 L500 265"/>
  <rect class="card" x="515" y="155" width="350" height="220" rx="24" fill="#ede9fe" stroke="#a78bfa"/>
  <text x="545" y="202" class="head">2　預設路由（必要）</text>
  <text x="545" y="242" class="code">ip -4 route show default</text>
  <text x="545" y="282" class="body">系統知道外部封包應該</text>
  <text x="545" y="312" class="body">交給哪個閘道與介面</text>
  <rect x="545" y="330" width="250" height="32" rx="16" fill="#ddd6fe"/>
  <text x="565" y="352" class="small">例：via 192.0.2.1 dev eth0</text>

  <path class="arrow" d="M865 265 L960 265"/>
  <rect class="card" x="975" y="155" width="370" height="220" rx="24" fill="#fef3c7" stroke="#f59e0b" stroke-dasharray="10 7"/>
  <text x="1005" y="202" class="head">3　Ping 主機（選擇性）</text>
  <text x="1005" y="242" class="code">ping -4 -c 1 -W 2 host</text>
  <text x="1005" y="282" class="body">只有提供 host 才執行</text>
  <text x="1005" y="312" class="body">避免 ICMP 被擋造成誤判</text>
  <rect x="1005" y="330" width="205" height="32" rx="16" fill="#fde68a"/>
  <text x="1025" y="352" class="small">None → 完全不執行</text>

  <path class="arrow" d="M690 375 L690 470"/>
  <rect class="card" x="350" y="485" width="680" height="135" rx="24" fill="#ffffff" stroke="#94a3b8"/>
  <text x="390" y="530" class="head">彙整全部已設定的檢查證據</text>
  <text x="390" y="568" class="body">固定順序：介面 → 路由 → 選擇性 Ping</text>
  <text x="390" y="598" class="small">即使前一層失敗，仍完成其他已設定的唯讀檢查</text>

  <path class="arrow" d="M570 620 C570 670 430 680 430 720"/>
  <path class="arrow" d="M810 620 C810 670 970 680 970 720"/>
  <rect class="card" x="205" y="720" width="450" height="95" rx="24" fill="#dcfce7" stroke="#4ade80"/>
  <text x="245" y="765" class="head" fill="#166534">PASS</text>
  <text x="245" y="795" class="body">必要層存在，且指定的 host 可達</text>
  <rect class="card" x="745" y="720" width="450" height="95" rx="24" fill="#fee2e2" stroke="#f87171"/>
  <text x="785" y="765" class="head" fill="#991b1b">FAIL + reason</text>
  <text x="785" y="795" class="body">缺少資源、無回應、逾時或輸出損壞</text>
</svg>
```

- [ ] **Step 4: Validate documentation, SVG, and tests**

```powershell
$svg = [xml](Get-Content -Encoding UTF8 -Raw 'docs\day5-network-validator-summary.svg')
if ($svg.DocumentElement.Name -ne 'svg') { throw 'SVG root is missing' }
git diff --check
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
```

Purpose: parse the image as XML, detect whitespace damage, and prove the
documentation changes did not affect behavior.

Expected: XML parsing and diff check succeed; 107 tests pass.

- [ ] **Step 5: Commit the Day 5 documentation and image**

```powershell
git add -- README.md docs/day5-network-validator-summary.svg
git commit -m "docs: explain Day 5 network validation"
```

### Task 7: Final Day 5 Verification and Review

**Files:**
- Verify only; no planned modifications.

- [ ] **Step 1: Run focused tests, the full suite, and compilation**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_network.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m compileall -q sysprobe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git diff --check
```

Purpose: provide fresh proof that Day 5 works, Days 1 through 4 did not regress,
all Python modules compile, and no whitespace error remains.

Expected: 49 Day 5 cases and 107 total tests pass; every command exits with
code 0.

- [ ] **Step 2: Verify branch cleanliness and exact scope**

```powershell
git status --short --branch
git log --oneline main..HEAD
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Purpose: confirm all Day 5 work is committed and inspect exactly what will be
reviewed and merged.

Expected changed paths:

```text
README.md
docs/day5-network-validator-summary.svg
docs/superpowers/plans/2026-09-28-network-validator.md
sysprobe/validators/network.py
tests/test_network.py
```

- [ ] **Step 3: Review against the approved specification**

Check every acceptance criterion in
`docs/superpowers/specs/2026-09-28-network-validator-design.md` against the
implementation, tests, README, and SVG. Pay special attention to command order,
the distinction between an empty successful result and malformed output,
`metrics=None` only for unavailable data, host validation before execution,
and the absence of IPv6 or `ss` scope creep.

- [ ] **Step 4: Prepare the beginner Linux/WSL smoke test**

After automated verification, guide the user through these read-only commands
on Linux or WSL and explain each option before execution:

```bash
ip -o -4 addr show scope global up
ip -4 route show default
python -c "from sysprobe.validators.network import validate_network; result = validate_network(); print('PASS' if result.passed else 'FAIL'); print(result.reason); print(result.metrics)"
```

An optional remote check can then use a host the user chooses:

```bash
python -c "from sysprobe.validators.network import validate_network; result = validate_network(host='example.com'); print('PASS' if result.passed else 'FAIL'); print(result.reason)"
```

Do not interpret a blocked ping alone as proof that the local interface or
route is broken; explain the three layers separately.

- [ ] **Step 5: Integrate only after review and fresh evidence**

Use the `superpowers:requesting-code-review` workflow, resolve verified review
findings, then use `superpowers:finishing-a-development-branch` to merge and
push only after the user approves integration.
