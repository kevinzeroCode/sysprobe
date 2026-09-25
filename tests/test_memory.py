from collections.abc import Sequence

import pytest

from sysprobe.result import CommandResult
from sysprobe.validators.memory import (
    MemoryMetrics,
    MemoryValidationResult,
    parse_meminfo,
    validate_memory,
)


MEMINFO_OUTPUT = """MemTotal:       16000000 kB
MemFree:         1000000 kB
MemAvailable:    6000000 kB
Buffers:          200000 kB
Cached:          4000000 kB
SwapTotal:       2000000 kB
SwapFree:        1500000 kB
"""


def make_meminfo(
    *,
    total_kb: int = 1_000,
    free_kb: int = 50,
    available_kb: int = 400,
    buffers_kb: int = 100,
    cached_kb: int = 200,
    swap_total_kb: int = 500,
    swap_free_kb: int = 250,
) -> str:
    return f"""MemTotal:       {total_kb} kB
MemFree:        {free_kb} kB
MemAvailable:   {available_kb} kB
Buffers:        {buffers_kb} kB
Cached:         {cached_kb} kB
SwapTotal:      {swap_total_kb} kB
SwapFree:       {swap_free_kb} kB
"""


def make_command_result(
    *,
    stdout: str = MEMINFO_OUTPUT,
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=("cat", "/proc/meminfo"),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )


def test_parse_meminfo_reads_required_metrics() -> None:
    assert parse_meminfo(MEMINFO_OUTPUT) == MemoryMetrics(
        total_kb=16_000_000,
        free_kb=1_000_000,
        available_kb=6_000_000,
        buffers_kb=200_000,
        cached_kb=4_000_000,
        swap_total_kb=2_000_000,
        swap_free_kb=1_500_000,
        used_kb=10_000_000,
        usage_percent=62.5,
    )


@pytest.mark.parametrize(
    (
        "free_kb",
        "available_kb",
        "swap_free_kb",
        "threshold",
        "expected_passed",
        "expected_reason",
    ),
    [
        (50, 400, 250, 70, True, "Memory usage 60.0% is below threshold 70%"),
        (
            50,
            100,
            250,
            90,
            False,
            "Memory usage 90.0% reached or exceeded threshold 90%",
        ),
        (
            50,
            50,
            250,
            90,
            False,
            "Memory usage 95.0% reached or exceeded threshold 90%",
        ),
        (1, 600, 0, 50, True, "Memory usage 40.0% is below threshold 50%"),
    ],
)
def test_validate_memory_applies_available_memory_threshold(
    free_kb: int,
    available_kb: int,
    swap_free_kb: int,
    threshold: int,
    expected_passed: bool,
    expected_reason: str,
) -> None:
    command_result = make_command_result(
        stdout=make_meminfo(
            free_kb=free_kb,
            available_kb=available_kb,
            swap_free_kb=swap_free_kb,
        ),
    )

    def fake_runner(command: Sequence[str]) -> CommandResult:
        assert tuple(command) == ("cat", "/proc/meminfo")
        return command_result

    result = validate_memory(threshold=threshold, command_executor=fake_runner)

    assert result == MemoryValidationResult(
        passed=expected_passed,
        reason=expected_reason,
        metrics=parse_meminfo(command_result.stdout),
        threshold_percent=threshold,
        command_result=command_result,
    )
    assert result.metrics is not None
    assert result.metrics.free_kb == free_kb
    assert result.metrics.available_kb == available_kb
    assert result.metrics.swap_free_kb == swap_free_kb
