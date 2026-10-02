# Day 6 Service Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add a read-only systemd service validator that reports PASS, FAIL, ERROR, or UNSUPPORTED while preserving structured command evidence.

**Architecture:** Extend the existing command boundary with typed launch-error evidence, then keep Day 6 policy in sysprobe/validators/service.py. A strict name normalizer and property parser feed one deterministic decision function around systemctl show; existing validators remain unchanged until the later integration milestone.

**Tech Stack:** Python 3.10+, standard-library dataclasses, enum, re, subprocess, pytest 9, systemd systemctl, deterministic SVG

---

## File Structure

- Create tests/test_result.py: stable shared-enum values and backward-compatible CommandResult defaults.
- Modify tests/test_command_runner.py: structured missing-executable, permission, and generic launch-error tests.
- Modify sysprobe/result.py: ValidationStatus, CommandErrorKind, and optional launch-error fields.
- Modify sysprobe/command_runner.py: convert OSError launch failures into CommandResult evidence.
- Create tests/test_service.py: name, parser, decision, error, evidence, and command-vector tests.
- Create sysprobe/validators/service.py: service-name normalization, systemctl parser, immutable models, and policy.
- Modify README.md: Day 6 usage, four statuses, Linux/systemd scope, and focused test command.
- Create docs/day6-service-validator-summary.svg: colored visual summary of query, parse, and classification.

### Task 1: Add the Shared Status and Command-Error Types

**Files:**
- Create: tests/test_result.py
- Modify: sysprobe/result.py

- [ ] **Step 1: Write the failing shared-result tests**

Create tests/test_result.py:

~~~python
from sysprobe.result import (
    CommandErrorKind,
    CommandResult,
    ValidationStatus,
)


def test_validation_status_values_are_stable() -> None:
    assert [status.value for status in ValidationStatus] == [
        "pass",
        "fail",
        "error",
        "unsupported",
    ]


def test_command_result_defaults_to_no_launch_error() -> None:
    result = CommandResult(
        command=("true",),
        exit_code=0,
        stdout="",
        stderr="",
        duration_seconds=0.01,
        timed_out=False,
    )

    assert result.error_kind is None
    assert result.error_message is None
    assert [kind.value for kind in CommandErrorKind] == [
        "not_found",
        "permission_denied",
        "os_error",
    ]
~~~

- [ ] **Step 2: Run the result tests and verify RED**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_result.py -v
~~~

Expected: collection fails because CommandErrorKind and ValidationStatus do not
exist yet.

- [ ] **Step 3: Add the minimal shared result types**

Replace sysprobe/result.py with:

~~~python
from dataclasses import dataclass
from enum import Enum


class ValidationStatus(str, Enum):
    """Machine-stable outcomes shared by integrated validators."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNSUPPORTED = "unsupported"


class CommandErrorKind(str, Enum):
    """Why the operating system could not launch a command."""

    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    OS_ERROR = "os_error"


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Facts captured from one local command execution attempt."""

    command: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    error_kind: CommandErrorKind | None = None
    error_message: str | None = None
~~~

- [ ] **Step 4: Run focused and regression tests and verify GREEN**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_result.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
~~~

Expected: 2 result tests and 110 total tests pass. Existing CommandResult
construction remains compatible because the new fields have defaults.

- [ ] **Step 5: Commit the shared types**

~~~powershell
git add -- sysprobe/result.py tests/test_result.py
git commit -m "feat: add shared validation status"
~~~

### Task 2: Preserve Command Launch Failures as Evidence

**Files:**
- Modify: tests/test_command_runner.py
- Modify: sysprobe/command_runner.py

- [ ] **Step 1: Add failing launch-error tests**

Add this import to tests/test_command_runner.py:

~~~python
from sysprobe.result import CommandErrorKind
~~~

Append:

~~~python
@pytest.mark.parametrize(
    ("launch_error", "expected_kind"),
    [
        (FileNotFoundError("missing executable"), CommandErrorKind.NOT_FOUND),
        (
            PermissionError("permission denied"),
            CommandErrorKind.PERMISSION_DENIED,
        ),
        (OSError("operating system error"), CommandErrorKind.OS_ERROR),
    ],
)
def test_run_command_returns_structured_launch_error(
    monkeypatch: pytest.MonkeyPatch,
    launch_error: OSError,
    expected_kind: CommandErrorKind,
) -> None:
    def raise_launch_error(*_args: object, **_kwargs: object) -> None:
        raise launch_error

    monkeypatch.setattr(subprocess, "run", raise_launch_error)

    result = run_command(["missing-command"], timeout_seconds=1.0)

    assert result.command == ("missing-command",)
    assert result.exit_code is None
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.duration_seconds >= 0
    assert result.timed_out is False
    assert result.error_kind is expected_kind
    assert result.error_message == str(launch_error)
