from dataclasses import dataclass


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
