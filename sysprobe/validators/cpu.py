from collections.abc import Callable, Sequence
from dataclasses import dataclass
import math

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]


def parse_loadavg(output: str) -> tuple[float, float, float]:
    """Parse the 1-, 5-, and 15-minute values from `/proc/loadavg`."""

    fields = output.split()
    if len(fields) < 3:
        raise ValueError("loadavg output must contain three load averages")

    try:
        load_1m, load_5m, load_15m = (
            float(fields[0]),
            float(fields[1]),
            float(fields[2]),
        )
    except ValueError as error:
        raise ValueError("load averages must be numbers") from error

    loads = (load_1m, load_5m, load_15m)
    if any(not math.isfinite(load) or load < 0 for load in loads):
        raise ValueError("load averages must be finite non-negative numbers")

    return loads


def parse_cpu_count(output: str) -> int:
    """Parse the positive processing-unit count returned by `nproc`."""

    fields = output.split()
    if len(fields) != 1 or not fields[0].isdigit():
        raise ValueError("CPU count must be one positive integer")

    cpu_count = int(fields[0])
    if cpu_count <= 0:
        raise ValueError("CPU count must be one positive integer")

    return cpu_count


@dataclass(frozen=True, slots=True)
class CpuMetrics:
    """Raw Linux load values plus the normalized one-minute load."""

    load_1m: float
    load_5m: float
    load_15m: float
    logical_cpu_count: int
    normalized_load_1m: float


@dataclass(frozen=True, slots=True)
class CpuValidationResult:
    """The CPU decision plus both command records behind it."""

    passed: bool
    reason: str
    metrics: CpuMetrics | None
    threshold: float
    load_command_result: CommandResult
    cpu_count_command_result: CommandResult


def validate_cpu(
    *,
    threshold: float = 1.0,
    command_executor: CommandExecutor = run_command,
) -> CpuValidationResult:
    """Check normalized Linux one-minute load against a threshold."""

    threshold_value = float(threshold)
    load_result = command_executor(["cat", "/proc/loadavg"])
    cpu_count_result = command_executor(["nproc"])

    load_1m, load_5m, load_15m = parse_loadavg(load_result.stdout)
    logical_cpu_count = parse_cpu_count(cpu_count_result.stdout)
    normalized_load_1m = load_1m / logical_cpu_count
    passed = normalized_load_1m < threshold_value

    if passed:
        reason = (
            f"Normalized CPU load {normalized_load_1m:.2f} is below "
            f"threshold {threshold_value:.2f}"
        )
    else:
        reason = (
            f"Normalized CPU load {normalized_load_1m:.2f} reached or "
            f"exceeded threshold {threshold_value:.2f}"
        )

    return CpuValidationResult(
        passed=passed,
        reason=reason,
        metrics=CpuMetrics(
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            logical_cpu_count=logical_cpu_count,
            normalized_load_1m=normalized_load_1m,
        ),
        threshold=threshold_value,
        load_command_result=load_result,
        cpu_count_command_result=cpu_count_result,
    )
