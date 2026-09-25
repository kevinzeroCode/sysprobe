DF_OUTPUT = """Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/sda1 10000000 7200000 2800000 72% /
"""


def test_parse_disk_usage_reads_capacity_percent() -> None:
    from sysprobe.validators.disk import parse_disk_usage

    assert parse_disk_usage(DF_OUTPUT) == 72