~~~

- [ ] **Step 2: Run the new tests and verify RED**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_command_runner.py -k launch_error -v
~~~

Expected: 3 cases fail because run_command lets each OSError escape.

- [ ] **Step 3: Add structured OSError handling**

Update the production import:

~~~python
from sysprobe.result import CommandErrorKind, CommandResult
~~~

Add this helper below _to_text:

~~~python
def _launch_error_result(
    command: tuple[str, ...],
    *,
    started_at: float,
    error: OSError,
    error_kind: CommandErrorKind,
) -> CommandResult:
    return CommandResult(
        command=command,
        exit_code=None,
        stdout="",
        stderr="",
        duration_seconds=time.perf_counter() - started_at,
        timed_out=False,
        error_kind=error_kind,
        error_message=str(error),
    )
~~~

Add these handlers immediately after the existing TimeoutExpired handler and
before the successful return:

~~~python
    except FileNotFoundError as error:
        return _launch_error_result(
            recorded_command,
            started_at=started_at,
            error=error,
            error_kind=CommandErrorKind.NOT_FOUND,
        )
    except PermissionError as error:
        return _launch_error_result(
            recorded_command,
            started_at=started_at,
            error=error,
            error_kind=CommandErrorKind.PERMISSION_DENIED,
        )
    except OSError as error:
        return _launch_error_result(
            recorded_command,
            started_at=started_at,
            error=error,
            error_kind=CommandErrorKind.OS_ERROR,
        )
~~~

Do not catch Exception. Programming errors must still surface.

- [ ] **Step 4: Run command-runner and complete tests and verify GREEN**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_command_runner.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
~~~

Expected: 9 command-runner cases and 113 total tests pass.

- [ ] **Step 5: Commit the command-boundary slice**

~~~powershell
git add -- sysprobe/command_runner.py tests/test_command_runner.py
git commit -m "feat: preserve command launch errors"
~~~

### Task 3: Normalize Safe Service Names

**Files:**
- Create: tests/test_service.py
- Create: sysprobe/validators/service.py

- [ ] **Step 1: Write the failing accepted-name tests**

Create tests/test_service.py:

~~~python
import pytest

from sysprobe.validators.service import normalize_service_name


@pytest.mark.parametrize(
    ("service_name", "expected"),
    [
        ("cron", "cron.service"),
        ("cron.service", "cron.service"),
        ("systemd-networkd", "systemd-networkd.service"),
        ("ssh@worker", "ssh@worker.service"),
        ("_helper", "_helper.service"),
    ],
)
def test_normalize_service_name_accepts_safe_service_names(
    service_name: str,
    expected: str,
) -> None:
    assert normalize_service_name(service_name) == expected
~~~

- [ ] **Step 2: Write the failing rejected-name tests**

Append:

~~~python
@pytest.mark.parametrize(
    "service_name",
    [
        "",
        " ",
        " cron",
        "cron ",
        "-cron",
        "../cron",
        "bad service",
        "cron;reboot",
        "cron\n",
        "crön",
        123,
        True,
    ],
)
def test_normalize_service_name_rejects_unsafe_values(
    service_name: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="service_name must be a safe systemd service name",
    ):
        normalize_service_name(service_name)


@pytest.mark.parametrize(
    "suffix",
    [
        ".automount",
        ".device",
        ".mount",
        ".path",
        ".scope",
        ".slice",
        ".socket",
        ".swap",
        ".target",
        ".timer",
    ],
)
def test_normalize_service_name_rejects_other_unit_types(
    suffix: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="service_name must be a safe systemd service name",
    ):
        normalize_service_name("cron" + suffix)


def test_normalize_service_name_enforces_systemd_length_limit() -> None:
    assert normalize_service_name("a" * 247) == "a" * 247 + ".service"

    with pytest.raises(
        ValueError,
        match="service_name must be a safe systemd service name",
    ):
        normalize_service_name("a" * 248)
~~~

- [ ] **Step 3: Run the name tests and verify RED**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -v
~~~

Expected: collection fails because sysprobe.validators.service does not exist.

- [ ] **Step 4: Add the minimal name normalizer**

Create sysprobe/validators/service.py:

~~~python
import re


_SERVICE_SUFFIX = ".service"
_OTHER_UNIT_SUFFIXES = (
    ".automount",
    ".device",
    ".mount",
    ".path",
    ".scope",
    ".slice",
    ".socket",
    ".swap",
    ".target",
    ".timer",
)
_SERVICE_STEM = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*")


