# Day 6 Service Validator Design

## Goal

Add a systemd service validator that determines whether one required Linux
service exists and is active. The validator must distinguish a confirmed
service-health failure from a check that errored or is unsupported, while
retaining the command evidence needed to debug the result.

This feature also introduces the smallest shared result vocabulary needed by
later SysProbe integration work:

- `PASS`: the check completed and the service meets policy;
- `FAIL`: the check completed and the service does not meet policy;
- `ERROR`: the environment should support the check, but this attempt did not
  produce a trustworthy answer; and
- `UNSUPPORTED`: the environment does not provide a usable systemd interface.

## Motivation

A command exit code describes command execution, not service health.
`systemctl show` can exit successfully for both an active unit and a unit with
`LoadState=not-found`. SysProbe therefore parses explicit systemd properties
instead of treating exit code zero as PASS.

The distinction between `FAIL`, `ERROR`, and `UNSUPPORTED` is important for
triage:

- `FAIL` directs the operator to the requested service;
- `ERROR` directs the operator to the failed check or its permissions; and
- `UNSUPPORTED` explains that the host cannot perform this kind of check.

## Scope

Day 6 supports local systemd `.service` units only. It performs a read-only
query and never starts, stops, enables, disables, reloads, or edits a unit.

The following are outside this feature:

- `.socket`, `.timer`, `.target`, and other systemd unit types;
- process-name fallback through `pgrep` or `ps`;
- service restart or remediation;
- remote execution;
- YAML configuration, the all-validator orchestrator, JSON reporting, and the
  CLI, which remain separate integration milestones; and
- immediate migration of the existing disk, memory, CPU, and network result
  objects to the shared status enum.

## Shared Result Foundation

Add a string enum in `sysprobe/result.py`:

```python
class ValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNSUPPORTED = "unsupported"
```

`CommandResult` also needs to represent a process that could not be launched.
Add a string enum with these categories:

```python
class CommandErrorKind(str, Enum):
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    OS_ERROR = "os_error"
```

Append two optional fields to `CommandResult` so existing keyword-based
construction remains compatible:

```python
error_kind: CommandErrorKind | None = None
error_message: str | None = None
```

The command-result invariants are:

- a launched process has `error_kind=None`;
- a launch error has `exit_code=None`, `timed_out=False`, empty stdout, and a
  human-readable `error_message`;
- a timeout keeps using `timed_out=True` and is not a launch error; and
- nonzero process exits remain ordinary command evidence rather than launch
  errors.

Extend `run_command` to convert `FileNotFoundError`, `PermissionError`, and
other `OSError` exceptions into the corresponding structured result. Existing
validators are not otherwise redesigned in Day 6.

## Public API and Data

Create `sysprobe/validators/service.py` with this entry point:

```python
validate_service(
    service_name: str,
    *,
    command_executor: CommandExecutor = run_command,
) -> ServiceValidationResult
```

`ServiceMetrics` is immutable and contains:

```python
load_state: str
active_state: str
sub_state: str
```

`ServiceValidationResult` is immutable and contains:

```python
status: ValidationStatus
reason: str
service_name: str
metrics: ServiceMetrics | None
command_result: CommandResult
```

Parsed systemd data is retained for `PASS` and `FAIL`. `metrics` is `None` for
`ERROR` and `UNSUPPORTED`, because those outcomes did not produce trustworthy
service state.

## Service-Name Validation

The caller may supply a safe service stem or a complete `.service` name:

```text
cron          -> cron.service
cron.service  -> cron.service
ssh@worker    -> ssh@worker.service
```

Validation happens before command execution. A valid value:

- is a string and is not empty;
- has no leading or trailing whitespace;
- contains only ASCII letters, digits, underscore, period, at sign, and
  hyphens after the first character;
- begins with an ASCII letter, digit, or underscore rather than `-`;
- contains no slash, whitespace, control character, or shell metacharacter;
- is either a stem or already ends in `.service`;
- does not end in `.automount`, `.device`, `.mount`, `.path`, `.scope`,
  `.slice`, `.socket`, `.swap`, `.target`, or `.timer`; and
- is at most 255 ASCII bytes after `.service` is appended.

Invalid input raises `ValueError` before the executor is called. SysProbe does
not silently trim or repair invalid input other than appending `.service`.

## Command and Parser

The validator executes one argument vector without a shell:

```text
systemctl show <normalized.service> \
  --property=LoadState \
  --property=ActiveState \
  --property=SubState \
  --no-pager
```

The exact Python argument vector is stable and tested. User input occupies one
already-validated argument and can never become shell syntax.

`parse_service_properties` processes nonblank `Key=Value` records. It requires
exactly one nonempty value for each of these keys:

- `LoadState`;
- `ActiveState`; and
- `SubState`.

