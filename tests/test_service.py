from collections.abc import Callable, Sequence

import pytest

from sysprobe.result import CommandErrorKind, CommandResult, ValidationStatus
from sysprobe.validators.service import (
    ServiceMetrics,
    ServiceValidationResult,
    normalize_service_name,
    parse_service_properties,
    validate_service,
)


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


def make_executor(
    result: CommandResult,
) -> tuple[list[tuple[str, ...]], Callable[[Sequence[str]], CommandResult]]:
    calls: list[tuple[str, ...]] = []

    def execute(command: Sequence[str]) -> CommandResult:
        assert isinstance(command, list)
        calls.append(tuple(command))
        return result

    return calls, execute


@pytest.mark.parametrize(
    ("command_result", "status", "reason"),
    [
        (make_command_result(exit_code=None, error_kind=CommandErrorKind.NOT_FOUND, error_message="systemctl was not found"), ValidationStatus.UNSUPPORTED, "Service check unsupported: systemctl executable was not found"),
        (make_command_result(exit_code=None, timed_out=True), ValidationStatus.ERROR, "Service check error for cron.service: systemctl timed out"),
        (make_command_result(exit_code=None, error_kind=CommandErrorKind.PERMISSION_DENIED, error_message="permission denied"), ValidationStatus.ERROR, "Service check error for cron.service: systemctl could not start: permission denied"),
        (make_command_result(exit_code=None, error_kind=CommandErrorKind.OS_ERROR, error_message="operating system error"), ValidationStatus.ERROR, "Service check error for cron.service: systemctl could not start: operating system error"),
        (make_command_result(exit_code=1, stderr="System has not been booted with systemd as init system"), ValidationStatus.UNSUPPORTED, "Service check unsupported: systemd is unavailable"),
        (make_command_result(exit_code=1, stderr="Failed to connect to bus: Host is down"), ValidationStatus.UNSUPPORTED, "Service check unsupported: systemd is unavailable"),
        (make_command_result(exit_code=1, stderr="Failed to connect to bus: No such file or directory"), ValidationStatus.UNSUPPORTED, "Service check unsupported: systemd is unavailable"),
        (make_command_result(exit_code=1, stderr="Failed to connect to bus: Permission denied"), ValidationStatus.ERROR, "Service check error for cron.service: systemctl failed with exit code 1"),
        (make_command_result(exit_code=5, stderr="unexpected failure"), ValidationStatus.ERROR, "Service check error for cron.service: systemctl failed with exit code 5"),
        (make_command_result(exit_code=0, stdout="LoadState=loaded\nActiveState=active\n"), ValidationStatus.ERROR, "Service check error for cron.service: malformed systemctl output"),
    ],
)
def test_validate_service_unavailable_evidence(
    command_result: CommandResult, status: ValidationStatus, reason: str
) -> None:
    calls, executor = make_executor(command_result)
    result = validate_service("cron", command_executor=executor)
    assert isinstance(result, ServiceValidationResult)
    assert result.status is status
    assert result.reason == reason
    assert result.service_name == "cron.service"
    assert result.metrics is None
    assert result.command_result is command_result
    assert calls == [SERVICE_COMMAND]


@pytest.mark.parametrize(
    ("output", "status", "reason", "metrics"),
    [
        (
            "LoadState=loaded\nActiveState=active\nSubState=running\n",
            ValidationStatus.PASS,
            "Service cron.service is active (running)",
            ServiceMetrics("loaded", "active", "running"),
        ),
        (
            "LoadState=loaded\nActiveState=active\nSubState=exited\n",
            ValidationStatus.PASS,
            "Service cron.service is active (exited)",
            ServiceMetrics("loaded", "active", "exited"),
        ),
        (
            "LoadState=not-found\nActiveState=inactive\nSubState=dead\n",
            ValidationStatus.FAIL,
            "Required service cron.service was not found",
            ServiceMetrics("not-found", "inactive", "dead"),
        ),
        (
            "LoadState=not-found\nActiveState=active\nSubState=running\n",
            ValidationStatus.FAIL,
            "Required service cron.service was not found",
            ServiceMetrics("not-found", "active", "running"),
        ),
        (
            "LoadState=loaded\nActiveState=inactive\nSubState=dead\n",
            ValidationStatus.FAIL,
            "Service cron.service is not active: inactive (dead)",
            ServiceMetrics("loaded", "inactive", "dead"),
        ),
        (
            "LoadState=loaded\nActiveState=failed\nSubState=failed\n",
            ValidationStatus.FAIL,
            "Service cron.service is not active: failed (failed)",
            ServiceMetrics("loaded", "failed", "failed"),
        ),
    ],
)
def test_validate_service_classifies_trustworthy_properties(
    output: str,
    status: ValidationStatus,
    reason: str,
    metrics: ServiceMetrics,
) -> None:
    command_result = make_command_result(stdout=output)
    calls, executor = make_executor(command_result)

    result = validate_service("cron", command_executor=executor)

    assert result == ServiceValidationResult(
        status=status,
        reason=reason,
        service_name="cron.service",
        metrics=metrics,
        command_result=command_result,
    )
    assert calls == [SERVICE_COMMAND]


def test_validate_service_rejects_invalid_name_before_execution() -> None:
    command_result = make_command_result()
    calls, executor = make_executor(command_result)

    with pytest.raises(
        ValueError, match="service_name must be a safe systemd service name"
    ):
        validate_service("../cron", command_executor=executor)

    assert calls == []


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            "LoadState=loaded\nActiveState=active\nSubState=running\n",
            ServiceMetrics("loaded", "active", "running"),
        ),
        (
            "SubState=exited\nLoadState=loaded\nActiveState=active\n",
            ServiceMetrics("loaded", "active", "exited"),
        ),
        (
            "LoadState=not-found\nActiveState=inactive\nSubState=dead\n",
            ServiceMetrics("not-found", "inactive", "dead"),
        ),
    ],
)
def test_parse_service_properties_reads_required_states(output: str, expected: ServiceMetrics) -> None:
    assert parse_service_properties(output) == expected


@pytest.mark.parametrize(
    "output",
    [
        "",
        "LoadState=loaded\nActiveState=active\n",
        "LoadState=loaded\nLoadState=loaded\nActiveState=active\nSubState=running\n",
        "LoadState=\nActiveState=active\nSubState=running\n",
        "LoadState=loaded\nActiveState=active\nSubState=running\nOther=value\n",
        "LoadState=loaded\nActiveState=active\nSubState\n",
    ],
)
def test_parse_service_properties_rejects_malformed_output(output: str) -> None:
    with pytest.raises(ValueError, match="malformed systemctl property output"):
        parse_service_properties(output)


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
def test_normalize_safe_service_names(service_name, expected):
    assert normalize_service_name(service_name) == expected


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
        "cr繹n",
        123,
        True,
    ],
)
def test_rejects_unsafe_service_names(service_name):
    with pytest.raises(
        ValueError, match="service_name must be a safe systemd service name"
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
def test_rejects_other_unit_suffixes(suffix):
    with pytest.raises(
        ValueError, match="service_name must be a safe systemd service name"
    ):
        normalize_service_name("cron" + suffix)


def test_accepts_maximum_length_normalized_service_name():
    assert normalize_service_name("a" * 247) == "a" * 247 + ".service"


def test_rejects_service_name_over_maximum_length():
    with pytest.raises(
        ValueError, match="service_name must be a safe systemd service name"
    ):
        normalize_service_name("a" * 248)
