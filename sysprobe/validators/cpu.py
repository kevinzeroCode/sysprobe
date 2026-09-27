import math


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