def normalize_service_name(service_name: object) -> str:
    """Validate one service name and append .service when omitted."""

    error_message = "service_name must be a safe systemd service name"
    if not isinstance(service_name, str) or not service_name:
        raise ValueError(error_message)
    if service_name.endswith(_OTHER_UNIT_SUFFIXES):
        raise ValueError(error_message)

    normalized = (
        service_name
        if service_name.endswith(_SERVICE_SUFFIX)
        else service_name + _SERVICE_SUFFIX
    )
    stem = normalized[: -len(_SERVICE_SUFFIX)]
    if (
        _SERVICE_STEM.fullmatch(stem) is None
        or len(normalized.encode("ascii")) > 255
    ):
        raise ValueError(error_message)

    return normalized
~~~

- [ ] **Step 5: Run focused and complete tests and verify GREEN**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
~~~

Expected: every service-name case and all prior tests pass.

- [ ] **Step 6: Commit safe normalization**

~~~powershell
git add -- sysprobe/validators/service.py tests/test_service.py
git commit -m "feat: normalize systemd service names"
~~~

### Task 4: Parse systemctl Property Output

**Files:**
- Modify: tests/test_service.py
- Modify: sysprobe/validators/service.py

- [ ] **Step 1: Add failing valid-property tests**

Replace the service import in tests/test_service.py with:

~~~python
from sysprobe.validators.service import (
    ServiceMetrics,
    normalize_service_name,
    parse_service_properties,
)
~~~

Append:

~~~python
@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "SubState=running\n",
            ServiceMetrics(
                load_state="loaded",
                active_state="active",
                sub_state="running",
            ),
        ),
        (
            "SubState=exited\n"
            "LoadState=loaded\n"
            "ActiveState=active\n",
            ServiceMetrics(
                load_state="loaded",
                active_state="active",
                sub_state="exited",
            ),
        ),
        (
            "LoadState=not-found\n"
            "ActiveState=inactive\n"
            "SubState=dead\n",
            ServiceMetrics(
                load_state="not-found",
                active_state="inactive",
                sub_state="dead",
            ),
        ),
    ],
)
def test_parse_service_properties_reads_required_states(
    output: str,
    expected: ServiceMetrics,
) -> None:
    assert parse_service_properties(output) == expected
~~~

- [ ] **Step 2: Add failing malformed-property tests**

Append:

~~~python
@pytest.mark.parametrize(
    "output",
    [
        "",
        "LoadState=loaded\nActiveState=active\n",
        (
            "LoadState=loaded\n"
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "SubState=running\n"
        ),
        (
            "LoadState=\n"
            "ActiveState=active\n"
            "SubState=running\n"
        ),
        (
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "Unexpected=value\n"
            "SubState=running\n"
        ),
        (
            "LoadState loaded\n"
            "ActiveState=active\n"
            "SubState=running\n"
        ),
    ],
)
def test_parse_service_properties_rejects_malformed_output(
    output: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="malformed systemctl property output",
    ):
        parse_service_properties(output)
~~~

- [ ] **Step 3: Run parser tests and verify RED**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -k service_properties -v
~~~

Expected: collection fails because ServiceMetrics and
parse_service_properties do not exist.

- [ ] **Step 4: Add the immutable metrics and strict parser**

Add this import to sysprobe/validators/service.py:

~~~python
from dataclasses import dataclass
~~~

Add below the constants:

~~~python
_REQUIRED_PROPERTIES = frozenset(
    {"LoadState", "ActiveState", "SubState"}
)


@dataclass(frozen=True, slots=True)
class ServiceMetrics:
    """Trustworthy service state returned by systemd."""

    load_state: str
    active_state: str
    sub_state: str
~~~

Add below normalize_service_name:

~~~python
def parse_service_properties(output: str) -> ServiceMetrics:
    """Parse the three requested systemctl show properties."""

    values: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise ValueError("malformed systemctl property output")

        name, value = line.split("=", maxsplit=1)
        if (
            name not in _REQUIRED_PROPERTIES
            or name in values
            or not value
        ):
            raise ValueError("malformed systemctl property output")
        values[name] = value

    if values.keys() != _REQUIRED_PROPERTIES:
        raise ValueError("malformed systemctl property output")

    return ServiceMetrics(
        load_state=values["LoadState"],
        active_state=values["ActiveState"],
        sub_state=values["SubState"],
    )
~~~

- [ ] **Step 5: Run service and complete tests and verify GREEN**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
~~~

Expected: all name and parser tests plus the prior suite pass.

- [ ] **Step 6: Commit the parser slice**

~~~powershell
git add -- sysprobe/validators/service.py tests/test_service.py
git commit -m "feat: parse systemd service properties"
~~~

### Task 5: Classify Trustworthy Service Health

**Files:**
- Modify: tests/test_service.py
- Modify: sysprobe/validators/service.py

- [ ] **Step 1: Add test helpers and failing health-policy tests**

Replace the import block at the top of tests/test_service.py with:

~~~python
from collections.abc import Callable, Sequence

import pytest

