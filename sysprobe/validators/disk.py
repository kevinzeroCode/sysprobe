from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True, slots=True)
class DiskValidationResult:
    """The disk decision plus the command evidence behind it."""

    passed: bool
    reason: str
    mount_point: str
    usage_percent: int | None
    threshold_percent: int
    command_result: CommandResult


def parse_disk_usage(output: str) -> int:
    """Extract the capacity percentage from POSIX `df -P /` output."""

    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("df output does not contain a data row")

    fields = lines[-1].split()
    if len(fields) < 6:
        raise ValueError("df data row does not contain the expected columns")

    usage_token = fields[-2]
    if not usage_token.endswith("%") or not usage_token[:-1].isdigit():
        raise ValueError("df capacity column is not a percentage")

    return int(usage_token[:-1])


def validate_disk(
    *,
    threshold: int = 90,
    command_executor: CommandExecutor = run_command,
) -> DiskValidationResult:
    """Check Linux root-filesystem usage against a percentage threshold."""

    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, int)
        or not 1 <= threshold <= 100
    ):
        raise ValueError("threshold must be an integer from 1 to 100")

    command_result = command_executor(["df", "-P", "/"])
    if command_result.timed_out:
        return DiskValidationResult(
            passed=False,
            reason="Disk check timed out",
            mount_point="/",
            usage_percent=None,
            threshold_percent=threshold,
            command_result=command_result,
        )

    if command_result.exit_code != 0:
        return DiskValidationResult(
            passed=False,
            reason=f"df command failed with exit code {command_result.exit_code}",
            mount_point="/",
            usage_percent=None,
            threshold_percent=threshold,
            command_result=command_result,
        )

    try:
        usage_percent = parse_disk_usage(command_result.stdout)
    except ValueError:
        return DiskValidationResult(
            passed=False,
            reason="Could not parse disk usage from df output",
            mount_point="/",
            usage_percent=None,
            threshold_percent=threshold,
            command_result=command_result,
        )

    passed = usage_percent < threshold

    if passed:
        reason = f"Disk usage {usage_percent}% is below threshold {threshold}%"
    else:
        reason = (
            f"Disk usage {usage_percent}% reached or exceeded "
            f"threshold {threshold}%"
        )

    return DiskValidationResult(
        passed=passed,
        reason=reason,
        mount_point="/",
        usage_percent=usage_percent,
        threshold_percent=threshold,
        command_result=command_result,
    )
