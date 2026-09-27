import pytest


def test_parse_loadavg_reads_three_time_windows() -> None:
    from sysprobe.validators.cpu import parse_loadavg

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
    from sysprobe.validators.cpu import parse_loadavg

    with pytest.raises(ValueError, match=message):
        parse_loadavg(output)


def test_parse_cpu_count_reads_positive_integer() -> None:
    from sysprobe.validators.cpu import parse_cpu_count

    assert parse_cpu_count("  8\n") == 8


@pytest.mark.parametrize("output", ["", "0\n", "-1\n", "4.0\n", "4 8\n"])
def test_parse_cpu_count_rejects_malformed_values(output: str) -> None:
    from sysprobe.validators.cpu import parse_cpu_count

    with pytest.raises(
        ValueError,
        match="CPU count must be one positive integer",
    ):
        parse_cpu_count(output)