from sysprobe.result import CommandResult, ValidationStatus
from sysprobe.validators.service import (
    ServiceMetrics,
    ServiceValidationResult,
    normalize_service_name,
    parse_service_properties,
    validate_service,
)
~~~

Add below the imports:

~~~python
SERVICE_COMMAND = (
    "systemctl",
    "show",
    "cron.service",
    "--property=LoadState",
    "--property=ActiveState",
    "--property=SubState",
    "--no-pager",
)


def make_command_result(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=SERVICE_COMMAND,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )


def make_executor(
    result: CommandResult,
) -> tuple[
    Callable[[Sequence[str]], CommandResult],
    list[tuple[str, ...]],
]:
    calls: list[tuple[str, ...]] = []

    def execute(command: Sequence[str]) -> CommandResult:
        calls.append(tuple(command))
        return result

    return execute, calls
~~~

Append:

~~~python
@pytest.mark.parametrize(
    ("output", "expected_status", "expected_reason"),
    [
        (
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "SubState=running\n",
            ValidationStatus.PASS,
            "Service cron.service is active (running)",
        ),
        (
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "SubState=exited\n",
            ValidationStatus.PASS,
            "Service cron.service is active (exited)",
        ),
        (
            "LoadState=not-found\n"
            "ActiveState=inactive\n"
            "SubState=dead\n",
            ValidationStatus.FAIL,
            "Required service cron.service was not found",
        ),
        (
            "LoadState=loaded\n"
            "ActiveState=inactive\n"
            "SubState=dead\n",
            ValidationStatus.FAIL,
            "Service cron.service is not active: inactive (dead)",
        ),
        (
            "LoadState=loaded\n"
            "ActiveState=failed\n"
            "SubState=failed\n",
            ValidationStatus.FAIL,
            "Service cron.service is not active: failed (failed)",
        ),
    ],
)
def test_validate_service_classifies_trustworthy_health(
    output: str,
    expected_status: ValidationStatus,
    expected_reason: str,
) -> None:
    command_result = make_command_result(stdout=output)
    executor, calls = make_executor(command_result)

    result = validate_service("cron", command_executor=executor)

    assert result == ServiceValidationResult(
        status=expected_status,
        reason=expected_reason,
        service_name="cron.service",
        metrics=parse_service_properties(output),
        command_result=command_result,
    )
    assert calls == [SERVICE_COMMAND]
~~~

- [ ] **Step 2: Add the failing pre-execution validation test**

Append:

~~~python
def test_validate_service_rejects_invalid_name_before_execution() -> None:
    def unexpected_executor(_command: Sequence[str]) -> CommandResult:
        raise AssertionError("invalid input must not execute systemctl")

    with pytest.raises(
        ValueError,
        match="service_name must be a safe systemd service name",
    ):
        validate_service("../cron", command_executor=unexpected_executor)
~~~

- [ ] **Step 3: Run health-policy tests and verify RED**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -k "classifies or before_execution" -v
~~~

Expected: collection fails because ServiceValidationResult and validate_service
do not exist.

- [ ] **Step 4: Add result data and the minimal health policy**

Add these imports to sysprobe/validators/service.py:

~~~python
from collections.abc import Callable, Sequence

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult, ValidationStatus
~~~

Add this alias below the imports:

~~~python
CommandExecutor = Callable[[Sequence[str]], CommandResult]
~~~

Add below ServiceMetrics:

~~~python
@dataclass(frozen=True, slots=True)
class ServiceValidationResult:
    """The service decision plus the command evidence behind it."""

    status: ValidationStatus
    reason: str
    service_name: str
    metrics: ServiceMetrics | None
    command_result: CommandResult
~~~

Add below parse_service_properties:

~~~python
def validate_service(
    service_name: str,
    *,
    command_executor: CommandExecutor = run_command,
) -> ServiceValidationResult:
    """Check whether one required systemd service is active."""

    normalized_name = normalize_service_name(service_name)
    command_result = command_executor(
        [
            "systemctl",
            "show",
            normalized_name,
            "--property=LoadState",
            "--property=ActiveState",
            "--property=SubState",
            "--no-pager",
        ]
    )
    metrics = parse_service_properties(command_result.stdout)

    if metrics.load_state == "not-found":
        status = ValidationStatus.FAIL
        reason = f"Required service {normalized_name} was not found"
    elif metrics.active_state == "active":
        status = ValidationStatus.PASS
        reason = (
            f"Service {normalized_name} is active ({metrics.sub_state})"
        )
    else:
        status = ValidationStatus.FAIL
        reason = (
            f"Service {normalized_name} is not active: "
            f"{metrics.active_state} ({metrics.sub_state})"
        )

    return ServiceValidationResult(
        status=status,
        reason=reason,
        service_name=normalized_name,
        metrics=metrics,
        command_result=command_result,
    )
~~~

