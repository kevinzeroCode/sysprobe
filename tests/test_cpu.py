from collections.abc import Callable, Sequence

import pytest

from sysprobe.result import CommandResult
from sysprobe.validators.cpu import (
    CpuMetrics,
    CpuValidationResult,
    parse_cpu_count,
    parse_loadavg,
    validate_cpu,
)


LOAD_COMMAND = ("cat", "/proc/loadavg")
CPU_COUNT_COMMAND = ("nproc",)


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
    load_result: CommandResult,
    cpu_count_result: CommandResult,
) -> tuple[
    Callable[[Sequence[str]], CommandResult],
    list[tuple[str, ...]],
]:
    calls: list[tuple[str, ...]] = []
    results = {
        LOAD_COMMAND: load_result,
        CPU_COUNT_COMMAND: cpu_count_result,
    }

    def execute(command: Sequence[str]) -> CommandResult:
        recorded_command = tuple(command)
        calls.append(recorded_command)
        return results[recorded_command]

    return execute, calls


def test_parse_loadavg_reads_three_time_windows() -> None:
    assert parse_loadavg("0.42 0.58 0.61 2/123 4567\n") == (
        0.42,
        0.58,
        0.61,
    )


@pytest.mark.parametrize(
    ("output", "message"),
    [
        ("", "loadavg output must contain three load averages"),
        ("0.1 nope 0.3 1/10 123\n", "load averages must be numbers"),
        (
            "-0.1 0.2 0.3 1/10 123\n",
            "load averages must be finite non-negative numbers",
        ),
        (
            "nan 0.2 0.3 1/10 123\n",
            "load averages must be finite non-negative numbers",
        ),
        (
            "inf 0.2 0.3 1/10 123\n",
            "load averages must be finite non-negative numbers",
        ),
    ],
)
def test_parse_loadavg_rejects_malformed_values(
    output: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_loadavg(output)


def test_parse_cpu_count_reads_positive_integer() -> None:
    assert parse_cpu_count("  8\n") == 8


@pytest.mark.parametrize("output", ["", "0\n", "-1\n", "4.0\n", "4 8\n"])
def test_parse_cpu_count_rejects_malformed_values(output: str) -> None:
    with pytest.raises(
        ValueError,
        match="CPU count must be one positive integer",
    ):
        parse_cpu_count(output)


@pytest.mark.parametrize(
    (
        "load_output",
        "cpu_count",
        "threshold",
        "expected_normalized",
        "expected_passed",
        "expected_reason",
    ),
    [
        (
            "3.00 1.50 0.75 2/100 1234\n",
            4,
            1.0,
            0.75,
            True,
            "Normalized CPU load 0.75 is below threshold 1.00",
        ),
        (
            "4.00 2.00 1.00 2/100 1234\n",
            4,
            1.0,
            1.0,
            False,
            "Normalized CPU load 1.00 reached or exceeded threshold 1.00",
        ),
        (
            "5.00 2.00 1.00 2/100 1234\n",
            4,
            1.0,
            1.25,
            False,
            "Normalized CPU load 1.25 reached or exceeded threshold 1.00",
        ),
        (
            "1.00 9.00 12.00 2/100 1234\n",
            2,
            1,
            0.5,
            True,
            "Normalized CPU load 0.50 is below threshold 1.00",
        ),
    ],
)
def test_validate_cpu_normalizes_one_minute_load(
    load_output: str,
    cpu_count: int,
    threshold: float,
    expected_normalized: float,
    expected_passed: bool,
    expected_reason: str,
) -> None:
    load_result = make_command_result(LOAD_COMMAND, stdout=load_output)
    cpu_count_result = make_command_result(
        CPU_COUNT_COMMAND,
        stdout=f"{cpu_count}\n",
    )
    executor, calls = make_executor(load_result, cpu_count_result)

    result = validate_cpu(threshold=threshold, command_executor=executor)

    load_1m, load_5m, load_15m = parse_loadavg(load_output)
    assert result == CpuValidationResult(
        passed=expected_passed,
        reason=expected_reason,
        metrics=CpuMetrics(
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            logical_cpu_count=cpu_count,
            normalized_load_1m=expected_normalized,
        ),
        threshold=float(threshold),
        load_command_result=load_result,
        cpu_count_command_result=cpu_count_result,
    )
    assert calls == [LOAD_COMMAND, CPU_COUNT_COMMAND]


@pytest.mark.parametrize(
    ("load_result", "cpu_count_result", "expected_reason"),
    [
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="partial output",
                exit_code=None,
                timed_out=True,
            ),
            make_command_result(CPU_COUNT_COMMAND, stdout="4\n"),
            "CPU check failed: load average command timed out",
        ),
        (
            make_command_result(LOAD_COMMAND, exit_code=2),
            make_command_result(CPU_COUNT_COMMAND, stdout="4\n"),
            "CPU check failed: load average command failed with exit code 2",
        ),
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="1.0 0.5 0.2 1/10 123\n",
            ),
            make_command_result(
                CPU_COUNT_COMMAND,
                stdout="partial",
                exit_code=None,
                timed_out=True,
            ),
            "CPU check failed: nproc timed out",
        ),
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="1.0 0.5 0.2 1/10 123\n",
            ),
            make_command_result(CPU_COUNT_COMMAND, exit_code=1),
            "CPU check failed: nproc failed with exit code 1",
        ),
        (
            make_command_result(LOAD_COMMAND, stdout="not loadavg\n"),
            make_command_result(CPU_COUNT_COMMAND, stdout="4\n"),
            "CPU check failed: malformed /proc/loadavg output",
        ),
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="1.0 0.5 0.2 1/10 123\n",
            ),
            make_command_result(CPU_COUNT_COMMAND, stdout="zero\n"),
            "CPU check failed: malformed nproc output",
        ),
    ],
)
def test_validate_cpu_reports_command_or_parse_failure(
    load_result: CommandResult,
    cpu_count_result: CommandResult,
    expected_reason: str,
) -> None:
    executor, calls = make_executor(load_result, cpu_count_result)

    result = validate_cpu(command_executor=executor)

    assert result.passed is False
    assert result.reason == expected_reason
    assert result.metrics is None
    assert result.load_command_result is load_result
    assert result.cpu_count_command_result is cpu_count_result
    assert calls == [LOAD_COMMAND, CPU_COUNT_COMMAND]


def test_validate_cpu_reports_both_failures_in_stable_order() -> None:
    load_result = make_command_result(LOAD_COMMAND, stdout="not loadavg\n")
    cpu_count_result = make_command_result(CPU_COUNT_COMMAND, exit_code=1)
    executor, calls = make_executor(load_result, cpu_count_result)

    result = validate_cpu(command_executor=executor)

    assert result.reason == (
        "CPU check failed: malformed /proc/loadavg output; "
        "nproc failed with exit code 1"
    )
    assert result.metrics is None
    assert result.load_command_result is load_result
    assert result.cpu_count_command_result is cpu_count_result
    assert calls == [LOAD_COMMAND, CPU_COUNT_COMMAND]


@pytest.mark.parametrize(
    "threshold",
    [0, -0.1, float("nan"), float("inf"), True, "1.0"],
)
def test_validate_cpu_rejects_invalid_threshold(threshold: object) -> None:
    def unexpected_runner(_command: Sequence[str]) -> CommandResult:
        raise AssertionError("invalid configuration must fail before execution")

    with pytest.raises(
        ValueError,
        match="threshold must be a finite number greater than zero",
    ):
        validate_cpu(
            threshold=threshold,  # type: ignore[arg-type]
            command_executor=unexpected_runner,
        )
