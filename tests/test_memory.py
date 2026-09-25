MEMINFO_OUTPUT = """MemTotal:       16000000 kB
MemFree:         1000000 kB
MemAvailable:    6000000 kB
Buffers:          200000 kB
Cached:          4000000 kB
SwapTotal:       2000000 kB
SwapFree:        1500000 kB
"""


def test_parse_meminfo_reads_required_metrics() -> None:
    from sysprobe.validators.memory import MemoryMetrics, parse_meminfo

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