- [ ] **Step 5: Run service and complete tests and verify GREEN**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
~~~

Expected: active/running and active/exited pass, absent/inactive/failed fail,
the exact argument vector is preserved, and all regressions pass.

- [ ] **Step 6: Commit the health-policy slice**

~~~powershell
git add -- sysprobe/validators/service.py tests/test_service.py
git commit -m "feat: validate systemd service health"
~~~

### Task 6: Classify ERROR and UNSUPPORTED Outcomes

**Files:**
- Modify: tests/test_service.py
- Modify: sysprobe/validators/service.py

- [ ] **Step 1: Extend the test helper for launch errors**

Update the result import in tests/test_service.py:

~~~python
from sysprobe.result import (
    CommandErrorKind,
    CommandResult,
    ValidationStatus,
)
~~~

Replace make_command_result with:

~~~python
def make_command_result(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
    error_kind: CommandErrorKind | None = None,
    error_message: str | None = None,
) -> CommandResult:
    return CommandResult(
        command=SERVICE_COMMAND,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
        error_kind=error_kind,
        error_message=error_message,
    )
~~~

- [ ] **Step 2: Add failing operational-classification tests**

Append:

~~~python
@pytest.mark.parametrize(
    (
        "command_result",
        "expected_status",
        "expected_reason",
    ),
    [
        (
            make_command_result(
                exit_code=None,
                error_kind=CommandErrorKind.NOT_FOUND,
                error_message="systemctl was not found",
            ),
            ValidationStatus.UNSUPPORTED,
            "Service check unsupported: systemctl executable was not found",
        ),
        (
            make_command_result(exit_code=None, timed_out=True),
            ValidationStatus.ERROR,
            "Service check error for cron.service: systemctl timed out",
        ),
        (
            make_command_result(
                exit_code=None,
                error_kind=CommandErrorKind.PERMISSION_DENIED,
                error_message="permission denied",
            ),
            ValidationStatus.ERROR,
            (
                "Service check error for cron.service: "
                "systemctl could not start: permission denied"
            ),
        ),
        (
            make_command_result(
                exit_code=None,
                error_kind=CommandErrorKind.OS_ERROR,
                error_message="operating system error",
            ),
            ValidationStatus.ERROR,
            (
                "Service check error for cron.service: "
                "systemctl could not start: operating system error"
            ),
        ),
        (
            make_command_result(
                exit_code=1,
                stderr=(
                    "System has not been booted with systemd as init system"
                ),
            ),
            ValidationStatus.UNSUPPORTED,
            "Service check unsupported: systemd is unavailable",
        ),
        (
            make_command_result(
                exit_code=1,
                stderr="Failed to connect to bus: Host is down",
            ),
            ValidationStatus.UNSUPPORTED,
            "Service check unsupported: systemd is unavailable",
        ),
        (
            make_command_result(
                exit_code=1,
                stderr="Failed to connect to bus: No such file or directory",
            ),
            ValidationStatus.UNSUPPORTED,
            "Service check unsupported: systemd is unavailable",
        ),
        (
            make_command_result(
                exit_code=1,
                stderr="Failed to connect to bus: Permission denied",
            ),
            ValidationStatus.ERROR,
            (
                "Service check error for cron.service: "
                "systemctl failed with exit code 1"
            ),
        ),
        (
            make_command_result(exit_code=5, stderr="unexpected failure"),
            ValidationStatus.ERROR,
            (
                "Service check error for cron.service: "
                "systemctl failed with exit code 5"
            ),
        ),
        (
            make_command_result(stdout="broken\n"),
            ValidationStatus.ERROR,
            (
                "Service check error for cron.service: "
                "malformed systemctl output"
            ),
        ),
    ],
)
def test_validate_service_classifies_unavailable_evidence(
    command_result: CommandResult,
    expected_status: ValidationStatus,
    expected_reason: str,
) -> None:
    executor, calls = make_executor(command_result)

    result = validate_service("cron", command_executor=executor)

    assert result == ServiceValidationResult(
        status=expected_status,
        reason=expected_reason,
        service_name="cron.service",
        metrics=None,
        command_result=command_result,
    )
    assert calls == [SERVICE_COMMAND]
~~~

- [ ] **Step 3: Run unavailable-evidence tests and verify RED**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -k unavailable_evidence -v
~~~

Expected: missing, timeout, permission, and nonzero cases error while parsing
empty output; the malformed case raises ValueError instead of returning ERROR.

- [ ] **Step 4: Add deterministic operational classification**

Update the result import in sysprobe/validators/service.py:

~~~python
from sysprobe.result import (
    CommandErrorKind,
    CommandResult,
    ValidationStatus,
)
~~~

Add below _REQUIRED_PROPERTIES:

