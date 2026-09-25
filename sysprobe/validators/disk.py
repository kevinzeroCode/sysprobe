def parse_disk_usage(output: str) -> int:
    """Extract the capacity percentage from POSIX `df -P /` output."""

    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("df output does not contain a data row")

    fields = lines[-1].split()
    if len(fields) < 6:
        raise ValueError("df data row does not contain the expected columns")

    usage_token = fields[-2]
    if not usage_token.endswith("%") or not usage_token[:-1].isdigit():
        raise ValueError("df capacity column is not a percentage")

    return int(usage_token[:-1])