Missing keys, duplicate keys, unexpected records, blank values, or malformed
lines raise `ValueError`. The parser returns `ServiceMetrics` without making a
health decision.

## Decision Table

Outcomes are evaluated in this order:

| Evidence | Status | Metrics | Meaning |
|---|---|---|---|
| `systemctl` executable is missing | `UNSUPPORTED` | `None` | systemd tooling is unavailable |
| an approved non-systemd diagnostic appears | `UNSUPPORTED` | `None` | systemd is not usable as the init interface |
| timeout | `ERROR` | `None` | no trustworthy answer arrived in time |
| permission or other launch error | `ERROR` | `None` | the check could not execute |
| other unexpected nonzero exit | `ERROR` | `None` | systemctl failed operationally |
| exit zero but malformed properties | `ERROR` | `None` | output cannot be trusted |
| `LoadState=not-found` | `FAIL` | retained | required service is absent |
| `ActiveState=active` | `PASS` | retained | systemd considers the service active |
| any other valid `ActiveState` | `FAIL` | retained | service is not active |

`ActiveState=active` is sufficient for the generic Day 6 policy.
`SubState=exited` remains PASS because a successful oneshot unit may finish its
process while systemd keeps the unit active. Requiring `SubState=running` would
produce false failures for valid oneshot services.

Only these case-sensitive stderr fragments classify a nonzero exit as
`UNSUPPORTED`:

- `System has not been booted with systemd`;
- `Failed to connect to bus: Host is down`; and
- `Failed to connect to bus: No such file or directory`.

For example, `Failed to connect to bus: Permission denied` remains `ERROR`.
Every other nonzero exit also remains `ERROR` rather than being guessed as
unsupported.

## Validation Flow

```text
normalize service name
    invalid -> raise ValueError without execution

execute systemctl show
    executable missing -> UNSUPPORTED
    systemd unavailable -> UNSUPPORTED
    timeout/permission/other operational failure -> ERROR

parse three properties
    malformed -> ERROR
    LoadState=not-found -> FAIL
    ActiveState=active -> PASS
    otherwise -> FAIL

return status, reason, normalized name, metrics when trustworthy,
and the complete CommandResult
```

Reasons are deterministic and identify the normalized service. They state
whether the service is active, absent, inactive/failed, operationally
uncheckable, or unsupported.

## Testing Strategy

All unit tests use injected command results and never modify a real service.

### Command-runner tests

- missing executable becomes `CommandErrorKind.NOT_FOUND`;
- permission denial becomes `PERMISSION_DENIED`;
- another `OSError` becomes `OS_ERROR`;
- existing success, nonzero-exit, timeout, decoding, and input tests remain
  green.

### Name tests

- accept stems, complete `.service` names, internal hyphens, and instance
  names;
- append `.service` exactly once;
- reject empty, non-string, whitespace, control characters, leading options,
  paths, shell-like values, other unit suffixes, and overlong values; and
- prove invalid input calls no executor.

### Parser tests

- parse active/running and active/exited properties;
- parse not-found/inactive/dead properties;
- accept any ordering while returning the same model; and
- reject missing, duplicate, blank, unexpected, and malformed records.

### Validator tests

- PASS for active/running and active/exited;
- FAIL with retained metrics for not-found, inactive, and failed;
- ERROR with `metrics=None` for timeout, permission, unexpected exit, and
  malformed output;
- UNSUPPORTED with `metrics=None` for a missing executable and known
  non-systemd diagnostics;
- exact command argument order;
- preservation of the original `CommandResult`; and
- stable human-readable reasons.

### Regression and live smoke test

- the Day 6 module and complete test suite pass;
- all Python modules compile and `git diff --check` succeeds;
- read-only WSL validation reports `cron.service` as PASS; and
- read-only WSL validation reports `sysprobe-missing.service` as FAIL.

The smoke test never stops, starts, enables, or changes a real service. ERROR
and UNSUPPORTED cases remain deterministic injected tests.

## Documentation and Learning Checkpoint

README gains Day 6 behavior, result semantics, usage, focused test command,
and the read-only Linux requirement. A deterministic colored SVG explains the
four statuses and the `systemctl show` data flow.

Before integration work begins, the learner should be able to explain:

- why command success is not the same as service health;
- the difference between `FAIL`, `ERROR`, and `UNSUPPORTED`;
- why `active/exited` can be healthy; and
- how argument-vector execution and input validation reduce injection risk.

## Completion Criteria

Day 6 is complete when:

- the approved shared enums, structured launch-error evidence, service-name
  validation, parser, result objects, and decision policy are implemented;
- new unit tests and the complete existing suite pass;
- the read-only WSL PASS and FAIL smoke tests match the automated policy;
- README and the visual summary match implemented behavior;
- independent review finds no unresolved Critical or Important issue; and
- only the approved files are changed, with user-owned working-tree changes
  preserved.
