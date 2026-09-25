from collections.abc import Sequence

import pytest

from sysprobe.result import CommandResult
from sysprobe.validators.disk import (
    DiskValidationResult,
    parse_disk_usage,
    validate_disk,
)


DF_OUTPUT = """Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/sda1 10000000 7200000 2800000 72% /
"""


def make_df_output(usage_percent: int) -> str:
    return DF_OUTPUT.replace("72%", f"{usage_percent}%")


def make_command_result(
    *,
    stdout: str = DF_OUTPUT,
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=("df", "-P", "/"),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )


def test_parse_disk_usage_reads_capacity_percent() -> None:
    assert parse_disk_usage(DF_OUTPUT) == 72


@pytest.mark.parametrize(
    ("usage_percent", "threshold", "expected_passed", "expected_reason"),
    [
        (72, 90, True, "Disk usage 72% is below threshold 90%"),
        (72, 70, False, "Disk usage 72% reached or exceeded threshold 70%"),
        (90, 90, False, "Disk usage 90% reached or exceeded threshold 90%"),
    ],
)
def test_validate_disk_applies_threshold_rule(
    usage_percent: int,
    threshold: int,
    expected_passed: bool,
    expected_reason: str,
) -> None:
    command_result = make_command_result(stdout=make_df_output(usage_percent))

    def fake_runner(command: Sequence[str]) -> CommandResult:
        assert tuple(command) == ("df", "-P", "/")
        return command_result

    result = validate_disk(threshold=threshold, command_executor=fake_runner)

    assert result == DiskValidationResult(
        passed=expected_passed,
        reason=expected_reason,
        mount_point="/",
        usage_percent=usage_percent,
        threshold_percent=threshold,
        command_result=command_result,
    )