~~~python
_UNSUPPORTED_SYSTEMD_DIAGNOSTICS = (
    "System has not been booted with systemd",
    "Failed to connect to bus: Host is down",
    "Failed to connect to bus: No such file or directory",
)
~~~

Replace validate_service with:

~~~python
def validate_service(
    service_name: str,
    *,
    command_executor: CommandExecutor = run_command,
) -> ServiceValidationResult:
    """Check whether one required systemd service is active."""

    normalized_name = normalize_service_name(service_name)
    command_result = command_executor(
        [
            "systemctl",
            "show",
            normalized_name,
            "--property=LoadState",
            "--property=ActiveState",
            "--property=SubState",
            "--no-pager",
        ]
    )

    if command_result.error_kind is CommandErrorKind.NOT_FOUND:
        return ServiceValidationResult(
            status=ValidationStatus.UNSUPPORTED,
            reason=(
                "Service check unsupported: "
                "systemctl executable was not found"
            ),
            service_name=normalized_name,
            metrics=None,
            command_result=command_result,
        )

    if command_result.error_kind is not None:
        detail = command_result.error_message or command_result.error_kind.value
        return ServiceValidationResult(
            status=ValidationStatus.ERROR,
            reason=(
                f"Service check error for {normalized_name}: "
                f"systemctl could not start: {detail}"
            ),
            service_name=normalized_name,
            metrics=None,
            command_result=command_result,
        )

    if command_result.timed_out:
        return ServiceValidationResult(
            status=ValidationStatus.ERROR,
            reason=(
                f"Service check error for {normalized_name}: "
                "systemctl timed out"
            ),
            service_name=normalized_name,
            metrics=None,
            command_result=command_result,
        )

    if command_result.exit_code != 0:
        unsupported = any(
            diagnostic in command_result.stderr
            for diagnostic in _UNSUPPORTED_SYSTEMD_DIAGNOSTICS
        )
        return ServiceValidationResult(
            status=(
                ValidationStatus.UNSUPPORTED
                if unsupported
                else ValidationStatus.ERROR
            ),
            reason=(
                "Service check unsupported: systemd is unavailable"
                if unsupported
                else (
                    f"Service check error for {normalized_name}: "
                    "systemctl failed with exit code "
                    f"{command_result.exit_code}"
                )
            ),
            service_name=normalized_name,
            metrics=None,
            command_result=command_result,
        )

    try:
        metrics = parse_service_properties(command_result.stdout)
    except ValueError:
        return ServiceValidationResult(
            status=ValidationStatus.ERROR,
            reason=(
                f"Service check error for {normalized_name}: "
                "malformed systemctl output"
            ),
            service_name=normalized_name,
            metrics=None,
            command_result=command_result,
        )

    if metrics.load_state == "not-found":
        status = ValidationStatus.FAIL
        reason = f"Required service {normalized_name} was not found"
    elif metrics.active_state == "active":
        status = ValidationStatus.PASS
        reason = (
            f"Service {normalized_name} is active ({metrics.sub_state})"
        )
    else:
        status = ValidationStatus.FAIL
        reason = (
            f"Service {normalized_name} is not active: "
            f"{metrics.active_state} ({metrics.sub_state})"
        )

    return ServiceValidationResult(
        status=status,
        reason=reason,
        service_name=normalized_name,
        metrics=metrics,
        command_result=command_result,
    )
~~~

- [ ] **Step 5: Run Day 6 and complete tests and verify GREEN**

Run:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
~~~

Expected: all four statuses, exact reasons, metrics rules, command evidence,
and prior validators pass.

- [ ] **Step 6: Commit error classification**

~~~powershell
git add -- sysprobe/validators/service.py tests/test_service.py
git commit -m "feat: classify service check outcomes"
~~~

### Task 7: Document Day 6 and Add the Learning Diagram

**Files:**
- Modify: README.md
- Create: docs/day6-service-validator-summary.svg

- [ ] **Step 1: Update the project introduction**

Extend the README introduction so the final sentences read:

~~~markdown
validator that normalizes Linux load average by available CPU count. Day 5
adds a layered IPv4 network validator with an optional reachability check. Day
6 adds a read-only systemd service validator with explicit PASS, FAIL, ERROR,
and UNSUPPORTED outcomes.
~~~

- [ ] **Step 2: Add the Day 6 README section before Requirements**

Insert:

~~~~markdown
## Day 6 behavior

validate_service queries one local systemd service with:

~~~text
systemctl show <name>.service \
  --property=LoadState \
  --property=ActiveState \
  --property=SubState \
  --no-pager
~~~

The caller may write cron or cron.service. SysProbe validates the name before
execution and never invokes a shell.

~~~python
from sysprobe.validators.service import validate_service

result = validate_service("cron")

print(result.status.value.upper())
print(result.reason)
print(result.metrics)
~~~

The four outcomes answer different questions:

