# Day 5 Network Validator Design

## Goal

Add a Linux IPv4 network validator that answers three progressively broader
questions:

1. Does the machine have at least one active, non-loopback IPv4 interface?
2. Does the machine have a default IPv4 route?
3. If the caller supplies a host, can that host be reached with one ping?

The validator reports one overall PASS or FAIL while retaining the raw command
evidence needed to diagnose every configured layer.

## Scope

Day 5 supports IPv4 only. It checks local interface configuration, the default
route, and an optional ping target. It does not modify network settings.

The following are explicitly outside this feature:

- IPv6;
- `ss -tulpn` and listening-service inspection;
- dedicated DNS diagnosis;
- retries or continuous monitoring;
- network configuration changes; and
- a common validator base class, which remains deferred until integration work.

`ss -tulpn` is not a health predicate because it describes local listening
services, not whether the network stack has an interface or a usable route.

## Chosen Approach

Use independent, layered checks and aggregate their results. This is preferred
over making ping mandatory because ICMP can be blocked even when local network
configuration is healthy. It is also preferred over collecting every network
command because unrelated diagnostic output would make the Day 5 policy harder
to understand and test.

The commands are argument vectors executed through the existing
`run_command` boundary:

```text
ip -o -4 addr show scope global up
ip -4 route show default
ping -4 -c 1 -W 2 <host>       # only when a host is supplied
```

The `ip -o` form produces one record per line, which is more stable for parsing
than the human-oriented multi-line `ip addr` display. The address command's
filters also exclude loopback and interfaces without an active global IPv4
address.

## Public API and Data

The new module is `sysprobe/validators/network.py`. Its entry point is:

```python
validate_network(
    *,
    host: str | None = None,
    command_executor: CommandExecutor = run_command,
) -> NetworkValidationResult
```

`NetworkMetrics` contains:

- `active_ipv4_interfaces: tuple[str, ...]`;
- `default_route_interfaces: tuple[str, ...]`;
- `ping_host: str | None`; and
- `host_reachable: bool | None`.

`host_reachable` is `None` when no ping was requested. Interface and route
names are de-duplicated while preserving command-output order.

`NetworkValidationResult` contains:

- `passed: bool`;
- `reason: str`;
- `metrics: NetworkMetrics | None`;
- `interface_command_result: CommandResult`;
- `route_command_result: CommandResult`; and
- `ping_command_result: CommandResult | None`.

The optional ping result is `None` only when no host was supplied. Raw results
retain command arguments, standard output, standard error, exit code, duration,
and timeout state.

## Host Validation and Command Safety

Configuration is validated before any command executes. `None` skips ping. A
supplied host must be either an IPv4 address accepted by `ipaddress.IPv4Address`
or an ASCII DNS hostname with these rules:

- the full name is at most 253 characters, excluding an optional final dot;
- labels are between 1 and 63 characters;
- labels contain only ASCII letters, digits, and hyphens;
- every label begins and ends with a letter or digit; and
- a single label such as `localhost` is allowed.

Empty strings, surrounding or embedded whitespace, IPv6 addresses, control
characters, underscores, empty DNS labels, and values beginning with `-` are
invalid. Invalid configuration raises `ValueError` before the executor is
called.

Commands remain argument vectors and never pass through a shell. This prevents
shell injection. Rejecting a leading `-` also prevents the host value from
being interpreted as an additional ping option.

## Parsers

`parse_active_ipv4_interfaces` processes nonblank one-line `ip address` records.
Each record must contain an interface index, interface name, the `inet` family,
and a valid IPv4 interface/prefix value. It returns unique interface names in
input order. Empty output is valid and returns an empty tuple.

`parse_default_route_interfaces` processes nonblank default-route records. Each
record must begin with `default`, contain at least one `dev <interface>` pair,
and contain a valid IPv4 address after every `via` token. It returns unique
route interface names in input order. Empty output is valid and returns an
empty tuple.

Malformed nonblank output raises `ValueError`. Empty valid output is kept
distinct from malformed output because it means the check succeeded but the
required network resource was absent.

## Validation Flow

After host validation, the interface and route commands always run. The ping
command also runs when a host was supplied, even if another check has already
failed. This provides all configured evidence in one result.

Results are evaluated in stable layer order:

1. interface command and interface output;
2. route command and route output; and
3. optional ping result.

For interface and route commands, timeout or a nonzero exit code is an
operational failure. Successful empty output is a health failure: no active
global IPv4 interface or no default IPv4 route.

For ping:

- exit code `0` means the host is reachable;
- exit code `1` means the check ran but received no reply, so the host is
  unreachable;
- a timeout is an operational failure; and
- any other exit code is an operational failure reported with its code.

Independent problems are joined into one deterministic reason string. A
health failure with successful parsing retains `NetworkMetrics`. If any command
has an operational failure or any nonblank output is malformed, `metrics` is
`None`; the raw command results still preserve successful and failed evidence.

Overall PASS requires at least one active global IPv4 interface, at least one
default IPv4 route, and, when requested, a reachable host.

## Error Messages

Failure reasons use the prefix `Network check failed:` followed by one or more
specific causes separated with semicolons. Causes remain in interface, route,
then ping order. They distinguish:

- a command timeout;
- a command's unexpected nonzero exit code;
- malformed output;
- a successfully observed but missing interface or route; and
- an optional host that did not reply.

Successful reasons state that the active IPv4 interface and default route were
found and, when applicable, name the reachable host.

## Testing Strategy

`tests/test_network.py` uses injected executors and representative command
output. Unit tests never require Linux, modify networking, or contact a real
host.

Parser tests cover:

- one and multiple interfaces or routes;
- stable de-duplication;
- direct and gateway routes;
- empty output; and
- malformed records and invalid IPv4 values.

Host-validation tests cover accepted IPv4 addresses, accepted DNS names, and
every rejected class defined above. They verify that invalid configuration
runs no commands.

Validator tests cover:

- PASS without ping and confirmation that ping was not executed;
- PASS with a reachable host;
- missing interface, missing route, and unreachable host;
- simultaneous health failures in stable order;
- command timeout and unexpected exit-code failures for every layer;
- malformed interface and route output;
- continued execution of all configured checks after an earlier failure;
- retention of every `CommandResult`; and
- `metrics=None` for operational or parsing failures.

The complete Day 1 through Day 5 suite must remain green.

## Documentation and Visual Summary

README gains a Day 5 usage example, command explanation, optional-host behavior,
Linux runtime note, and a command for running only the Day 5 tests. A colored
SVG illustrates the three layers and makes clear that ping is optional.

## Completion Criteria

Day 5 is complete when:

- the approved module, data objects, parsers, and policy are implemented;
- the Day 5 tests and the complete existing suite pass;
- Python compilation succeeds;
- README and the colored SVG match the implemented behavior; and
- review finds no unintended changes to user-owned files.
