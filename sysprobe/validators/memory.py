from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True, slots=True)
class MemoryMetrics:
    """Raw and calculated values from Linux `/proc/meminfo`."""

    total_kb: int
    free_kb: int
    available_kb: int
    buffers_kb: int
    cached_kb: int
    swap_total_kb: int
    swap_free_kb: int
    used_kb: int
    usage_percent: float


@dataclass(frozen=True, slots=True)
class MemoryValidationResult:
    """The memory decision plus the metrics and command evidence behind it."""

    passed: bool
    reason: str
    metrics: MemoryMetrics | None
    threshold_percent: int
    command_result: CommandResult


def parse_meminfo(output: str) -> MemoryMetrics:
    """Parse the Day 3 fields from `/proc/meminfo`."""

    wanted_fields = {
        "MemTotal",
        "MemFree",
        "MemAvailable",
        "Buffers",
        "Cached",
        "SwapTotal",
        "SwapFree",
    }
    values: dict[str, int] = {}

    for line in output.splitlines():
        if ":" not in line:
            continue
        name, raw_value = line.split(":", maxsplit=1)
        if name not in wanted_fields:
            continue
        value_text, _unit = raw_value.split()
        values[name] = int(value_text)

    total_kb = values["MemTotal"]
    available_kb = values["MemAvailable"]
    used_kb = total_kb - available_kb

    return MemoryMetrics(
        total_kb=total_kb,
        free_kb=values["MemFree"],
        available_kb=available_kb,
        buffers_kb=values["Buffers"],
        cached_kb=values["Cached"],
        swap_total_kb=values["SwapTotal"],
        swap_free_kb=values["SwapFree"],
        used_kb=used_kb,
        usage_percent=used_kb / total_kb * 100,
    )


def validate_memory(
    *,
    threshold: int = 90,
    command_executor: CommandExecutor = run_command,
) -> MemoryValidationResult:
    """Check Linux available-memory usage against a percentage threshold."""

    command_result = command_executor(["cat", "/proc/meminfo"])
    metrics = parse_meminfo(command_result.stdout)
    passed = metrics.usage_percent < threshold
    displayed_usage = f"{metrics.usage_percent:.1f}"

    if passed:
        reason = (
            f"Memory usage {displayed_usage}% is below threshold {threshold}%"
        )
    else:
        reason = (
            f"Memory usage {displayed_usage}% reached or exceeded "
            f"threshold {threshold}%"
        )

    return MemoryValidationResult(
        passed=passed,
        reason=reason,
        metrics=metrics,
        threshold_percent=threshold,
        command_result=command_result,
    )