- PASS: systemd reports ActiveState=active.
- FAIL: the required service is absent, inactive, or failed.
- ERROR: the check timed out, lacked permission, failed unexpectedly, or
  returned malformed data.
- UNSUPPORTED: systemctl or a usable systemd manager is unavailable.

The result.status field uses the shared ValidationStatus enum so later CLI and
JSON integration can consume the same stable machine values.

ActiveState=active remains PASS when SubState=exited because a successful
oneshot service may complete its process while systemd keeps the unit active.
The real check requires Linux with systemd. Deterministic unit tests run on
Windows and never start, stop, or modify a service.

Run only the Day 6 tests:

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_service.py tests/test_result.py tests/test_command_runner.py -v
~~~

### Day 6 visual summary

![Day 6 Service Validator flow](docs/day6-service-validator-summary.svg)
~~~~

When writing the README, use backtick code fences if that matches the
surrounding file.

- [ ] **Step 3: Create the deterministic colored SVG**

Create docs/day6-service-validator-summary.svg:

~~~xml
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="860" viewBox="0 0 1400 860" role="img" aria-labelledby="title desc">
  <title id="title">SysProbe Day 6 Service Validator</title>
  <desc id="desc">A safe service name flows through systemctl show, strict property parsing, and four explicit outcomes.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#eff6ff"/>
      <stop offset="1" stop-color="#f5f3ff"/>
    </linearGradient>
    <filter id="shadow"><feDropShadow dx="0" dy="7" stdDeviation="7" flood-opacity="0.14"/></filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#475569"/></marker>
    <style>
      text{font-family:"Segoe UI","Microsoft JhengHei",sans-serif;fill:#0f172a}.title{font-size:36px;font-weight:700}.sub{font-size:18px;fill:#475569}.head{font-size:22px;font-weight:700}.body{font-size:17px}.small{font-size:15px;fill:#475569}.code{font:700 15px Consolas,monospace}.card{stroke-width:2;filter:url(#shadow)}.arrow{stroke:#475569;stroke-width:4;fill:none;marker-end:url(#arrow)}
    </style>
  </defs>
  <rect width="1400" height="860" fill="url(#bg)"/>
  <text x="60" y="60" class="title">SysProbe Day 6：systemd 服務驗證</text>
  <text x="60" y="94" class="sub">命令成功不等於服務健康：查詢後仍要解析狀態</text>

  <rect class="card" x="60" y="155" width="340" height="210" rx="24" fill="#dbeafe" stroke="#60a5fa"/>
  <text x="90" y="202" class="head">1　安全輸入</text>
  <text x="90" y="246" class="code">cron → cron.service</text>
  <text x="90" y="288" class="body">拒絕路徑、空白、其他 unit</text>
  <text x="90" y="324" class="small">不經 shell，不修改服務</text>

  <path class="arrow" d="M400 260 L500 260"/>
  <rect class="card" x="515" y="155" width="370" height="210" rx="24" fill="#ede9fe" stroke="#a78bfa"/>
  <text x="545" y="202" class="head">2　唯讀查詢</text>
  <text x="545" y="244" class="code">systemctl show</text>
  <text x="545" y="284" class="body">LoadState / ActiveState</text>
  <text x="545" y="318" class="body">SubState + CommandResult</text>

  <path class="arrow" d="M885 260 L985 260"/>
  <rect class="card" x="1000" y="155" width="340" height="210" rx="24" fill="#fef3c7" stroke="#f59e0b"/>
  <text x="1030" y="202" class="head">3　嚴格解析</text>
  <text x="1030" y="244" class="body">三個欄位都必須存在</text>
  <text x="1030" y="282" class="body">缺漏、重複、損壞 → ERROR</text>
  <text x="1030" y="320" class="small">exit code 0 仍需判斷內容</text>

  <path class="arrow" d="M700 365 L700 465"/>
  <rect class="card" x="110" y="490" width="260" height="190" rx="24" fill="#dcfce7" stroke="#4ade80"/>
  <text x="145" y="540" class="head">PASS</text>
  <text x="145" y="582" class="body">ActiveState=active</text>
  <text x="145" y="620" class="small">running 或 exited</text>

  <rect class="card" x="415" y="490" width="260" height="190" rx="24" fill="#fee2e2" stroke="#f87171"/>
  <text x="450" y="540" class="head">FAIL</text>
  <text x="450" y="582" class="body">not-found / inactive</text>
  <text x="450" y="620" class="small">服務確定不符合政策</text>

  <rect class="card" x="720" y="490" width="260" height="190" rx="24" fill="#ffedd5" stroke="#fb923c"/>
  <text x="755" y="540" class="head">ERROR</text>
  <text x="755" y="582" class="body">timeout / permission</text>
  <text x="755" y="620" class="small">檢查結果不可信</text>

  <rect class="card" x="1025" y="490" width="260" height="190" rx="24" fill="#e2e8f0" stroke="#94a3b8"/>
  <text x="1060" y="540" class="head">UNSUPPORTED</text>
  <text x="1060" y="582" class="body">無 systemctl / systemd</text>
  <text x="1060" y="620" class="small">環境不提供這種能力</text>

  <rect x="285" y="740" width="830" height="70" rx="22" fill="#ffffff" stroke="#94a3b8" stroke-width="2"/>
  <text x="330" y="784" class="body">先分清「服務壞了」和「檢查做不到」，才能快速排錯</text>
</svg>
~~~

- [ ] **Step 4: Validate docs, SVG, and tests**

Run:

~~~powershell
python -c "import xml.etree.ElementTree as ET; ET.parse('docs/day6-service-validator-summary.svg')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
rg -n "Day 6|ValidationStatus|systemctl show|UNSUPPORTED|active.*exited" README.md docs/day6-service-validator-summary.svg
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
git diff --check
~~~

Expected: XML parsing succeeds, each documentation concept is found, the
complete suite passes, and diff-check prints nothing.

- [ ] **Step 5: Commit Day 6 documentation**

~~~powershell
git add -- README.md docs/day6-service-validator-summary.svg
git commit -m "docs: explain Day 6 service validation"
~~~

### Task 8: Final Verification, WSL Smoke Test, and Review

**Files:**
- Verify only; no planned modifications.

- [ ] **Step 1: Run focused tests, the full suite, compilation, and diff check**

~~~powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_result.py tests/test_command_runner.py tests/test_service.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m compileall -q sysprobe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -c "import xml.etree.ElementTree as ET; ET.parse('docs/day6-service-validator-summary.svg')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git diff --check
~~~

Purpose: prove Day 6, all regressions, Python syntax, SVG syntax, and whitespace
are clean with fresh evidence.

- [ ] **Step 2: Verify branch cleanliness and exact scope**

~~~powershell
git status --short --branch
git log --oneline main..HEAD
git diff --stat main...HEAD
git diff --name-only main...HEAD
~~~

Expected changed paths:

~~~text
README.md
docs/day6-service-validator-summary.svg
docs/superpowers/plans/2026-10-02-service-validator.md
sysprobe/command_runner.py
sysprobe/result.py
sysprobe/validators/service.py
tests/test_command_runner.py
tests/test_result.py
tests/test_service.py
~~~

- [ ] **Step 3: Run the read-only WSL PASS smoke test**

From Ubuntu WSL in this worktree, run:

~~~bash
python3 -c "from sysprobe.validators.service import validate_service; result = validate_service('cron'); print(result.status.value.upper()); print(result.reason); print(result.metrics)"
~~~

Expected:

~~~text
PASS
Service cron.service is active (running)
ServiceMetrics(load_state='loaded', active_state='active', sub_state='running')
~~~

If cron has a different trustworthy sub-state, explain it before deciding
whether the generic ActiveState policy still passes.

- [ ] **Step 4: Run the read-only WSL FAIL smoke test**

~~~bash
python3 -c "from sysprobe.validators.service import validate_service; result = validate_service('sysprobe-missing'); print(result.status.value.upper()); print(result.reason); print(result.metrics)"
~~~

Expected:

~~~text
FAIL
Required service sysprobe-missing.service was not found
ServiceMetrics(load_state='not-found', active_state='inactive', sub_state='dead')
~~~

Do not stop or modify a real service to manufacture failure.

- [ ] **Step 5: Review against the approved specification**

Check every acceptance criterion in
docs/superpowers/specs/2026-10-02-service-validator-design.md. Pay special
attention to:

- FAIL versus ERROR versus UNSUPPORTED semantics;
- active/exited remaining PASS;
- invalid names executing no command;
- exact allowed unsupported diagnostic fragments;
- metrics retained only for trustworthy parsed states;
- all CommandResult evidence retained;
- no shell, remediation, pgrep fallback, other unit types, YAML, CLI, or remote
  execution; and
- preservation of user-owned files outside the worktree.

- [ ] **Step 6: Request independent review and resolve findings**

Use the superpowers:requesting-code-review workflow with:

~~~text
BASE_SHA: 88576633bca9da8f17754e7ed708a332e529c82d
HEAD_SHA: current feature HEAD
WHAT_WAS_IMPLEMENTED: Day 6 shared result foundation and systemd service validator
PLAN_OR_REQUIREMENTS: docs/superpowers/specs/2026-10-02-service-validator-design.md
~~~

Resolve every verified Critical or Important finding and re-run Step 1 after
any fix. Re-review fixes before proceeding.

- [ ] **Step 7: Integrate only after fresh evidence and user approval**

Use superpowers:finishing-a-development-branch. Present the four integration
options and merge or push only after the user chooses.
